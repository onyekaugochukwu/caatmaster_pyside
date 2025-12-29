"""
Report Generation Service for CAATmaster
Generate reports with embedded charts and data tables
"""
import polars as pl
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import io
import base64

from services.visualization_service import VisualizationService


class ReportSection:
    """Represents a section in a report"""

    def __init__(
        self,
        title: str,
        section_type: str,
        content: Any = None,
        chart_config: Dict = None,
        table_config: Dict = None
    ):
        self.title = title
        self.section_type = section_type  # 'text', 'chart', 'table', 'summary', 'transformation_steps'
        self.content = content
        self.chart_config = chart_config or {}
        self.table_config = table_config or {}


class ReportService:
    """Service for generating HTML and PDF reports"""

    def __init__(self):
        """Initialize the report service"""
        self.viz_service = VisualizationService()

    def generate_report(
        self,
        df: pl.DataFrame,
        title: str,
        sections: List[ReportSection],
        author: str = "CAATmaster",
        output_path: str = None
    ) -> str:
        """
        Generate a complete HTML report

        Args:
            df: Source DataFrame
            title: Report title
            sections: List of ReportSection objects
            author: Report author
            output_path: Optional output file path

        Returns:
            HTML report as string
        """
        # Create HTML content
        html_parts = []
        html_parts.append(self._create_html_header(title))

        # Report info header
        html_parts.append(self._create_report_header(title, author, df))

        # Process each section
        for section in sections:
            html_parts.append(self._create_section(df, section))

        # Footer
        html_parts.append(self._create_html_footer())

        # Combine
        full_html = "\n".join(html_parts)

        # Save to file if path provided
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(full_html)

        return full_html

    def _create_html_header(self, title: str) -> str:
        """Create HTML document header"""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-radius: 8px;
        }}
        .report-header {{
            border-bottom: 3px solid #0078d4;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .report-header h1 {{
            color: #0078d4;
            margin: 0 0 10px 0;
            font-size: 32px;
        }}
        .report-meta {{
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }}
        .section {{
            margin: 30px 0;
        }}
        .section-title {{
            color: #333;
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e0e0e0;
        }}
        .section-content {{
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
        }}
        th {{
            background: #0078d4;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #e0e0e0;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        tr:hover {{
            background: #f0f0f0;
        }}
        .chart-container {{
            text-align: center;
            margin: 20px 0;
            padding: 20px;
            background: #fafafa;
            border-radius: 4px;
        }}
        .chart-container img {{
            max-width: 100%;
            height: auto;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #0078d4 0%, #005a9e 100%);
            color: white;
            padding: 20px;
            border-radius: 6px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .summary-card.secondary {{
            background: linear-gradient(135deg, #28a745 0%, #218838 100%);
        }}
        .summary-card.accent {{
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
        }}
        .summary-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            opacity: 0.9;
            margin-bottom: 10px;
        }}
        .summary-value {{
            font-size: 32px;
            font-weight: bold;
            margin: 0;
        }}
        .text-content {{
            line-height: 1.6;
            color: #555;
            padding: 10px 0;
        }}
        .transformation-step {{
            background: #f8f8f8;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #0078d4;
            border-radius: 4px;
        }}
        .transformation-step .step-number {{
            font-weight: bold;
            color: #0078d4;
            margin-right: 10px;
        }}
        .report-footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #999;
            font-size: 12px;
        }}
        @media print {{
            body {{ background: white; }}
            .container {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="container">
"""

    def _create_html_footer(self) -> str:
        """Create HTML document footer"""
        return f"""
        <div class="report-footer">
            <p>Generated by CAATmaster - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Professional Continuous Audit Analytics Tool</p>
        </div>
    </div>
</body>
</html>
"""

    def _create_report_header(self, title: str, author: str, df: pl.DataFrame) -> str:
        """Create report header with metadata"""
        rows = len(df)
        cols = len(df.columns)
        memory_mb = df.estimated_size('mb')

        return f"""
        <div class="report-header">
            <h1>{title}</h1>
            <div class="report-meta">
                <strong>Author:</strong> {author} &nbsp;|&nbsp;
                <strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp;
                <strong>Data:</strong> {rows:,} rows × {cols} columns ({memory_mb:.2f} MB)
            </div>
        </div>
"""

    def _create_section(self, df: pl.DataFrame, section: ReportSection) -> str:
        """Create HTML for a section"""
        html = f'<div class="section">\n'
        html += f'    <h2 class="section-title">{section.title}</h2>\n'
        html += f'    <div class="section-content">\n'

        if section.section_type == 'text':
            html += self._create_text_section(section.content)

        elif section.section_type == 'summary':
            html += self._create_summary_section(df)

        elif section.section_type == 'chart':
            html += self._create_chart_section(df, section)

        elif section.section_type == 'table':
            html += self._create_table_section(df, section)

        elif section.section_type == 'transformation_steps':
            html += self._create_transformation_steps_section(section.content)

        html += '    </div>\n'
        html += '</div>\n'

        return html

    def _create_text_section(self, content: str) -> str:
        """Create text content section"""
        return f'        <div class="text-content">{content}</div>\n'

    def _create_summary_section(self, df: pl.DataFrame) -> str:
        """Create summary statistics section"""
        rows = len(df)
        cols = len(df.columns)
        memory_mb = df.estimated_size('mb')

        # Count nulls
        total_nulls = sum(df[col].null_count() for col in df.columns)

        html = f"""
        <div class="summary-grid">
            <div class="summary-card">
                <div class="summary-label">Total Rows</div>
                <p class="summary-value">{rows:,}</p>
            </div>
            <div class="summary-card secondary">
                <div class="summary-label">Total Columns</div>
                <p class="summary-value">{cols}</p>
            </div>
            <div class="summary-card accent">
                <div class="summary-label">Memory Size</div>
                <p class="summary-value">{memory_mb:.1f} MB</p>
            </div>
            <div class="summary-card">
                <div class="summary-label">Missing Values</div>
                <p class="summary-value">{total_nulls:,}</p>
            </div>
        </div>
"""

        # Column information table
        html += """
        <h3>Column Details</h3>
        <table>
            <thead>
                <tr>
                    <th>Column</th>
                    <th>Type</th>
                    <th>Null Count</th>
                    <th>Unique Values</th>
                </tr>
            </thead>
            <tbody>
"""

        for col in df.columns:
            col_type = df[col].dtype
            null_count = df[col].null_count()
            unique_count = df[col].n_unique()

            html += f"""
                <tr>
                    <td>{col}</td>
                    <td>{col_type}</td>
                    <td>{null_count:,}</td>
                    <td>{unique_count:,}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
"""

        return html

    def _create_chart_section(self, df: pl.DataFrame, section: ReportSection) -> str:
        """Create chart section with embedded image"""
        config = section.chart_config

        try:
            # Create the chart
            chart_type = config.get('type', 'bar')

            if chart_type == 'bar':
                fig = self.viz_service.create_bar_chart(
                    df, config.get('x_column'), config.get('y_column'),
                    config.get('title', 'Bar Chart'),
                    config.get('group_column'),
                    figsize=config.get('figsize', (10, 6))
                )
            elif chart_type == 'line':
                fig = self.viz_service.create_line_chart(
                    df, config.get('x_column'), [config.get('y_column')],
                    config.get('title', 'Line Chart'),
                    figsize=config.get('figsize', (10, 6))
                )
            elif chart_type == 'scatter':
                fig = self.viz_service.create_scatter_plot(
                    df, config.get('x_column'), config.get('y_column'),
                    config.get('title', 'Scatter Plot'),
                    config.get('group_column'),
                    figsize=config.get('figsize', (10, 6))
                )
            elif chart_type == 'histogram':
                fig = self.viz_service.create_histogram(
                    df, config.get('column'),
                    config.get('title', 'Histogram'),
                    bins=config.get('bins', 30),
                    figsize=config.get('figsize', (10, 6))
                )
            elif chart_type == 'pie':
                fig = self.viz_service.create_pie_chart(
                    df, config.get('label_column'), config.get('value_column'),
                    config.get('title', 'Pie Chart'),
                    figsize=config.get('figsize', (8, 8))
                )
            elif chart_type == 'box':
                fig = self.viz_service.create_box_plot(
                    df, config.get('value_column'), config.get('group_column'),
                    config.get('title', 'Box Plot'),
                    figsize=config.get('figsize', (10, 6))
                )
            elif chart_type == 'heatmap':
                fig = self.viz_service.create_heatmap(
                    df, config.get('title', 'Heatmap'),
                    figsize=config.get('figsize', (10, 8))
                )
            elif chart_type == 'area':
                fig = self.viz_service.create_area_chart(
                    df, config.get('x_column'), [config.get('y_column')],
                    config.get('title', 'Area Chart'),
                    figsize=config.get('figsize', (10, 6))
                )
            else:
                return '<p>Unknown chart type</p>'

            # Convert to base64
            img_data = self.viz_service.get_figure_as_image(fig)
            img_base64 = base64.b64encode(img_data).decode('utf-8')

            html = f"""
        <div class="chart-container">
            <img src="data:image/png;base64,{img_base64}" alt="{section.title}">
        </div>
"""

            # Close figure to free memory
            import matplotlib.pyplot as plt
            plt.close(fig)

            return html

        except Exception as e:
            return f'<p>Error creating chart: {str(e)}</p>'

    def _create_table_section(self, df: pl.DataFrame, section: ReportSection) -> str:
        """Create data table section"""
        config = section.table_config

        # Get display DataFrame
        max_rows = config.get('max_rows', 100)
        display_df = df.head(max_rows)

        # Select columns if specified
        if 'columns' in config and config['columns']:
            display_df = display_df.select(config['columns'])

        html = """
        <table>
            <thead>
                <tr>
"""
        # Headers
        for col in display_df.columns:
            html += f'                    <th>{col}</th>\n'
        html += "                </tr>\n"
        html += "            </thead>\n"
        html += "            <tbody>\n"

        # Data rows
        for row_idx in range(len(display_df)):
            html += "                <tr>\n"
            for col in display_df.columns:
                value = display_df[row_idx, col]
                # Format value
                if value is None:
                    display_val = "<em>NULL</em>"
                else:
                    display_val = str(value)
                    # Truncate long strings
                    if len(display_val) > 100:
                        display_val = display_val[:100] + "..."
                html += f'                    <td>{display_val}</td>\n'
            html += "                </tr>\n"

        html += "            </tbody>\n"
        html += "        </table>\n"

        if len(df) > max_rows:
            html += f"<p><em>Showing {max_rows:,} of {len(df):,} rows</em></p>\n"

        return html

    def _create_transformation_steps_section(self, steps: List[Dict]) -> str:
        """Create transformation steps section"""
        if not steps:
            return '<p>No transformation steps applied.</p>\n'

        html = ""

        for i, step in enumerate(steps, 1):
            html += f"""
        <div class="transformation-step">
            <span class="step-number">{i}.</span>
            <strong>{step.get('operation', 'Unknown')}</strong>
            {f"- {step.get('description', '')}" if step.get('description') else ""}
            <br><small style="color: #666;">{step.get('timestamp', '')}</small>
        </div>
"""

        return html

    def create_quick_report(
        self,
        df: pl.DataFrame,
        title: str = "Data Analysis Report",
        include_summary: bool = True,
        include_chart: bool = True,
        include_table: bool = True,
        chart_columns: List[str] = None,
        output_path: str = None
    ) -> str:
        """
        Create a quick report with common sections

        Args:
            df: Source DataFrame
            title: Report title
            include_summary: Include summary statistics
            include_chart: Include auto-generated chart
            include_table: Include data table
            chart_columns: Columns to use for chart (auto-detect if None)
            output_path: Output file path

        Returns:
            HTML report as string
        """
        sections = []

        # Summary section
        if include_summary:
            sections.append(ReportSection(
                "Data Overview",
                "summary"
            ))

        # Auto-generate a chart
        if include_chart and chart_columns:
            numeric_cols = self.viz_service.get_numeric_columns(df)
            categorical_cols = self.viz_service.get_categorical_columns(df)

            # Try to create a meaningful chart
            if len(categorical_cols) > 0 and len(numeric_cols) > 0:
                # Bar chart
                x_col = categorical_cols[0]
                y_col = numeric_cols[0]
                sections.append(ReportSection(
                    f"{y_col} by {x_col}",
                    "chart",
                    chart_config={
                        'type': 'bar',
                        'x_column': x_col,
                        'y_column': y_col,
                        'title': f"{y_col} by {x_col}"
                    }
                ))
            elif len(numeric_cols) >= 2:
                # Scatter plot
                sections.append(ReportSection(
                    f"{numeric_cols[0]} vs {numeric_cols[1]}",
                    "chart",
                    chart_config={
                        'type': 'scatter',
                        'x_column': numeric_cols[0],
                        'y_column': numeric_cols[1],
                        'title': f"{numeric_cols[0]} vs {numeric_cols[1]}"
                    }
                ))

        # Data table
        if include_table:
            sections.append(ReportSection(
                "Sample Data",
                "table",
                table_config={'max_rows': 100}
            ))

        return self.generate_report(df, title, sections, output_path=output_path)
