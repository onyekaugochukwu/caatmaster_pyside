"""
Financial Ratios Dialog
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QCheckBox, QScrollArea,
    QWidget, QMessageBox, QRadioButton, QFrame
)
from PySide6.QtCore import Qt, Signal, QThread, Slot
from PySide6.QtGui import QMovie
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import polars as pl
import re
import json
import asyncio

from ..components.common_modals import BaseModal, create_primary_button, create_success_button
from ..theme import Colors


@dataclass
class FinancialColumnMappings:
    """Structured result from AI column detection"""
    mappings: Dict[str, str] = field(default_factory=dict)
    data_orientation: str = "unknown"
    explanation: str = ""
    source_dataset: str = ""  # Which dataset this mapping applies to

    @property
    def is_row_oriented(self) -> bool:
        return self.data_orientation == "row_oriented"

    def get_column(self, key: str) -> Optional[str]:
        return self.mappings.get(key)


# Financial statement groupings with required concepts
FINANCIAL_CONCEPTS = {
    "Income Statement (P&L)": [
        ("revenue", "Revenue / Sales"),
        ("gross_profit", "Gross Profit"),
        ("cogs", "Cost of Goods Sold"),
        ("ebitda", "EBITDA"),
        ("ebit", "EBIT"),
        ("net_income", "Net Income"),
    ],
    "Balance Sheet": [
        ("current_assets", "Current Assets"),
        ("current_liabilities", "Current Liabilities"),
        ("cash", "Cash & Equivalents"),
        ("inventory", "Inventory"),
        ("total_assets", "Total Assets"),
        ("total_liabilities", "Total Liabilities"),
        ("total_equity", "Total Equity"),
    ],
    "Cash Flow Statement": [
        ("interest_expense", "Interest Expense"),
        ("depreciation_amortization", "Depreciation & Amortization"),
    ]
}


class FinancialRatiosDialog(BaseModal):
    """Dialog for calculating financial ratios with multi-dataset support"""

    transformation_applied = Signal(str, dict)  # operation_id, parameters

    def __init__(self, dataframe: pl.DataFrame, parent=None, available_datasets: Dict[str, pl.DataFrame] = None):
        """Initialize dialog

        Args:
            dataframe: Primary dataset (currently loaded)
            parent: Parent widget
            available_datasets: Dict of {dataset_name: DataFrame} for other saved datasets
        """
        # These must be set before super().__init__() - BaseModal's own
        # __init__ calls self._setup_ui() internally, and _setup_ui() below
        # reads self.dataset_map (via len(self.dataset_map) > 1) - setting
        # it afterward meant this dialog crashed with an AttributeError on
        # every single instantiation. Same ordering already used correctly
        # elsewhere in this codebase (e.g. SplitColumnDialog).
        self.available_datasets = available_datasets or {}
        # Add primary dataset as default option
        self.dataset_map = {"Current Dataset": dataframe}
        if available_datasets:
            self.dataset_map.update(available_datasets)

        # Track which dataset is selected for each statement type
        self.statement_datasets = {}  # {statement_type: dataset_name}

        # Track column combos for each concept
        self.column_combos = {}  # {concept_key: QComboBox}
        self.statement_combos = {}  # {statement_type: QComboBox}

        super().__init__("Financial Ratios Analysis", dataframe, parent)
        self.resize(950, 750)

    def _setup_ui(self):
        """Setup the UI components"""
        main_layout = QVBoxLayout(self)

        # 0. Multi-Dataset Info Section
        info_group = QGroupBox("Data Sources")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; }")
        info_layout = QVBoxLayout(info_group)

        if len(self.dataset_map) > 1:
            info_layout.addWidget(QLabel(
                "<b>Tip:</b> Financial ratios often require data from multiple statements. "
                "Select which dataset to use for each statement type below."
            ))
        else:
            info_layout.addWidget(QLabel(
                "<b>Tip:</b> For multi-statement analysis, save your P&L, Balance Sheet, "
                "and Cash Flow statements as separate datasets first."
            ))

        main_layout.addWidget(info_group)

        # 1. Statement Type Selection with Dataset Dropdowns
        mapping_group = QGroupBox("1. Map Data Columns")
        mapping_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; }")
        mapping_layout = QGridLayout(mapping_group)

        # Dataset selector row
        mapping_layout.addWidget(QLabel("<b>Select Dataset for Each Statement:</b>"), 0, 0, 1, 3)
        row = 1

        dataset_names = list(self.dataset_map.keys())
        dataset_options = [""] + dataset_names

        for stmt_type in FINANCIAL_CONCEPTS.keys():
            # Statement type label
            label = QLabel(f"{stmt_type}:")
            label.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_SECONDARY};")
            mapping_layout.addWidget(label, row, 0)

            # Dataset selector combo
            combo = QComboBox()
            combo.addItems(dataset_options)
            combo.setCurrentText("Current Dataset")  # Default to current
            combo.currentTextChanged.connect(
                lambda checked, st=stmt_type, cb=combo: self._on_dataset_changed(st, cb.currentText)
            )
            mapping_layout.addWidget(combo, row, 1)
            self.statement_combos[stmt_type] = combo

            # Auto-detect button for this statement
            auto_btn = QPushButton(f"Auto-Detect {stmt_type.split()[0]}")
            auto_btn.setToolTip(f"Auto-detect columns for {stmt_type}")
            auto_btn.setObjectName("SuccessButton")
            auto_btn.clicked.connect(
                lambda checked, st=stmt_type: self._auto_detect_for_statement(st)
            )
            mapping_layout.addWidget(auto_btn, row, 2)

            row += 1

        # AI auto-detect button (all statements)
        ai_btn_layout = QHBoxLayout()
        self.ai_detect_btn = QPushButton("AI Auto-Detect All Statements")
        self.ai_detect_btn.setToolTip("Use AI to detect columns across all datasets")
        self.ai_detect_btn.setObjectName("PrimaryButton")
        self.ai_detect_btn.clicked.connect(self._ai_detect_columns)
        ai_btn_layout.addWidget(self.ai_detect_btn)

        # Loading indicator
        self.ai_loading = QLabel()
        self.ai_loading.setFixedSize(20, 20)
        self.ai_loading.setVisible(False)
        ai_btn_layout.addWidget(self.ai_loading)
        ai_btn_layout.addStretch()

        mapping_layout.addLayout(ai_btn_layout, row, 0, 1, 3)
        row += 1

        # Column mapping for each concept
        for stmt_type, concepts in FINANCIAL_CONCEPTS.items():
            # Section header
            header = QLabel(f"\n--- {stmt_type} ---")
            header.setStyleSheet(f"font-weight: bold; color: {Colors.ACCENT}; margin-top: 15px;")
            mapping_layout.addWidget(header, row, 0, 1, 3)
            row += 1

            for key, label in concepts:
                mapping_layout.addWidget(QLabel(f"  {label}:"), row, 1)

                combo = QComboBox()
                self.column_combos[key] = combo
                self._update_combo_for_concept(key, "Current Dataset")
                mapping_layout.addWidget(combo, row, 2)
                row += 1

        scroll = QScrollArea()
        scroll.setWidget(mapping_group)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll, 1)

        # 2. Ratio Selection
        ratios_group = QGroupBox("2. Select Ratios to Calculate")
        ratios_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; }")
        ratios_layout = QGridLayout(ratios_group)

        self.ratio_checks = {}
        
        ratios = [
            ("Liquidity", [
                ("current_ratio", "Current Ratio"),
                ("quick_ratio", "Quick Ratio"),
                ("cash_ratio", "Cash Ratio")
            ]),
            ("Solvency", [
                ("debt_to_equity", "Debt to Equity"),
                ("debt_ratio", "Debt Ratio"),
                ("interest_coverage", "Interest Coverage")
            ]),
            ("Profitability", [
                ("net_profit_margin", "Net Profit Margin"),
                ("gross_margin", "Gross Margin"),
                ("return_on_assets", "Return on Assets (ROA)"),
                ("return_on_equity", "Return on Equity (ROE)"),
                ("ebitda_margin", "EBITDA Margin")
            ]),
            ("Efficiency", [
                ("asset_turnover", "Asset Turnover")
            ])
        ]
        
        col_idx = 0
        for category, items in ratios:
            cat_layout = QVBoxLayout()
            cat_layout.addWidget(QLabel(f"<b>{category}</b>"))
            
            for key, label in items:
                chk = QCheckBox(label)
                chk.setChecked(True)
                self.ratio_checks[key] = chk
                cat_layout.addWidget(chk)
            
            cat_layout.addStretch()
            ratios_layout.addLayout(cat_layout, 0, col_idx)
            col_idx += 1
            
        main_layout.addWidget(ratios_group)
        
        # 3. Advanced Analysis
        advanced_group = QGroupBox("3. Advanced Analysis")
        advanced_group.setStyleSheet("QGroupBox { font-weight: bold; margin-top: 10px; }")
        advanced_layout = QGridLayout(advanced_group)
        
        # Altman Z
        self.altman_chk = QCheckBox("Calculate Altman Z-Score")
        self.altman_chk.setToolTip("Bankruptcy prediction model based on multiple financial ratios.")
        advanced_layout.addWidget(self.altman_chk, 0, 0)
        
        self.public_radio = QRadioButton("Public")
        self.private_radio = QRadioButton("Private")
        self.private_radio.setChecked(True)
        altman_type_layout = QHBoxLayout()
        altman_type_layout.addWidget(self.public_radio)
        altman_type_layout.addWidget(self.private_radio)
        advanced_layout.addLayout(altman_type_layout, 0, 1)
        
        # Vertical Analysis
        self.vertical_chk = QCheckBox("Vertical Analysis (Common Size)")
        advanced_layout.addWidget(self.vertical_chk, 1, 0)
        
        v_base_layout = QHBoxLayout()
        v_base_layout.addWidget(QLabel("Base:"))
        self.v_base_combo = QComboBox()
        # numeric_cols was referenced here but never defined - this dialog
        # crashed with a NameError on every single instantiation. Same
        # numeric-column filter already used elsewhere in this file
        # (_calculate_ratios below).
        numeric_cols = [col for col in self.original_df.columns
                        if self.original_df[col].dtype in (pl.Float64, pl.Float32, pl.Int64, pl.Int32)]
        self.v_base_combo.addItems(numeric_cols)
        # Try to guess base (Total Assets or Revenue)
        for i in range(self.v_base_combo.count()):
            txt = self.v_base_combo.itemText(i).lower()
            if "total_assets" in txt or "revenue" in txt:
                self.v_base_combo.setCurrentIndex(i)
                break
        v_base_layout.addWidget(self.v_base_combo)
        advanced_layout.addLayout(v_base_layout, 1, 1)
        
        # Horizontal Analysis
        self.horizontal_chk = QCheckBox("Horizontal Analysis (Trend)")
        advanced_layout.addWidget(self.horizontal_chk, 2, 0)
        
        h_period_layout = QHBoxLayout()
        h_period_layout.addWidget(QLabel("Period:"))
        self.h_period_combo = QComboBox()
        self.h_period_combo.addItems([""] + list(self.original_df.columns))
        # Try to guess period column
        for i in range(self.h_period_combo.count()):
            txt = self.h_period_combo.itemText(i).lower()
            if "year" in txt or "period" in txt or "date" in txt:
                self.h_period_combo.setCurrentIndex(i)
                break
        h_period_layout.addWidget(self.h_period_combo)
        advanced_layout.addLayout(h_period_layout, 2, 1)
        
        main_layout.addWidget(advanced_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        calc_btn = create_primary_button("Calculate Ratios")
        calc_btn.clicked.connect(self.accept_changes)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(calc_btn)
        
        main_layout.addLayout(btn_layout)

    def _ai_detect_columns(self):
        """Use AI to intelligently detect and map financial columns"""
        from services.ai_service import AIManager

        # Show loading indicator
        self.ai_detect_btn.setEnabled(False)
        self.ai_detect_btn.setText("AI Analyzing...")
        self.ai_loading.setVisible(True)

        try:
            # Get data info
            all_cols = list(self.original_df.columns)
            numeric_cols = [col for col in all_cols
                           if self.original_df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]

            # Get sample data from first column (for row-oriented data)
            first_col_values = []
            if self.original_df.height > 0:
                for i in range(min(30, self.original_df.height)):
                    val = self.original_df.row(i)[0]
                    if val is not None and str(val).strip():
                        first_col_values.append(str(val).strip())

            # Get sample values from numeric columns
            sample_data = {}
            for col in numeric_cols[:5]:  # First 5 numeric columns
                values = []
                for i in range(min(5, self.original_df.height)):
                    val = self.original_df.row(i)
                    col_idx = list(self.original_df.columns).index(col)
                    if val[col_idx] is not None:
                        values.append(str(val[col_idx]))
                if values:
                    sample_data[col] = values[:5]

            # Build the prompt
            prompt = self._build_ai_prompt(all_cols, first_col_values, sample_data)

            # Create a thread to run the async AI call
            class AIThread(QThread):
                result_ready = Signal(dict)

                def __init__(self, prompt):
                    super().__init__()
                    self.prompt = prompt

                def run(self):
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                        # Import and load stored providers
                        from services.ai_service import load_stored_providers
                        manager = AIManager()
                        load_stored_providers(manager)

                        provider = manager.get_provider()

                        if not provider:
                            self.result_ready.emit({"error": "No AI provider configured. Please add a provider in AI Settings."})
                            return

                        # Initialize the provider if needed (initialize is sync, not async)
                        if hasattr(provider, 'initialize'):
                            init_result = provider.initialize()
                            if not init_result:
                                self.result_ready.emit({"error": f"Failed to initialize provider: {provider.provider_name}"})
                                return

                        response = loop.run_until_complete(
                            manager.complete(self.prompt, task_type="general", temperature=0.1, force_json=True)
                        )

                        # Parse the JSON response
                        result = self._parse_response(response.content)
                        self.result_ready.emit(result)
                    except Exception as e:
                        self.result_ready.emit({"error": str(e)})

                def _parse_response(self, content):
                    """Parse AI response to extract mappings"""
                    try:
                        # Clean up the content - remove markdown code blocks if present
                        clean_content = content.strip()
                        clean_content = re.sub(r'^```json\s*\n?', '', clean_content)
                        clean_content = re.sub(r'^```\s*\n?', '', clean_content)
                        clean_content = re.sub(r'\n?```\s*$', '', clean_content)

                        # Try to find a JSON object in the content
                        json_match = re.search(r'\{[^{}]*"mappings"[^{}]*\}', clean_content, re.DOTALL)
                        if json_match:
                            result = json.loads(json_match.group())
                            if "mappings" in result:
                                return result

                        # Try to parse the whole content as JSON
                        try:
                            result = json.loads(clean_content)
                            if "mappings" in result:
                                return result
                        except:
                            pass

                        # Last resort: try to extract from AI's alternative format
                        # Handle "financial_statement_mapping" or "columns" format
                        try:
                            result = json.loads(clean_content)
                            if "financial_statement_mapping" in result:
                                # Extract mappings from the AI's format
                                mappings = {}
                                columns = result.get("financial_statement_mapping", {}).get("columns", {})
                                for col_name, mapping_info in columns.items():
                                    if isinstance(mapping_info, dict):
                                        concept = mapping_info.get("standard_concept", "")
                                        # Map to our standard concepts
                                        concept_lower = concept.lower()
                                        if "revenue" in concept_lower:
                                            mappings["revenue"] = col_name
                                        elif "net income" in concept_lower or "profit" in concept_lower:
                                            mappings["net_income"] = col_name
                                        elif "total asset" in concept_lower:
                                            mappings["total_assets"] = col_name
                                        elif "total liab" in concept_lower:
                                            mappings["total_liabilities"] = col_name
                                        elif "equity" in concept_lower:
                                            mappings["total_equity"] = col_name
                                        elif "current asset" in concept_lower:
                                            mappings["current_assets"] = col_name
                                        elif "current liab" in concept_lower:
                                            mappings["current_liabilities"] = col_name
                                        elif "cash" in concept_lower:
                                            mappings["cash"] = col_name
                                        elif "inventor" in concept_lower:
                                            mappings["inventory"] = col_name
                                        elif "gross profit" in concept_lower:
                                            mappings["gross_profit"] = col_name
                                        elif "cogs" in concept_lower or "cost of good" in concept_lower:
                                            mappings["cogs"] = col_name
                                        elif "ebitda" in concept_lower:
                                            mappings["ebitda"] = col_name
                                        elif "ebit" in concept_lower or "operating" in concept_lower:
                                            mappings["ebit"] = col_name
                                        elif "interest" in concept_lower:
                                            mappings["interest_expense"] = col_name
                                return {
                                    "mappings": mappings,
                                    "data_orientation": "unknown",
                                    "explanation": "Parsed from alternative format"
                                }
                        except:
                            pass

                        return {"error": "Response missing 'mappings' field", "raw": content[:500]}

                    except json.JSONDecodeError as e:
                        print(f"JSON parse error: {e}")
                        print(f"AI Response (first 500 chars): {content[:500]}")
                        return {"error": f"Invalid JSON response: {e}", "raw": content[:500]}
                    except Exception as e:
                        return {"error": f"Parse error: {str(e)}", "raw": content[:500]}

                def _parse_markdown_table(self, content):
                    """Parse markdown table format to extract mappings"""
                    try:
                        lines = content.strip().split('\n')
                        mappings = {}
                        data_orientation = "unknown"
                        explanation = ""

                        # Find the header line and separator line
                        header_idx = None
                        for i, line in enumerate(lines):
                            if '|' in line and ('Column' in line.lower() or 'Concept' in line.lower() or 'Name' in line.lower()):
                                header_idx = i
                                break

                        if header_idx is None:
                            return None

                        # Get the separator line
                        if header_idx + 1 >= len(lines):
                            return None
                        separator = lines[header_idx + 1]

                        # Parse the table rows
                        for i in range(header_idx + 2, len(lines)):
                            line = lines[i].strip()
                            if not line or not line.startswith('|'):
                                continue

                            # Parse the row
                            parts = [p.strip() for p in line.split('|')[1:-1]]
                            if len(parts) >= 2:
                                col_name = parts[0].strip()
                                concept = parts[1].strip()

                                # Map concept names to our keys
                                concept_lower = concept.lower()
                                if 'revenue' in concept_lower or 'sale' in concept_lower:
                                    mappings['revenue'] = col_name
                                elif 'net income' in concept_lower or 'net profit' in concept_lower:
                                    mappings['net_income'] = col_name
                                elif 'total asset' in concept_lower:
                                    mappings['total_assets'] = col_name
                                elif 'total liab' in concept_lower:
                                    mappings['total_liabilities'] = col_name
                                elif 'equity' in concept_lower:
                                    mappings['total_equity'] = col_name
                                elif 'current asset' in concept_lower:
                                    mappings['current_assets'] = col_name
                                elif 'current liab' in concept_lower:
                                    mappings['current_liabilities'] = col_name
                                elif 'cash' in concept_lower:
                                    mappings['cash'] = col_name
                                elif 'inventor' in concept_lower:
                                    mappings['inventory'] = col_name
                                elif 'gross profit' in concept_lower:
                                    mappings['gross_profit'] = col_name
                                elif 'cogs' in concept_lower or 'cost of good' in concept_lower:
                                    mappings['cogs'] = col_name
                                elif 'ebitda' in concept_lower:
                                    mappings['ebitda'] = col_name
                                elif 'ebit' in concept_lower or 'operating' in concept_lower:
                                    mappings['ebit'] = col_name
                                elif 'interest' in concept_lower:
                                    mappings['interest_expense'] = col_name

                        if mappings:
                            # Determine if data is row-oriented based on column names
                            if col_name.startswith('col_') or col_name.replace('.', '').replace('-', '').isdigit():
                                data_orientation = "column_oriented"
                            else:
                                data_orientation = "row_oriented"

                            return {
                                "mappings": mappings,
                                "data_orientation": data_orientation,
                                "explanation": "Parsed from markdown table format"
                            }

                        return None
                    except Exception as e:
                        return None

            # Start the AI thread
            self.ai_thread = AIThread(prompt)
            self.ai_thread.result_ready.connect(self._on_ai_result)
            self.ai_thread.start()

        except Exception as e:
            self.ai_detect_btn.setEnabled(True)
            self.ai_detect_btn.setText("Auto-Detect (AI)")
            self.ai_loading.setVisible(False)
            QMessageBox.warning(self, "AI Error", f"Failed to use AI detection:\n{str(e)}")

    def _build_ai_prompt(self, all_cols, first_col_values, sample_data):
        """Build the AI prompt for column mapping"""
        prompt = f"""Map these financial line items to standard concepts. Output MUST be simple JSON.

DATA COLUMNS: {all_cols}

FIRST COLUMN VALUES:
"""

        # Add first column values as they contain line items
        for val in first_col_values[:30]:
            prompt += f"- {val}\n"

        if sample_data:
            prompt += "\nSAMPLE DATA:\n"
            for col, values in list(sample_data.items())[:5]:
                prompt += f"- {col}: {values}\n"

        prompt += """
OUTPUT MUST BE EXACTLY THIS STRUCTURE (no nesting beyond "mappings"):

{"mappings":{"revenue":"Revenue","net_income":"Net Income","total_assets":null,"total_liabilities":null,"total_equity":null,"current_assets":null,"current_liabilities":null,"cash":null,"inventory":null,"gross_profit":null,"cogs":null,"ebitda":null,"ebit":null,"interest_expense":null},"data_orientation":"row_oriented","explanation":"short text"}

REQUIREMENTS:
- "mappings" is a flat object, NOT nested
- Use null for unmapped concepts
- DO NOT use "financial_statement_mapping" or "columns"
- Response must be ONE LINE of valid JSON starting with { and ending with }
- No markdown, no code blocks, no formatting

If no mappings found: {"mappings":{},"error":"Could not determine mappings"}

{"mappings":{"revenue":"", "net_income":"""

        return prompt

    @Slot(dict)
    def _on_ai_result(self, result):
        """Handle AI detection result"""
        # Reset button state
        self.ai_detect_btn.setEnabled(True)
        self.ai_detect_btn.setText("Auto-Detect (AI)")
        self.ai_loading.setVisible(False)

        if "error" in result:
            error_msg = result['error']
            if "raw" in result:
                error_msg += f"\n\nAI Response:\n{result['raw']}"
            QMessageBox.warning(self, "AI Error", f"AI detection failed:\n{error_msg}")
            return

        # Apply the mappings
        mappings = result.get("mappings", {})
        data_orientation = result.get("data_orientation", "unknown")
        explanation = result.get("explanation", "")

        detected_count = 0
        row_oriented_detected = []

        # Get first column values for matching (for row-oriented data)
        first_col_values = []
        if self.original_df.height > 0:
            for i in range(min(50, self.original_df.height)):
                val = self.original_df.row(i)[0]
                if val is not None and str(val).strip():
                    first_col_values.append(str(val).strip().lower())

        for key, value in mappings.items():
            if key in self.column_combos:
                # Check if the value matches a column name (column-oriented)
                if value in self.original_df.columns:
                    self.column_combos[key].setCurrentText(value)
                    detected_count += 1
                # Check if the value matches a first-column value (row-oriented)
                elif value and str(value).strip().lower() in first_col_values:
                    row_oriented_detected.append((key, value))
                # Value is null or invalid
                elif value is None or str(value).strip() == "" or str(value).strip().lower() == "null":
                    pass  # Skip unmapped fields
                else:
                    # Unknown format - try as-is or treat as row-oriented
                    row_oriented_detected.append((key, value))

        # Show results
        if row_oriented_detected:
            guidance = (
                "AI detected that your data is ROW-ORIENTED (line items as rows).\n\n"
                f"Explanation: {explanation}\n\n"
                "To use Financial Ratios analysis, you need to restructure the data:\n\n"
                "Step 1: Remove header rows if any\n"
                "   Use: Table → Transform → Remove Rows\n\n"
                "Step 2: Promote year/period row to headers\n"
                "   Use: Table → Transform → Use First Row as Headers\n\n"
                "Step 3: Transpose the data (swap rows and columns)\n"
                "   Use: Table → Transform → Transpose\n\n"
                "Step 4: Run Financial Ratios analysis\n\n"
                "AI-detected line items (these are in your first column):\n"
            )
            for key, val in row_oriented_detected:
                guidance += f"  - {key}: {val}\n"

            QMessageBox.warning(self, "Data Restructuring Required", guidance)
        elif detected_count > 0:
            QMessageBox.information(
                self, "AI Detection Complete",
                f"AI successfully mapped {detected_count} column(s).\n"
                f"Explanation: {explanation}\n\n"
                "Please review and adjust mappings as needed."
            )
        else:
            QMessageBox.warning(
                self, "No Matches Found",
                "AI could not detect any financial columns.\n"
                "Please map columns manually."
            )

    def _on_dataset_changed(self, stmt_type: str, dataset_name: str):
        """Handle dataset selection change for a statement type"""
        self.statement_datasets[stmt_type] = dataset_name

        # Update all column combos for concepts in this statement type
        concepts = FINANCIAL_CONCEPTS.get(stmt_type, [])
        for key, label in concepts:
            if key in self.column_combos:
                self._update_combo_for_concept(key, dataset_name)

    def _update_combo_for_concept(self, concept_key: str, dataset_name: str):
        """Update a combo box with columns from the selected dataset"""
        combo = self.column_combos.get(concept_key)
        if combo is None:
            return

        # Get the dataset
        if not dataset_name or dataset_name == "Current Dataset":
            df = self.original_df
        else:
            df = self.dataset_map.get(dataset_name)
            if df is None:
                df = self.original_df

        if df is None:
            return

        # Get numeric columns
        numeric_cols = [col for col in df.columns
                       if df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]
        all_cols = list(df.columns)
        options = [""] + all_cols

        # Save current selection if it's still valid
        current = combo.currentText()

        combo.clear()
        combo.addItems(options)

        # Try to restore selection
        if current in options:
            combo.setCurrentText(current)
        elif numeric_cols:
            # Default to first numeric column
            combo.setCurrentIndex(1)

    def _auto_detect_for_statement(self, stmt_type: str):
        """Auto-detect columns for a specific statement type"""
        dataset_name = self.statement_datasets.get(stmt_type, "Current Dataset")
        if not dataset_name or dataset_name == "Current Dataset":
            df = self.original_df
        else:
            df = self.dataset_map.get(dataset_name, self.original_df)

        if df is None:
            return

        # Get concepts for this statement type
        concepts = FINANCIAL_CONCEPTS.get(stmt_type, [])

        # Run pattern-based detection
        all_cols = list(df.columns)
        detection_patterns = {
            "revenue": [r"revenue", r"sale", r"turnover"],
            "gross_profit": [r"gross.?profit"],
            "cogs": [r"cogs", r"cost.?of.?good", r"cost.?of.?sale"],
            "ebitda": [r"ebitda"],
            "ebit": [r"ebit", r"operating.?income", r"operating.?profit"],
            "net_income": [r"net.?income", r"profit.?after.?tax"],
            "current_assets": [r"current.?asset", r"receivable"],
            "current_liabilities": [r"current.?liabil", r"payable"],
            "cash": [r"cash", r"bank"],
            "inventory": [r"invent", r"stock"],
            "total_assets": [r"total.?asset"],
            "total_liabilities": [r"total.?liabil"],
            "total_equity": [r"total.?equit", r"shareholder"],
            "interest_expense": [r"interest.?expense"],
            "depreciation_amortization": [r"depreciat", r"amortiz"],
        }

        detected = 0
        for key, label in concepts:
            if key not in detection_patterns:
                continue
            patterns = detection_patterns[key]
            matched = False
            for col in all_cols:
                col_lower = col.lower()
                for pattern in patterns:
                    if re.search(pattern, col_lower):
                        self.column_combos[key].setCurrentText(col)
                        detected += 1
                        matched = True
                        break
                if matched:
                    break

        if detected > 0:
            QMessageBox.information(
                self, "Detection Complete",
                f"Auto-detected {detected} column(s) for {stmt_type}."
            )
        else:
            QMessageBox.warning(
                self, "No Matches",
                f"Could not auto-detect columns for {stmt_type}.\n"
                "Please map manually."
            )

    def _auto_detect_columns(self):
        """Auto-detect financial columns based on common patterns"""
        all_cols = list(self.original_df.columns)

        # Patterns to match financial terms - regex patterns
        # Key: (concept_key, search_patterns)
        detection_patterns = {
            # Liquidity
            "current_assets": [
                r"current.?asset", r"total.?current.?asset",
                r"receivable", r"debtor", r"trade.?receive"
            ],
            "current_liabilities": [
                r"current.?liabil", r"total.?current.?liabil",
                r"payable", r"creditor", r"trade.?payable",
                r"short.?term.?debt"
            ],
            "cash": [
                r"cash", r"bank", r"cash.?equival"
            ],
            "inventory": [
                r"invent", r"stock", r"goods"
            ],
            # Solvency
            "total_assets": [
                r"total.?asset", r"asset.?total"
            ],
            "total_liabilities": [
                r"total.?liabil", r"liabil.?total",
                r"non.?current.?liabil"
            ],
            "total_equity": [
                r"total.?equit", r"equit.?total",
                r"shareholder", r"stockholder",
                r"reserve", r"retained.?earn"
            ],
            "interest_expense": [
                r"interest.?expense", r"finance.?cost",
                r"interest.?cost"
            ],
            # Profitability
            "revenue": [
                r"revenue", r"sale", r"turnover",
                r"income.?from.?oper", r"operating.?income"
            ],
            "net_income": [
                r"net.?income", r"profit.?after.?tax",
                r"profit.?for.?year", r"earn"
            ],
            "gross_profit": [
                r"gross.?profit", r"gross.?margin"
            ],
            "cogs": [
                r"cost.?of.?good", r"cogs", r"cost.?of.?sale",
                r"direct.?cost", r"operational.?expense"
            ],
            "ebitda": [
                r"ebitda", r"earning.?before.?interest",
                r"operating.?profit.?before.?deprec"
            ],
            "ebit": [
                r"ebit", r"operating.?income",
                r"operating.?profit", r"earning.?before.?interest.?tax"
            ],
            "retained_earnings": [
                r"retained.?earn", r"accumulate.?profit"
            ]
        }

        # Try to detect if data is row-oriented (line items in first column)
        first_col = all_cols[0] if all_cols else ""
        first_col_values = []
        if self.original_df.height > 0:
            first_col_values = [str(self.original_df.row(i)[0]) for i in range(min(30, self.original_df.height))]

        # Combine column names and first column values for matching
        search_values = all_cols.copy()
        search_values.extend(first_col_values)

        # Track what columns have been matched
        matched_cols = {}

        for key, patterns in detection_patterns.items():
            # First try to match column names (column-oriented data)
            for col in all_cols:
                col_lower = col.lower()
                for pattern in patterns:
                    if re.search(pattern, col_lower):
                        if key not in matched_cols:
                            matched_cols[key] = col
                        break

            # If not found, try to match first column values (row-oriented data)
            if key not in matched_cols:
                for val in first_col_values:
                    val_lower = val.lower()
                    for pattern in patterns:
                        if re.search(pattern, val_lower):
                            # For row-oriented data, we need to tell user to transpose
                            matched_cols[key] = f"[Row: {val}]"
                            break
                    if key in matched_cols:
                        break

        # Update combos
        detected_count = 0
        missing_from_cols = []

        for key, combo in self.column_combos.items():
            if key in matched_cols:
                matched_val = matched_cols[key]
                if matched_val.startswith("[Row:"):
                    # This is a row-oriented match
                    missing_from_cols.append((key, matched_val))
                else:
                    combo.setCurrentText(matched_val)
                    detected_count += 1

        # Show results
        if missing_from_cols:
            # Data is row-oriented - provide guidance
            guidance = (
                "Your data appears to be ROW-ORIENTED (line items as rows).\n\n"
                "To use Financial Ratios analysis, you need to:\n"
                "1. Use 'Table → Transform → Use First Row as Headers' to promote year headers\n"
                "2. Use 'Table → Transform → Transpose' to swap rows/columns\n"
                "3. Then run Financial Ratios analysis\n\n"
                f"Detected line items:\n"
            )
            for key, val in missing_from_cols:
                guidance += f"  - {key}: {val}\n"

            QMessageBox.warning(self, "Data Restructuring Required", guidance)
        elif detected_count > 0:
            QMessageBox.information(
                self, "Auto-Detection Complete",
                f"Successfully detected {detected_count} financial column(s).\n"
                "Please review and adjust mappings as needed."
            )
        else:
            QMessageBox.warning(
                self, "No Matches Found",
                "Could not auto-detect any financial columns.\n"
                "Please map columns manually or check your column names."
            )

    def get_parameters(self):
        """Get the parameters for the operation"""
        mapping = {}
        dataset_mapping = {}  # Track which dataset each concept uses
        for key, combo in self.column_combos.items():
            val = combo.currentText()
            if val:
                mapping[key] = val
                # Find which dataset this concept's combo belongs to
                for stmt_type, concepts in FINANCIAL_CONCEPTS.items():
                    if key in [c[0] for c in concepts]:
                        dataset_mapping[key] = self.statement_datasets.get(stmt_type, "Current Dataset")
                        break

        ratios = []
        for key, chk in self.ratio_checks.items():
            if chk.isChecked():
                ratios.append(key)

        # Get all numeric columns for vertical/horizontal analysis
        numeric_cols = [col for col in self.original_df.columns
                       if self.original_df[col].dtype in [pl.Float64, pl.Float32, pl.Int64, pl.Int32]]

        # Build all_datasets dict - only include non-Current Dataset entries
        all_datasets = {}
        for name, df in self.dataset_map.items():
            if name != "Current Dataset" and df is not None:
                all_datasets[name] = df

        return {
            "mapping": mapping,
            "dataset_mapping": dataset_mapping,  # Which dataset each concept comes from
            "all_datasets": all_datasets,  # Dict of available datasets (excluding primary)
            "ratios": ratios,
            "do_altman_z": self.altman_chk.isChecked(),
            "is_public": self.public_radio.isChecked(),
            "vertical_base": self.v_base_combo.currentText() if self.vertical_chk.isChecked() else None,
            "vertical_cols": numeric_cols if self.vertical_chk.isChecked() else [],
            "horizontal_period": self.h_period_combo.currentText() if self.horizontal_chk.isChecked() else None,
            "horizontal_cols": numeric_cols if self.horizontal_chk.isChecked() else []
        }

    def accept_changes(self):
        """Validate and accept"""
        params = self.get_parameters()
        if not params["mapping"]:
            QMessageBox.warning(self, "Missing Mapping", "Please map at least one data column.")
            return
            
        if not any([params["ratios"], params["do_altman_z"], params["vertical_base"], params["horizontal_period"]]):
            QMessageBox.warning(self, "No Analysis Selected", "Please select at least one analysis type to perform.")
            return
            
        self.transformation_applied.emit("financial_ratios", params)
        self.accept()
