from enum import Enum

class TransformationStepType(str, Enum):
    """Enumeration for the different types of transformation steps."""
    CALCULATE = "calculate"
    FILTER = "filter"
    SORT = "sort"
    ML_PREDICT = "ml_predict"
    ML_TRAIN = "ml_train"
    AI_ENRICH = "ai_enrich"
    AI_EXTRACT = "ai_extract"
    AI_PATTERN_LEARN = "ai_pattern_learn"
    AUDIT_FLAG = "audit_flag"
    STAT_ADD_GROUP = "stat_add_group"
    AGGREGATE = "aggregate"
    JOIN = "join"
    PIVOT = "pivot"
    UNPIVOT = "unpivot"
    QUERY = "query"


OPERATION_REGISTRY = {
    # =========================================================================
    # SQL (DuckDB) — recorded as a first-class pipeline step so a query run
    # from the SQL view shows up in Applied Steps and replays on refresh,
    # exactly like any ribbon transformation.
    # =========================================================================
    "sql_query": {
        "display_name": "SQL Query",
        "type": TransformationStepType.QUERY,
        "category": "sql",
        "description": "Transform the dataset with a DuckDB SQL query",
        "parameter_schema": {
            "query": {"type": "text", "required": True, "label": "SQL Query"}
        },
        "creates_columns": False,
    },

    # =========================================================================
    # TEXT TRANSFORMATIONS
    # =========================================================================
    "text_uppercase": {
        "display_name": "Uppercase",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Converts all text to uppercase",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_upper"
    },
    "text_lowercase": {
        "display_name": "Lowercase",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Converts all text to lowercase",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_lower"
    },
    "text_titlecase": {
        "display_name": "Title Case",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Converts text to title case",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_title"
    },
    "text_trim": {
        "display_name": "Trim Whitespace",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Removes leading and trailing whitespace",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_trimmed"
    },
    "text_extract_numbers": {
        "display_name": "Extract Numbers",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Extracts numbers from text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_numbers"
    },
    "text_extract_text": {
        "display_name": "Extract Text",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Extracts alphabetic text from string",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_text"
    },
    "text_reverse": {
        "display_name": "Reverse Text",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Reverses the text string",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_reversed"
    },
    "text_length": {
        "display_name": "Text Length",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Returns the length of the text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_length"
    },
    "text_hash_md5": {
        "display_name": "Hash (MD5)",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Creates an MD5 hash of the text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_md5"
    },
    "text_soundex": {
        "display_name": "Soundex Code",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Creates a Soundex code for phonetic matching",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_soundex"
    },

    # =========================================================================
    # MATH TRANSFORMATIONS
    # =========================================================================
    "math_round": {
        "display_name": "Round",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Rounds numbers to specified decimals",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "decimals": {"type": "int", "required": False, "default": 2, "label": "Decimals"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_rounded"
    },
    "math_ceil": {
        "display_name": "Ceiling",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Rounds up to the nearest integer",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_ceil"
    },
    "math_floor": {
        "display_name": "Floor",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Rounds down to the nearest integer",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_floor"
    },
    "math_abs": {
        "display_name": "Absolute Value",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Returns the absolute value",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_abs"
    },
    "math_sqrt": {
        "display_name": "Square Root",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates the square root",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_sqrt"
    },
    "math_square": {
        "display_name": "Square",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Squares the number",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_sq"
    },
    "math_log": {
        "display_name": "Logarithm (ln)",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates the natural logarithm",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_log"
    },
    "math_log10": {
        "display_name": "Logarithm (base 10)",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates the base-10 logarithm",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_log10"
    },
    "math_exp": {
        "display_name": "Exponential",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates e raised to the power",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_exp"
    },

    # =========================================================================
    # TRIGONOMETRIC TRANSFORMATIONS
    # =========================================================================
    "trig_sin": {
        "display_name": "Sine",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates sine (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_sin"
    },
    "trig_cos": {
        "display_name": "Cosine",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates cosine (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_cos"
    },
    "trig_tan": {
        "display_name": "Tangent",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates tangent (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_tan"
    },
    "trig_asin": {
        "display_name": "Arc Sine",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates arc sine (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_asin"
    },
    "trig_acos": {
        "display_name": "Arc Cosine",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates arc cosine (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_acos"
    },
    "trig_atan": {
        "display_name": "Arc Tangent",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates arc tangent (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_atan"
    },

    # =========================================================================
    # DATE/TIME TRANSFORMATIONS
    # =========================================================================
    "datetime_year": {
        "display_name": "Extract Year",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the year from a date",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_year"
    },
    "datetime_month": {
        "display_name": "Extract Month",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the month (1-12) from a date",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_month"
    },
    "datetime_day": {
        "display_name": "Extract Day",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the day of month from a date",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_day"
    },
    "datetime_hour": {
        "display_name": "Extract Hour",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the hour from a datetime",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Datetime Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_hour"
    },
    "datetime_minute": {
        "display_name": "Extract Minute",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the minute from a datetime",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Datetime Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_minute"
    },
    "datetime_second": {
        "display_name": "Extract Second",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the second from a datetime",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Datetime Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_second"
    },
    "datetime_weekday": {
        "display_name": "Extract Weekday",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the day of week (0=Monday, 6=Sunday)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_weekday"
    },
    "datetime_quarter": {
        "display_name": "Extract Quarter",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the quarter (1-4) from a date",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_quarter"
    },
    "datetime_age_days": {
        "display_name": "Age (Days)",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Calculates age in days from today",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_age_days"
    },
    "datetime_age_years": {
        "display_name": "Age (Years)",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Calculates age in years from today",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_age_years"
    },
    "datetime_is_weekend": {
        "display_name": "Is Weekend",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Returns True if date is Saturday or Sunday",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_is_weekend"
    },
    "datetime_is_leap_year": {
        "display_name": "Is Leap Year",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Returns True if year is a leap year",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_is_leap_year"
    },
    "datetime_days_in_month": {
        "display_name": "Days in Month",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Returns the number of days in the month",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_days_in_month"
    },

    # =========================================================================
    # STATISTICAL TRANSFORMATIONS
    # =========================================================================
    "stat_zscore": {
        "display_name": "Z-Score",
        "type": TransformationStepType.STAT_ADD_GROUP,
        "category": "statistics",
        "description": "Calculates the z-score (standard score)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_zscore"
    },
    "stat_percent_rank": {
        "display_name": "Percent Rank",
        "type": TransformationStepType.CALCULATE,
        "category": "statistics",
        "description": "Calculates the percent rank within the column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_pct_rank"
    },
    "stat_rank": {
        "display_name": "Rank",
        "type": TransformationStepType.CALCULATE,
        "category": "statistics",
        "description": "Calculates the rank within the column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_rank"
    },

    # =========================================================================
    # FINANCIAL OPERATIONS
    # =========================================================================
    "financial_ratios": {
        "display_name": "Financial Ratios",
        "type": TransformationStepType.CALCULATE,
        "category": "financial",
        "description": "Calculate standard financial ratios (Liquidity, Solvency, Profitability)",
        "parameter_schema": {
            "mapping": {"type": "dict", "label": "Column Mapping"},
            "ratios": {"type": "list", "label": "Selected Ratios"}
        },
        "creates_columns": True
    },
    
    # IFRS 9 OPERATIONS
    "ifrs9_staging": {
        "display_name": "IFRS 9 Staging",
        "type": TransformationStepType.CALCULATE,
        "category": "financial",
        "description": "Classify loans into Stages 1, 2, 3 based on DPD and calculate ECL",
        "parameter_schema": {
            "mapping": {"type": "dict", "label": "Column Mapping"},
            "thresholds": {"type": "dict", "label": "Staging Thresholds"}
        },
        "creates_columns": True
    },

    # =========================================================================
    # SOX OPERATIONS
    # =========================================================================
    "sox_sod_analysis": {
        "display_name": "SOX SoD Analysis",
        "type": TransformationStepType.AUDIT_FLAG,
        "category": "audit",
        "description": "Scan transaction logs for Segregation of Duties conflicts",
        "parameter_schema": {
            "user_column": {"type": "column", "label": "User ID Column"},
            "action_column": {"type": "column", "label": "Action/Role Column"},
            "conflicts": {"type": "list", "label": "Conflict Rules"}
        },
        "creates_columns": ["sod_conflict_found", "sod_conflict_detail"],
        "requires_specific_dialog": True
    },

    # =========================================================================
    # COSO OPERATIONS
    # =========================================================================
    "coso_risk_heatmap": {
        "display_name": "COSO Risk Heatmap",
        "type": TransformationStepType.AGGREGATE,
        "category": "audit",
        "description": "Aggregate risk scores by COSO components",
        "parameter_schema": {
            "category_column": {"type": "column", "label": "Category Column"},
            "risk_score_column": {"type": "column", "label": "Risk Score Column"},
            "mapping": {"type": "dict", "label": "Mapping"}
        },
        "creates_columns": False, # Creates summary table
        "requires_specific_dialog": True
    },

    # =========================================================================
    # COLUMN OPERATIONS
    # =========================================================================
    "column_rename": {
        "display_name": "Rename Column",
        "type": TransformationStepType.CALCULATE,
        "category": "column",
        "description": "Renames a column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "new_name": {"type": "string", "required": True, "label": "New Name"}
        },
        "creates_columns": []
    },

    # =========================================================================
    # SPLIT OPERATIONS
    # =========================================================================
    "split_comma": {
        "display_name": "Split by Comma",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by comma",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{column}_part0", "{column}_part1"]
    },
    "split_space": {
        "display_name": "Split by Space",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by space",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{column}_part0", "{column}_part1"]
    },
    "split_semicolon": {
        "display_name": "Split by Semicolon",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by semicolon",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{column}_part0", "{column}_part1"]
    },
    "split_pipe": {
        "display_name": "Split by Pipe",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by pipe",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{column}_part0", "{column}_part1"]
    },
    "split_custom": {
        "display_name": "Split by Custom Character",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by custom delimiter",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "delimiter": {"type": "string", "required": True, "label": "Delimiter"}
        },
        "creates_columns": ["{column}_part0", "{column}_part1"]
    },

    # =========================================================================
    # PIVOT/UNPIVOT OPERATIONS
    # =========================================================================
    "pivot_table": {
        "display_name": "Pivot Table",
        "type": TransformationStepType.PIVOT,
        "category": "pivot",
        "description": "Creates a pivot table",
        "parameter_schema": {
            "index": {"type": "column", "required": True, "label": "Index Column"},
            "columns": {"type": "column", "required": True, "label": "Column to Pivot"},
            "values": {"type": "column", "required": True, "label": "Values Column"},
            "aggregate_function": {"type": "string", "required": False, "default": "sum",
                                  "options": ["sum", "mean", "min", "max", "count"], "label": "Aggregate Function"}
        },
        "creates_columns": []
    },
    "unpivot_table": {
        "display_name": "Unpivot (Melt)",
        "type": TransformationStepType.UNPIVOT,
        "category": "pivot",
        "description": "Transforms columns into rows",
        "parameter_schema": {
            "id_vars": {"type": "list[column]", "required": True, "label": "ID Columns"},
            "value_vars": {"type": "list[column]", "required": False, "label": "Value Columns"},
            "var_name": {"type": "string", "required": False, "default": "variable", "label": "Variable Name"},
            "value_name": {"type": "string", "required": False, "default": "value", "label": "Value Name"}
        },
        "creates_columns": []
    },

    # =========================================================================
    # ML OPERATIONS
    # =========================================================================
    "ml_anomaly_iforest": {
        "display_name": "Anomaly Detection (Isolation Forest)",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Detects anomalies using Isolation Forest algorithm",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "contamination": {"type": "float", "required": False, "default": 0.1, "label": "Contamination"}
        },
        "creates_columns": ["{column}_is_anomaly", "{column}_anomaly_score"]
    },
    "ml_anomaly_zscore": {
        "display_name": "Anomaly Detection (Z-Score)",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Detects anomalies using Z-Score method",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "threshold": {"type": "float", "required": False, "default": 3.0, "label": "Threshold (std devs)"}
        },
        "creates_columns": ["{column}_is_outlier", "{column}_zscore"]
    },
    "ml_anomaly_iqr": {
        "display_name": "Anomaly Detection (IQR)",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Detects anomalies using Interquartile Range method",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "multiplier": {"type": "float", "required": False, "default": 1.5, "label": "IQR Multiplier"}
        },
        "creates_columns": ["{column}_is_outlier", "{column}_iqr_distance"]
    },
    "ml_anomaly_lof": {
        "display_name": "Anomaly Detection (Local Outlier Factor)",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Detects anomalies using Local Outlier Factor",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "n_neighbors": {"type": "int", "required": False, "default": 20, "label": "Number of Neighbors"}
        },
        "creates_columns": ["{column}_is_outlier", "{column}_lof_score"]
    },
    "ml_outlier": {
        "display_name": "Outlier Detection",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Detects statistical outliers",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "method": {"type": "string", "required": False, "default": "iqr",
                      "options": ["iqr", "zscore"], "label": "Method"}
        },
        "creates_columns": ["{column}_is_outlier", "{column}_outlier_score"]
    },
    "ml_cluster": {
        "display_name": "K-Means Clustering",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Performs K-Means clustering",
        "parameter_schema": {
            "columns": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "n_clusters": {"type": "int", "required": False, "default": 3, "label": "Number of Clusters"}
        },
        "creates_columns": ["cluster"]
    },
    "ml_forecast": {
        "display_name": "Time Series Forecast",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Forecasts future values using exponential smoothing",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Value Column"},
            "periods": {"type": "int", "required": False, "default": 12, "label": "Periods to Forecast"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_forecast"
    },

    # =========================================================================
    # ML TRAINING OPERATIONS
    # =========================================================================
    "ml_train": {
        "display_name": "Train ML Model",
        "type": TransformationStepType.ML_TRAIN,
        "category": "ml",
        "description": "Train a machine learning model for later use in predictions",
        "parameter_schema": {
            "model_name": {"type": "string", "required": True, "label": "Model Name"},
            "algorithm": {"type": "string", "required": True, "options": ["random_forest", "logistic_regression", "svm", "gradient_boosting", "neural_network"], "label": "Algorithm"},
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "test_split": {"type": "float", "required": False, "default": 0.2, "label": "Test Split Ratio"},
            "random_seed": {"type": "int", "required": False, "default": 42, "label": "Random Seed"}
        },
        "creates_columns": False  # This operation saves a model, doesn't create columns
    },

    # =========================================================================
    # AUDIT OPERATIONS
    # =========================================================================
    "audit_benford_law": {
        "display_name": "Benford's Law Analysis",
        "type": TransformationStepType.AUDIT_FLAG,
        "category": "audit",
        "description": "Analyzes first digits for conformity with Benford's Law",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column to Analyze"}
        },
        "creates_columns": ["{column}_benford_deviation", "{column}_is_suspicious"]
    },

    # =========================================================================
    # AI OPERATIONS
    # =========================================================================
    "ai_explain": {
        "display_name": "Explain Column with AI",
        "type": TransformationStepType.AI_ENRICH,
        "category": "ai",
        "description": "Generates AI explanations for column values",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "style": {"type": "string", "required": False, "default": "concise",
                     "options": ["concise", "detailed"], "label": "Explanation Style"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_ai_explanation"
    },
    "ai_sentiment": {
        "display_name": "Sentiment Analysis",
        "type": TransformationStepType.AI_ENRICH,
        "category": "ai",
        "description": "Analyzes text sentiment",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Text Column"}
        },
        "creates_columns": ["{column}_sentiment_score", "{column}_sentiment_label"]
    },
    "ai_extract": {
        "display_name": "Extract Entities",
        "type": TransformationStepType.AI_EXTRACT,
        "category": "ai",
        "description": "Extracts entities from text using AI",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Text Column"},
            "entity_type": {"type": "string", "required": True,
                           "options": ["email", "phone", "date", "money"], "label": "Entity Type"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_extracted"
    },
    "ai_pattern_learn": {
        "display_name": "Pattern Learning (Flash Fill)",
        "type": TransformationStepType.AI_PATTERN_LEARN,
        "category": "ai",
        "description": "Learns patterns from examples and applies to all rows",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Source Column"},
            "output_column": {"type": "string", "required": True, "label": "Output Column"}
        },
        "creates_columns": ["{output_column}"]
    },

    # =========================================================================
    # STATISTICS OPERATIONS
    # =========================================================================
    "stat_quick_stats": {
        "display_name": "Quick Stats",
        "type": TransformationStepType.STAT_ADD_GROUP,
        "category": "statistics",
        "description": "Calculates quick column statistics",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{column}_min", "{column}_max", "{column}_mean", "{column}_std"]
    },
    "stat_group_stats": {
        "display_name": "Add Group Statistics",
        "type": TransformationStepType.STAT_ADD_GROUP,
        "category": "statistics",
        "description": "Adds aggregate statistics as new columns per group",
        "parameter_schema": {
            "group_column": {"type": "column", "required": True, "label": "Group By Column"},
            "target_column": {"type": "column", "required": True, "label": "Target Column"},
            "calculations": {"type": "list[str]", "required": False,
                           "options": ["mean", "std", "min", "max", "sum", "count"],
                           "default": ["mean", "std"], "label": "Calculations"}
        },
        "creates_columns": ["{target_column}_mean", "{target_column}_std"]
    },

    # =========================================================================
    # ML CLASSIFICATION & PREDICTION OPERATIONS
    # =========================================================================
    "ml_classify": {
        "display_name": "ML Classification",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Classifies data using a supervised ML model",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column (Labels)"},
            "model_id": {"type": "string", "required": False, "label": "Model ID"},
            "output_column": {"type": "string", "required": False, "default": "predicted_class", "label": "Output Column"},
            "probability_column": {"type": "string", "required": False, "default": "probability", "label": "Probability Column"}
        },
        "creates_columns": ["{output_column}", "{probability_column}"]
    },
    "ml_risk_score": {
        "display_name": "ML Risk Score",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Calculates risk scores per group based on features",
        "parameter_schema": {
            "group_column": {"type": "column", "required": True, "label": "Group Column"},
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "output_column": {"type": "string", "required": False, "default": "risk_score", "label": "Output Column"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_predict": {
        "display_name": "ML Predict",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Applies a trained model to predict new values",
        "parameter_schema": {
            "model_id": {"type": "string", "required": True, "label": "Model ID"},
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "output_column": {"type": "string", "required": False, "default": "predicted", "label": "Output Column"}
        },
        "creates_columns": ["{output_column}"]
    },

    # =========================================================================
    # SUPERVISED LEARNING - REGRESSION
    # =========================================================================
    "ml_linear_regression": {
        "display_name": "Linear Regression",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Predicts continuous values using linear regression",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "output_column": {"type": "string", "required": False, "default": "y_hat", "label": "Prediction Column"},
            "fit_intercept": {"type": "bool", "required": False, "default": True, "label": "Fit Intercept"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_glm": {
        "display_name": "GLM Regression",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Generalized Linear Models (Gaussian, Binomial, Poisson, Gamma)",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "output_column": {"type": "string", "required": False, "default": "y_hat", "label": "Prediction Column"},
            "family": {"type": "string", "required": False, "default": "gaussian", "label": "Family",
                       "options": ["gaussian", "binomial", "poisson", "gamma"]}
        },
        "creates_columns": ["{output_column}"]
    },

    # =========================================================================
    # SUPERVISED LEARNING - TREE-BASED
    # =========================================================================
    "ml_decision_tree": {
        "display_name": "Decision Tree",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Classification/regression using decision tree",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "output_column": {"type": "string", "required": False, "default": "prediction", "label": "Prediction Column"},
            "max_depth": {"type": "int", "required": False, "default": 10, "label": "Max Depth"},
            "min_samples_split": {"type": "int", "required": False, "default": 2, "label": "Min Samples Split"},
            "min_samples_leaf": {"type": "int", "required": False, "default": 1, "label": "Min Samples Leaf"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_random_forest": {
        "display_name": "Random Forest",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Ensemble learning with multiple decision trees",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "output_column": {"type": "string", "required": False, "default": "prediction", "label": "Prediction Column"},
            "n_estimators": {"type": "int", "required": False, "default": 100, "label": "Number of Trees"},
            "max_depth": {"type": "int", "required": False, "default": 10, "label": "Max Depth"},
            "min_samples_split": {"type": "int", "required": False, "default": 2, "label": "Min Samples Split"},
            "min_samples_leaf": {"type": "int", "required": False, "default": 1, "label": "Min Samples Leaf"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_gradient_boosting": {
        "display_name": "Gradient Boosting",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Sequential ensemble using gradient boosting",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "output_column": {"type": "string", "required": False, "default": "prediction", "label": "Prediction Column"},
            "n_estimators": {"type": "int", "required": False, "default": 100, "label": "Number of Estimators"},
            "learning_rate": {"type": "float", "required": False, "default": 0.1, "label": "Learning Rate"},
            "max_depth": {"type": "int", "required": False, "default": 5, "label": "Max Depth"},
            "min_samples_split": {"type": "int", "required": False, "default": 2, "label": "Min Samples Split"},
            "min_samples_leaf": {"type": "int", "required": False, "default": 1, "label": "Min Samples Leaf"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_xgboost": {
        "display_name": "XGBoost",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Extreme Gradient Boosting for high performance",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "output_column": {"type": "string", "required": False, "default": "prediction", "label": "Prediction Column"},
            "n_estimators": {"type": "int", "required": False, "default": 100, "label": "Number of Trees"},
            "learning_rate": {"type": "float", "required": False, "default": 0.1, "label": "Learning Rate"},
            "max_depth": {"type": "int", "required": False, "default": 6, "label": "Max Depth"},
            "subsample": {"type": "float", "required": False, "default": 0.8, "label": "Subsample"},
            "colsample_bytree": {"type": "float", "required": False, "default": 0.8, "label": "Column Sample by Tree"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_lightgbm": {
        "display_name": "LightGBM",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Light Gradient Boosting Machine - fast on large datasets",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "target": {"type": "column", "required": True, "label": "Target Column"},
            "output_column": {"type": "string", "required": False, "default": "prediction", "label": "Prediction Column"},
            "n_estimators": {"type": "int", "required": False, "default": 100, "label": "Number of Leaves"},
            "learning_rate": {"type": "float", "required": False, "default": 0.1, "label": "Learning Rate"},
            "num_leaves": {"type": "int", "required": False, "default": 31, "label": "Number of Leaves"},
            "min_child_samples": {"type": "int", "required": False, "default": 20, "label": "Min Child Samples"}
        },
        "creates_columns": ["{output_column}"]
    },

    # =========================================================================
    # UNSUPERVISED LEARNING - CLUSTERING
    # =========================================================================
    "ml_dbscan": {
        "display_name": "DBSCAN Clustering",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Density-based spatial clustering",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "output_column": {"type": "string", "required": False, "default": "cluster", "label": "Cluster Column"},
            "eps": {"type": "float", "required": False, "default": 0.5, "label": "Epsilon (neighborhood)"},
            "min_samples": {"type": "int", "required": False, "default": 5, "label": "Min Samples"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_gmm": {
        "display_name": "Gaussian Mixture",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Probabilistic clustering with Gaussian mixtures",
        "parameter_schema": {
            "features": {"type": "list[column]", "required": True, "label": "Feature Columns"},
            "output_column": {"type": "string", "required": False, "default": "cluster", "label": "Cluster Column"},
            "n_components": {"type": "int", "required": False, "default": 3, "label": "Number of Components"}
        },
        "creates_columns": ["{output_column}"]
    },

    # =========================================================================
    # TIME SERIES (Statsmodels)
    # =========================================================================
    "ml_arima": {
        "display_name": "ARIMA Forecast",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Time series forecasting with ARIMA",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Value Column"},
            "output_column": {"type": "string", "required": False, "default": "forecast", "label": "Forecast Column"},
            "order_p": {"type": "int", "required": False, "default": 1, "label": "AR Order (p)"},
            "order_d": {"type": "int", "required": False, "default": 1, "label": "Differencing (d)"},
            "order_q": {"type": "int", "required": False, "default": 1, "label": "MA Order (q)"},
            "steps": {"type": "int", "required": False, "default": 12, "label": "Forecast Steps"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ml_ets": {
        "display_name": "Exponential Smoothing",
        "type": TransformationStepType.ML_PREDICT,
        "category": "ml",
        "description": "Exponential smoothing state space models",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Value Column"},
            "output_column": {"type": "string", "required": False, "default": "forecast", "label": "Forecast Column"},
            "trend": {"type": "string", "required": False, "default": "add", "label": "Trend",
                      "options": ["add", "mul", None]},
            "seasonal": {"type": "string", "required": False, "default": None, "label": "Seasonal",
                        "options": ["add", "mul", None]},
            "steps": {"type": "int", "required": False, "default": 12, "label": "Forecast Steps"}
        },
        "creates_columns": ["{output_column}"]
    },

    # =========================================================================
    # AI OPERATIONS (Enrichment & Classification)
    # =========================================================================
    "ai_classify": {
        "display_name": "AI Text Classification",
        "type": TransformationStepType.AI_ENRICH,
        "category": "ai",
        "description": "Classifies text into categories using AI",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Text Column"},
            "categories": {"type": "list[str]", "required": True, "label": "Categories"},
            "output_column": {"type": "string", "required": False, "default": "ai_category", "label": "Category Column"},
            "confidence_column": {"type": "string", "required": False, "default": "ai_confidence", "label": "Confidence Column"}
        },
        "creates_columns": ["{output_column}", "{confidence_column}"]
    },
    "ai_summarize": {
        "display_name": "AI Summarize",
        "type": TransformationStepType.AI_ENRICH,
        "category": "ai",
        "description": "Generates AI summaries for text content",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Text Column"},
            "max_length": {"type": "int", "required": False, "default": 100, "label": "Max Length"},
            "output_column": {"type": "string", "required": False, "default": "summary", "label": "Output Column"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ai_enrich": {
        "display_name": "AI Enrich",
        "type": TransformationStepType.AI_ENRICH,
        "category": "ai",
        "description": "Enriches data with AI-generated information",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Source Column"},
            "enrichment_type": {"type": "string", "required": True,
                               "options": ["industry", "sentiment", "category", "entity"],
                               "label": "Enrichment Type"},
            "output_column": {"type": "string", "required": False, "default": "enriched", "label": "Output Column"}
        },
        "creates_columns": ["{output_column}"]
    },
    "ai_generate_column": {
        "display_name": "AI Generate Column",
        "type": TransformationStepType.AI_EXTRACT,
        "category": "ai",
        "description": "Generates a new column using AI",
        "parameter_schema": {
            "column_name": {"type": "string", "required": True, "label": "Column Name"},
            "instruction": {"type": "string", "required": True, "label": "Instruction"},
            "generated_code": {"type": "string", "required": True, "label": "Generated Code"}
        },
        "creates_columns": ["{column_name}"]
    },

    # =========================================================================
    # AUDIT OPERATIONS (Duplicate, Gap, Outlier Detection)
    # =========================================================================
    "audit_duplicate_detection": {
        "display_name": "Duplicate Detection",
        "type": TransformationStepType.AUDIT_FLAG,
        "category": "audit",
        "description": "Detects duplicate rows based on specified columns",
        "parameter_schema": {
            "columns": {"type": "list[column]", "required": True, "label": "Columns to Check"},
            "output_column": {"type": "string", "required": False, "default": "duplicate_group_id", "label": "Group ID Column"},
            "flag_column": {"type": "string", "required": False, "default": "is_duplicate", "label": "Flag Column"}
        },
        "creates_columns": ["{output_column}", "{flag_column}"]
    },
    "audit_gap_analysis": {
        "display_name": "Gap Analysis",
        "type": TransformationStepType.AUDIT_FLAG,
        "category": "audit",
        "description": "Detects missing values in sequential ID columns",
        "parameter_schema": {
            "id_column": {"type": "column", "required": True, "label": "ID Column"},
            "output_column": {"type": "string", "required": False, "default": "is_missing_sequence", "label": "Missing Flag Column"},
            "missing_count_column": {"type": "string", "required": "False", "default": "gaps_after_this", "label": "Gap Count Column"}
        },
        "creates_columns": ["{output_column}", "{missing_count_column}"]
    },
    "audit_outlier_detection": {
        "display_name": "Audit Outlier Detection",
        "type": TransformationStepType.AUDIT_FLAG,
        "category": "audit",
        "description": "Detects statistical outliers for audit purposes",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "method": {"type": "string", "required": False, "default": "iqr",
                      "options": ["iqr", "zscore", "mad"], "label": "Method"},
            "output_column": {"type": "string", "required": False, "default": "is_outlier", "label": "Flag Column"},
            "deviation_column": {"type": "string", "required": False, "default": "outlier_deviation", "label": "Deviation Column"}
        },
        "creates_columns": ["{output_column}", "{deviation_column}"]
    },
    "audit_round_numbers": {
        "display_name": "Round Number Detection",
        "type": TransformationStepType.AUDIT_FLAG,
        "category": "audit",
        "description": "Flags unusually round numbers (potential manipulation)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "threshold": {"type": "float", "required": False, "default": 0.9, "label": "Roundness Threshold"},
            "output_column": {"type": "string", "required": False, "default": "is_round_number", "label": "Flag Column"},
            "score_column": {"type": "string", "required": False, "default": "roundness_score", "label": "Score Column"}
        },
        "creates_columns": ["{output_column}", "{score_column}"]
    },

    # =========================================================================
    # STATISTICS ADD GROUP OPERATIONS
    # =========================================================================
    "stat_add_group_stats": {
        "display_name": "Add Group Statistics",
        "type": TransformationStepType.STAT_ADD_GROUP,
        "category": "statistics",
        "description": "Adds aggregate statistics as columns (mean, std, zscore, etc.)",
        "parameter_schema": {
            "group_column": {"type": "column", "required": True, "label": "Group By Column"},
            "target_column": {"type": "column", "required": True, "label": "Target Column"},
            "calculations": {"type": "list[str]", "required": False,
                           "options": ["mean", "std", "min", "max", "sum", "count", "zscore"],
                           "default": ["mean", "std"], "label": "Calculations"}
        },
        "creates_columns": ["{target_column}_mean_by_{group}", "{target_column}_std_by_{group}"]
    },

    # =========================================================================
    # TEXT EXTRACTION OPERATIONS (Excel LEFT/RIGHT/MID style)
    # =========================================================================
    "text_extract_first": {
        "display_name": "Extract First N Characters",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Extracts the first N characters from text (Excel LEFT function)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "num_chars": {"type": "int", "required": False, "default": 1, "label": "Number of Characters"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_left"
    },
    "text_extract_last": {
        "display_name": "Extract Last N Characters",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Extracts the last N characters from text (Excel RIGHT function)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "num_chars": {"type": "int", "required": False, "default": 1, "label": "Number of Characters"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_right"
    },
    "text_extract_middle": {
        "display_name": "Extract Middle Characters",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Extracts characters from the middle of text (Excel MID function)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "start_pos": {"type": "int", "required": False, "default": 1, "label": "Start Position (1-indexed)"},
            "num_chars": {"type": "int", "required": False, "default": 1, "label": "Number of Characters"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_mid"
    },

    # =========================================================================
    # MATH OPERATIONS - MODULO & POWER
    # =========================================================================
    "math_modulo": {
        "display_name": "Modulo (Remainder)",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates the remainder after division",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "divisor": {"type": "int", "required": True, "label": "Divisor"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_mod"
    },
    "math_power": {
        "display_name": "Raise to Power",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Raises the value to a specified power",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "exponent": {"type": "int", "required": True, "label": "Exponent"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_power"
    },

    # =========================================================================
    # PREFIX/SUFFIX OPERATIONS
    # =========================================================================
    "text_add_prefix": {
        "display_name": "Add Prefix",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Adds a prefix to the beginning of text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "prefix": {"type": "string", "required": True, "label": "Prefix Text"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_prefixed"
    },
    "text_add_suffix": {
        "display_name": "Add Suffix",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Adds a suffix to the end of text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "suffix": {"type": "string", "required": True, "label": "Suffix Text"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_suffixed"
    },

    # =========================================================================
    # REPLACE VALUES OPERATION
    # =========================================================================
    "replace_values": {
        "display_name": "Find and Replace",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Finds and replaces values in a column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "find_value": {"type": "string", "required": True, "label": "Find"},
            "replace_value": {"type": "string", "required": True, "label": "Replace With"},
            "case_sensitive": {"type": "bool", "required": False, "default": True, "label": "Case Sensitive"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_replaced"
    },

    # =========================================================================
    # STANDARDIZATION OPERATIONS
    # =========================================================================
    "standardize_minmax": {
        "display_name": "Min-Max Normalization",
        "type": TransformationStepType.CALCULATE,
        "category": "statistics",
        "description": "Scales values to range 0-1 using min-max normalization",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": True,
        "column_naming_pattern": "{column}_minmax"
    },

    # =========================================================================
    # NEW: FUNCTIONS THAT CREATE COLUMNS OR TABLES
    # =========================================================================

    # -------------------------------------------------------------------------
    # SPLIT COLUMNS BY DELIMITER
    # -------------------------------------------------------------------------
    "split_columns_by_delimiter": {
        "display_name": "Split Columns by Delimiters",
        "type": TransformationStepType.CALCULATE,
        "category": "column",
        "description": "Splits a column into multiple columns at a specified delimiter",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column to Split"},
            "delimiter": {"type": "string", "required": False, "default": " ", "label": "Delimiter",
                         "options": ["space", "comma", "tab", "period", "asterisk", "custom"]},
            "custom_delimiter": {"type": "string", "required": False, "label": "Custom Delimiter"},
            "max_splits": {"type": "int", "required": False, "default": -1, "label": "Max Splits (-1 for all)"}
        },
        "creates_columns": ["{column}_1", "{column}_2", "{column}_3"]
    },

    # -------------------------------------------------------------------------
    # CUSTOM COLUMN FROM MATH
    # -------------------------------------------------------------------------
    "custom_column_from_math": {
        "display_name": "Custom Column from Math",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Creates a custom column using mathematical operations",
        "parameter_schema": {
            "expression": {"type": "string", "required": True, "label": "Expression",
                          "placeholder": "e.g., col('A') + col('B') * 2"},
            "output_column": {"type": "string", "required": False, "default": "custom_result", "label": "Output Column"},
            "columns": {"type": "list[column]", "required": True, "label": "Columns to Use"}
        },
        "creates_columns": ["{output_column}"]
    },

    # -------------------------------------------------------------------------
    # SPLIT SHEET (Creates new tables based on unique values)
    # -------------------------------------------------------------------------
    "split_sheet": {
        "display_name": "Split Sheet",
        "type": TransformationStepType.FILTER,
        "category": "table",
        "description": "Splits the dataset into multiple tables based on unique values in a column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column to Group By"},
            "output_type": {"type": "string", "required": False, "default": "separate_tables",
                           "options": ["separate_tables", "filter_column"], "label": "Output Type"},
            "filter_value": {"type": "string", "required": False, "label": "Filter Value (for single output)"}
        },
        "creates_columns": False  # Creates new dataset/filter, not columns
    },

    # -------------------------------------------------------------------------
    # CALCULATED COLUMNS (Formula-based)
    # -------------------------------------------------------------------------
    "calculated_columns": {
        "display_name": "Calculated Columns",
        "type": TransformationStepType.CALCULATE,
        "category": "column",
        "description": "Creates new columns using formulas or expressions",
        "parameter_schema": {
            "formula": {"type": "string", "required": True, "label": "Formula",
                       "placeholder": "e.g., col('A') > col('B')"},
            "output_column": {"type": "string", "required": True, "label": "Output Column"},
            "formula_type": {"type": "string", "required": False, "default": "arithmetic",
                            "options": ["arithmetic", "conditional", "comparison", "logical"], "label": "Formula Type"}
        },
        "creates_columns": ["{output_column}"]
    },

    # -------------------------------------------------------------------------
    # CHOOSE COLUMNS (Select, Remove, Reorder)
    # -------------------------------------------------------------------------
    "choose_columns": {
        "display_name": "Choose Columns",
        "type": TransformationStepType.CALCULATE,
        "category": "column",
        "description": "Selects, removes, and reorders columns in the dataset",
        "parameter_schema": {
            "action": {"type": "string", "required": True, "options": ["keep", "remove", "reorder"], "label": "Action"},
            "columns_to_keep": {"type": "list[column]", "required": False, "label": "Columns to Keep"},
            "columns_to_remove": {"type": "list[column]", "required": False, "label": "Columns to Remove"},
            "column_order": {"type": "list[column]", "required": False, "label": "New Column Order"}
        },
        "creates_columns": False  # Modifies structure, returns same columns
    },

    # -------------------------------------------------------------------------
    # CHANGE DATA TYPE (Extended types)
    # -------------------------------------------------------------------------
    "change_dtype": {
        "display_name": "Change Data Type",
        "type": TransformationStepType.CALCULATE,
        "category": "column",
        "description": "Converts column data types to ensure compatibility with operations",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "new_dtype": {"type": "string", "required": True, "label": "New Type",
                         "options": ["Int8", "Int16", "Int32", "Int64", "Float32", "Float64",
                                    "Utf8", "Boolean", "Date", "Datetime", "Categorical"]},
            "format_string": {"type": "string", "required": False, "label": "Format (for dates)"}
        },
        "creates_columns": []
    },

    # -------------------------------------------------------------------------
    # RENAME COLUMNS (Bulk rename)
    # -------------------------------------------------------------------------
    "rename_columns": {
        "display_name": "Rename Columns",
        "type": TransformationStepType.CALCULATE,
        "category": "column",
        "description": "Renames one or more columns to improve clarity",
        "parameter_schema": {
            "renames": {"type": "list[dict]", "required": True, "label": "Renames",
                       "schema": [{"old_name": "string", "new_name": "string"}]},
            "prefix": {"type": "string", "required": False, "label": "Add Prefix"},
            "suffix": {"type": "string", "required": False, "label": "Add Suffix"},
            "lowercase": {"type": "bool", "required": False, "default": False, "label": "Convert to lowercase"},
            "uppercase": {"type": "bool", "required": False, "default": False, "label": "Convert to uppercase"}
        },
        "creates_columns": []
    },

    # -------------------------------------------------------------------------
    # SPLIT ALPHANUMERIC
    # -------------------------------------------------------------------------
    "split_alphanumeric": {
        "display_name": "Split Alphanumeric",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Separates alphanumeric values into text and numeric components",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "output_text": {"type": "string", "required": False, "default": "{column}_text", "label": "Text Output Column"},
            "output_number": {"type": "string", "required": False, "default": "{column}_number", "label": "Number Output Column"}
        },
        "creates_columns": ["{output_text}", "{output_number}"]
    },

    # -------------------------------------------------------------------------
    # SELECT N ROWS
    # -------------------------------------------------------------------------
    "select_n_rows": {
        "display_name": "Select N Rows",
        "type": TransformationStepType.FILTER,
        "category": "table",
        "description": "Creates a new table with a specified number of rows",
        "parameter_schema": {
            "selection_type": {"type": "string", "required": True, "label": "Selection Type",
                              "options": ["first", "last", "random", "every_nth"]},
            "n": {"type": "int", "required": True, "label": "Number of Rows"},
            "random_seed": {"type": "int", "required": False, "label": "Random Seed (for random)"},
            "step": {"type": "int", "required": False, "default": 1, "label": "Step (for every_nth)"}
        },
        "creates_columns": False  # Returns subset of rows
    },

    # -------------------------------------------------------------------------
    # TRANSPOSE (Rows to Columns)
    # -------------------------------------------------------------------------
    "transpose": {
        "display_name": "Transpose",
        "type": TransformationStepType.CALCULATE,
        "category": "table",
        "description": "Swaps rows and columns to convert column headers into row values",
        "parameter_schema": {
            "columns_to_transpose": {"type": "list[column]", "required": True, "label": "Columns to Transpose"},
            "include_index": {"type": "bool", "required": False, "default": True, "label": "Include Index Column"},
            "index_column": {"type": "string", "required": False, "default": "index", "label": "Index Column Name"}
        },
        "creates_columns": False  # Creates transposed table
    },

    # -------------------------------------------------------------------------
    # PROMOTE ROW AS HEADER
    # -------------------------------------------------------------------------
    "promote_row_header": {
        "display_name": "Use First Row as Headers",
        "type": TransformationStepType.CALCULATE,
        "category": "table",
        "description": "Promotes the first row to become column headers (removes that row from data)",
        "parameter_schema": {
            "row_index": {"type": "int", "required": False, "default": 0, "label": "Row Number to Use as Header", "min": 0}
        },
        "creates_columns": False  # Renames columns
    },

    # -------------------------------------------------------------------------
    # REMOVE ROWS
    # -------------------------------------------------------------------------
    "remove_rows": {
        "display_name": "Remove Rows",
        "type": TransformationStepType.FILTER,
        "category": "table",
        "description": "Remove or keep specific rows by their row numbers",
        "parameter_schema": {
            "row_indices": {"type": "list[int]", "required": True, "label": "Row Indices (0-based)", "placeholder": "e.g., 0, 1, 5"},
            "remove": {"type": "bool", "required": False, "default": True, "label": "Remove These Rows (uncheck to Keep Only)"}
        },
        "creates_columns": False  # Filters rows
    },

    # -------------------------------------------------------------------------
    # FILTER ROWS
    # -------------------------------------------------------------------------
    "filter_rows": {
        "display_name": "Filter Rows",
        "type": TransformationStepType.FILTER,
        "category": "table",
        "description": "Filter rows based on a column value",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "operator": {"type": "string", "required": True, "label": "Operator",
                        "options": ["==", "!=", ">", "<", ">=", "<=", "contains", "starts_with", "ends_with", "is_null", "is_not_null"]},
            "value": {"type": "string", "required": False, "label": "Value"}
        },
        "creates_columns": False  # Filters rows
    },

    # -------------------------------------------------------------------------
    # COMBINE WORKSHEETS (Union/Append)
    # -------------------------------------------------------------------------
    "combine_sheets": {
        "display_name": "Combine Worksheets",
        "type": TransformationStepType.JOIN,
        "category": "table",
        "description": "Creates a unified dataset by appending multiple worksheets",
        "parameter_schema": {
            "source_datasets": {"type": "list[str]", "required": True, "label": "Source Datasets"},
            "align_columns": {"type": "bool", "required": False, "default": True, "label": "Auto-align Columns"},
            "fill_missing": {"type": "bool", "required": False, "default": False, "label": "Fill Missing with Null"}
        },
        "creates_columns": False  # Combines datasets
    },

    # -------------------------------------------------------------------------
    # QUERY SHEET (Filter/Transform with formulas)
    # -------------------------------------------------------------------------
    "query_sheet": {
        "display_name": "Query Sheet",
        "type": TransformationStepType.FILTER,
        "category": "table",
        "description": "Creates a new filtered or transformed table using formulas",
        "parameter_schema": {
            "condition": {"type": "string", "required": True, "label": "Filter Condition",
                         "placeholder": "e.g., col('Amount') > 1000"},
            "sort_by": {"type": "list[column]", "required": False, "label": "Sort By"},
            "sort_order": {"type": "string", "required": False, "default": "asc",
                          "options": ["asc", "desc"], "label": "Sort Order"},
            "select_columns": {"type": "list[column]", "required": False, "label": "Select Columns (leave empty for all)"}
        },
        "creates_columns": False  # Creates filtered view
    },

    # =========================================================================
    # NEW: FUNCTIONS THAT CREATE SUMMARY REPORTS
    # =========================================================================

    # -------------------------------------------------------------------------
    # GROUP SUMMARY
    # -------------------------------------------------------------------------
    "group_summary": {
        "display_name": "Group Summary",
        "type": TransformationStepType.AGGREGATE,
        "category": "statistics",
        "description": "Creates aggregated summary reports by grouping data",
        "parameter_schema": {
            "group_columns": {"type": "list[column]", "required": True, "label": "Group By Columns"},
            "value_column": {"type": "column", "required": True, "label": "Value Column"},
            "aggregations": {"type": "list[str]", "required": False,
                            "options": ["sum", "mean", "count", "min", "max", "std", "median", "first", "last"],
                            "default": ["sum", "count"], "label": "Aggregations"}
        },
        "creates_columns": False  # Creates summary table
    },

    # -------------------------------------------------------------------------
    # TOP/BOTTOM ITEMS
    # -------------------------------------------------------------------------
    "top_bottom": {
        "display_name": "Top/Bottom Items",
        "type": TransformationStepType.FILTER,
        "category": "statistics",
        "description": "Shows ranked top or bottom N records based on a metric",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column to Rank"},
            "value_column": {"type": "column", "required": True, "label": "Value Column"},
            "n": {"type": "int", "required": True, "label": "Number of Items"},
            "rank_type": {"type": "string", "required": False, "default": "top",
                         "options": ["top", "bottom"], "label": "Rank Type"},
            "tie_break": {"type": "string", "required": False, "default": "keep_all",
                         "options": ["keep_all", "random", "first", "last"], "label": "Tie Break"}
        },
        "creates_columns": False  # Creates ranked summary
    },

    # -------------------------------------------------------------------------
    # STRATIFICATION
    # -------------------------------------------------------------------------
    "stratification": {
        "display_name": "Stratification",
        "type": TransformationStepType.AGGREGATE,
        "category": "statistics",
        "description": "Generates stratified views by dividing values into ranges",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column to Stratify"},
            "strata": {"type": "list[float]", "required": True, "label": "Strata Boundaries",
                      "placeholder": "e.g., 0, 100, 500, 1000, inf"},
            "value_column": {"type": "column", "required": False, "label": "Value Column (optional)"},
            "include_counts": {"type": "bool", "required": False, "default": True, "label": "Include Counts"}
        },
        "creates_columns": False  # Creates stratified summary
    },

    # -------------------------------------------------------------------------
    # SAMPLING
    # -------------------------------------------------------------------------
    "sampling": {
        "display_name": "Sampling",
        "type": TransformationStepType.FILTER,
        "category": "statistics",
        "description": "Creates a sample-based analytical view without changing original data",
        "parameter_schema": {
            "method": {"type": "string", "required": True, "label": "Sampling Method",
                      "options": ["random", "stratified", "systematic", "cluster"]},
            "sample_size": {"type": "int", "required": False, "label": "Sample Size (or percentage if < 1)"},
            "percentage": {"type": "float", "required": False, "label": "Sample Percentage (0-100)"},
            "stratify_column": {"type": "column", "required": False, "label": "Stratify Column (for stratified)"},
            "random_seed": {"type": "int", "required": False, "label": "Random Seed"},
            "output_type": {"type": "string", "required": False, "default": "sample_view",
                           "options": ["sample_view", "sample_table"], "label": "Output Type"}
        },
        "creates_columns": False  # Creates sample view
    },

    # -------------------------------------------------------------------------
    # CROSS-TABULATION
    # -------------------------------------------------------------------------
    "cross_tabulation": {
        "display_name": "Cross-Tabulation",
        "type": TransformationStepType.AGGREGATE,
        "category": "statistics",
        "description": "Generates contingency tables for categorical variables",
        "parameter_schema": {
            "rows": {"type": "column", "required": True, "label": "Row Variable"},
            "columns": {"type": "column", "required": True, "label": "Column Variable"},
            "values": {"type": "column", "required": False, "label": "Value Column (optional)"},
            "agg_function": {"type": "string", "required": False, "default": "count",
                            "options": ["count", "sum", "mean", "min", "max"], "label": "Aggregation"},
            "show_percentages": {"type": "bool", "required": False, "default": False, "label": "Show Percentages"},
            "percentages_by": {"type": "string", "required": False, "default": "total",
                              "options": ["total", "row", "column"], "label": "Percentages By"}
        },
        "creates_columns": False  # Creates cross-tab table
    },

    # -------------------------------------------------------------------------
    # TREND ANALYSIS
    # -------------------------------------------------------------------------
    "trend_analysis": {
        "display_name": "Trend Analysis",
        "type": TransformationStepType.AGGREGATE,
        "category": "statistics",
        "description": "Generates time-based analytical summaries showing trends",
        "parameter_schema": {
            "date_column": {"type": "column", "required": True, "label": "Date/Time Column"},
            "value_column": {"type": "column", "required": True, "label": "Value Column"},
            "period": {"type": "string", "required": False, "default": "month",
                      "options": ["day", "week", "month", "quarter", "year"], "label": "Period"},
            "aggregations": {"type": "list[str]", "required": False,
                            "options": ["sum", "mean", "count", "min", "max"],
                            "default": ["sum", "mean"], "label": "Aggregations"},
            "include_trendline": {"type": "bool", "required": False, "default": False, "label": "Include Trend Line"},
            "trend_type": {"type": "string", "required": False, "default": "linear",
                          "options": ["linear", "exponential", "moving_average"], "label": "Trend Type"}
        },
        "creates_columns": False  # Creates trend summary table
    },

    # -------------------------------------------------------------------------
    # JOIN DATASETS
    # -------------------------------------------------------------------------
    "join_datasets": {
        "display_name": "Join Datasets",
        "type": TransformationStepType.CALCULATE,
        "category": "table",
        "description": "Join two datasets using various join types (left, right, inner, outer, cross)",
        "parameter_schema": {
            "right_dataset": {"type": "string", "required": True, "label": "Right Dataset Name"},
            "left_key": {"type": "column", "required": True, "label": "Left Join Key"},
            "right_key": {"type": "string", "required": True, "label": "Right Join Key"},
            "join_type": {"type": "string", "required": False, "default": "left_join",
                         "options": ["left_join", "right_join", "inner_join", "outer_join", "cross_join"],
                         "label": "Join Type"},
            "suffix": {"type": "string", "required": False, "default": "_right", "label": "Column Suffix"}
        },
        "creates_columns": True
    },

    # -------------------------------------------------------------------------
    # APPEND DATASETS
    # -------------------------------------------------------------------------
    "append_datasets": {
        "display_name": "Append Datasets",
        "type": TransformationStepType.CALCULATE,
        "category": "table",
        "description": "Append/stack multiple datasets vertically",
        "parameter_schema": {
            "source_datasets": {"type": "list[string]", "required": True, "label": "Dataset Names",
                              "placeholder": "dataset1, dataset2, ..."},
            "align_columns": {"type": "bool", "required": False, "default": True, "label": "Auto-align Columns"},
            "fill_missing": {"type": "bool", "required": False, "default": True, "label": "Fill Missing with Null"}
        },
        "creates_columns": True
    },

    # -------------------------------------------------------------------------
    # SPLIT SHEET
    # -------------------------------------------------------------------------
    "split_sheet": {
        "display_name": "Split Sheet",
        "type": TransformationStepType.CALCULATE,
        "category": "table",
        "description": "Split a dataset into multiple datasets based on unique values in a column",
        "parameter_schema": {
            "column": {"type": "string", "required": True, "label": "Split By Column",
                      "placeholder": "Select a column to split by"},
            "datasets": {"type": "list", "required": False, "label": "Split Datasets",
                        "description": "List of {name, dataframe} tuples for each split"}
        },
        "creates_columns": False,
        "returns_multiple_datasets": True  # Special flag for operations that create multiple datasets
    },
}
