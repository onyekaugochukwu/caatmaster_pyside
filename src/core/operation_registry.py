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


OPERATION_REGISTRY = {
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
        "creates_columns": ["{col}_lower"]
    },
    "text_titlecase": {
        "display_name": "Title Case",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Converts text to title case",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_title"]
    },
    "text_trim": {
        "display_name": "Trim Whitespace",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Removes leading and trailing whitespace",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_trimmed"]
    },
    "text_extract_numbers": {
        "display_name": "Extract Numbers",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Extracts numbers from text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_numbers"]
    },
    "text_extract_text": {
        "display_name": "Extract Text",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Extracts alphabetic text from string",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_text"]
    },
    "text_reverse": {
        "display_name": "Reverse Text",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Reverses the text string",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_reversed"]
    },
    "text_length": {
        "display_name": "Text Length",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Returns the length of the text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_length"]
    },
    "text_hash_md5": {
        "display_name": "Hash (MD5)",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Creates an MD5 hash of the text",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_md5"]
    },
    "text_soundex": {
        "display_name": "Soundex Code",
        "type": TransformationStepType.CALCULATE,
        "category": "text",
        "description": "Creates a Soundex code for phonetic matching",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_soundex"]
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
        "creates_columns": ["{col}_rounded"]
    },
    "math_ceil": {
        "display_name": "Ceiling",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Rounds up to the nearest integer",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_ceil"]
    },
    "math_floor": {
        "display_name": "Floor",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Rounds down to the nearest integer",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_floor"]
    },
    "math_abs": {
        "display_name": "Absolute Value",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Returns the absolute value",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_abs"]
    },
    "math_sqrt": {
        "display_name": "Square Root",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates the square root",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_sqrt"]
    },
    "math_square": {
        "display_name": "Square",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Squares the number",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_sq"]
    },
    "math_log": {
        "display_name": "Logarithm (ln)",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates the natural logarithm",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_log"]
    },
    "math_log10": {
        "display_name": "Logarithm (base 10)",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates the base-10 logarithm",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_log10"]
    },
    "math_exp": {
        "display_name": "Exponential",
        "type": TransformationStepType.CALCULATE,
        "category": "math",
        "description": "Calculates e raised to the power",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_exp"]
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
        "creates_columns": ["{col}_sin"]
    },
    "trig_cos": {
        "display_name": "Cosine",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates cosine (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_cos"]
    },
    "trig_tan": {
        "display_name": "Tangent",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates tangent (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_tan"]
    },
    "trig_asin": {
        "display_name": "Arc Sine",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates arc sine (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_asin"]
    },
    "trig_acos": {
        "display_name": "Arc Cosine",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates arc cosine (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_acos"]
    },
    "trig_atan": {
        "display_name": "Arc Tangent",
        "type": TransformationStepType.CALCULATE,
        "category": "trigonometric",
        "description": "Calculates arc tangent (radians)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_atan"]
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
        "creates_columns": ["{col}_year"]
    },
    "datetime_month": {
        "display_name": "Extract Month",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the month (1-12) from a date",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_month"]
    },
    "datetime_day": {
        "display_name": "Extract Day",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the day of month from a date",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_day"]
    },
    "datetime_hour": {
        "display_name": "Extract Hour",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the hour from a datetime",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Datetime Column"}
        },
        "creates_columns": ["{col}_hour"]
    },
    "datetime_minute": {
        "display_name": "Extract Minute",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the minute from a datetime",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Datetime Column"}
        },
        "creates_columns": ["{col}_minute"]
    },
    "datetime_second": {
        "display_name": "Extract Second",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the second from a datetime",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Datetime Column"}
        },
        "creates_columns": ["{col}_second"]
    },
    "datetime_weekday": {
        "display_name": "Extract Weekday",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the day of week (0=Monday, 6=Sunday)",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_weekday"]
    },
    "datetime_quarter": {
        "display_name": "Extract Quarter",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Extracts the quarter (1-4) from a date",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_quarter"]
    },
    "datetime_age_days": {
        "display_name": "Age (Days)",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Calculates age in days from today",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_age_days"]
    },
    "datetime_age_years": {
        "display_name": "Age (Years)",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Calculates age in years from today",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_age_years"]
    },
    "datetime_is_weekend": {
        "display_name": "Is Weekend",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Returns True if date is Saturday or Sunday",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_is_weekend"]
    },
    "datetime_is_leap_year": {
        "display_name": "Is Leap Year",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Returns True if year is a leap year",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_is_leap_year"]
    },
    "datetime_days_in_month": {
        "display_name": "Days in Month",
        "type": TransformationStepType.CALCULATE,
        "category": "datetime",
        "description": "Returns the number of days in the month",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Date Column"}
        },
        "creates_columns": ["{col}_days_in_month"]
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
        "creates_columns": ["{col}_zscore"]
    },
    "stat_percent_rank": {
        "display_name": "Percent Rank",
        "type": TransformationStepType.CALCULATE,
        "category": "statistics",
        "description": "Calculates the percent rank within the column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_pct_rank"]
    },
    "stat_rank": {
        "display_name": "Rank",
        "type": TransformationStepType.CALCULATE,
        "category": "statistics",
        "description": "Calculates the rank within the column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_rank"]
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
    "column_change_dtype": {
        "display_name": "Change Data Type",
        "type": TransformationStepType.CALCULATE,
        "category": "column",
        "description": "Changes the data type of a column",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"},
            "new_dtype": {"type": "string", "required": True, "label": "New Type",
                         "options": ["Int64", "Float64", "Utf8", "Boolean", "Date", "Datetime"]}
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
        "creates_columns": ["{col}_part0", "{col}_part1"]
    },
    "split_space": {
        "display_name": "Split by Space",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by space",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_part0", "{col}_part1"]
    },
    "split_semicolon": {
        "display_name": "Split by Semicolon",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by semicolon",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_part0", "{col}_part1"]
    },
    "split_pipe": {
        "display_name": "Split by Pipe",
        "type": TransformationStepType.CALCULATE,
        "category": "split",
        "description": "Splits text by pipe",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Column"}
        },
        "creates_columns": ["{col}_part0", "{col}_part1"]
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
        "creates_columns": ["{col}_part0", "{col}_part1"]
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
        "creates_columns": ["{col}_is_anomaly", "{col}_anomaly_score"]
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
        "creates_columns": ["{col}_is_outlier", "{col}_zscore"]
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
        "creates_columns": ["{col}_is_outlier", "{col}_iqr_distance"]
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
        "creates_columns": ["{col}_is_outlier", "{col}_lof_score"]
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
        "creates_columns": ["{col}_is_outlier", "{col}_outlier_score"]
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
        "creates_columns": ["{col}_benford_deviation", "{col}_is_suspicious"]
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
        "creates_columns": ["{col}_ai_explanation"]
    },
    "ai_sentiment": {
        "display_name": "Sentiment Analysis",
        "type": TransformationStepType.AI_ENRICH,
        "category": "ai",
        "description": "Analyzes text sentiment",
        "parameter_schema": {
            "column": {"type": "column", "required": True, "label": "Text Column"}
        },
        "creates_columns": ["{col}_sentiment_score", "{col}_sentiment_label"]
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
        "creates_columns": ["{col}_extracted"]
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
        "creates_columns": ["{col}_min", "{col}_max", "{col}_mean", "{col}_std"]
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
}
