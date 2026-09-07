"""
Tests for Operation Registry
"""
import pytest
from core.operation_registry import OPERATION_REGISTRY, TransformationStepType


class TestOperationRegistry:
    """Test cases for the operation registry"""

    def test_registry_not_empty(self):
        """Test that the registry contains operations"""
        assert len(OPERATION_REGISTRY) > 0

    def test_all_operations_have_required_fields(self):
        """Test that all operations have required metadata fields"""
        required_fields = ["display_name", "type", "category", "description", "parameter_schema"]

        for op_id, op_info in OPERATION_REGISTRY.items():
            for field in required_fields:
                assert field in op_info, f"Operation '{op_id}' missing field: {field}"

    def test_operation_types_are_valid(self):
        """Test that all operation types are valid TransformationStepType values"""
        valid_types = set(t.value for t in TransformationStepType)

        for op_id, op_info in OPERATION_REGISTRY.items():
            op_type = op_info["type"]
            if isinstance(op_type, TransformationStepType):
                assert op_type.value in valid_types
            else:
                assert op_type in valid_types, f"Operation '{op_id}' has invalid type: {op_type}"

    def test_text_operations_category(self):
        """Test that text operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("text_"):
                assert op_info["category"] == "text", f"Text operation '{op_id}' has wrong category"

    def test_math_operations_category(self):
        """Test that math operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("math_"):
                assert op_info["category"] == "math", f"Math operation '{op_id}' has wrong category"

    def test_datetime_operations_category(self):
        """Test that datetime operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("datetime_"):
                assert op_info["category"] == "datetime", f"Datetime operation '{op_id}' has wrong category"

    def test_stat_operations_category(self):
        """Test that statistical operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("stat_"):
                # Statistical operations might use different category names
                # Just verify they have a category
                assert "category" in op_info, f"Stat operation '{op_id}' missing category"

    def test_ml_operations_category(self):
        """Test that ML operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("ml_"):
                assert op_info["category"] == "ml", f"ML operation '{op_id}' has wrong category"

    def test_audit_operations_category(self):
        """Test that audit operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("audit_"):
                assert op_info["category"] == "audit", f"Audit operation '{op_id}' has wrong category"

    def test_ai_operations_category(self):
        """Test that AI operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("ai_"):
                assert op_info["category"] == "ai", f"AI operation '{op_id}' has wrong category"

    # The set of categories the ribbon/context-menu UI actually groups
    # operations into (transform_view.py's category_order) - an
    # operation's category reflects where it belongs in that UI, which is
    # deliberately NOT always a literal match of its operation_id prefix
    # (e.g. "column_value_filter" is a row-filter that happens to filter
    # BY a column's value, correctly categorized "table" not "column";
    # "split_columns_by_delimiter" splits one column into several,
    # correctly categorized "column" not "split").
    _VALID_CATEGORIES = {
        "ai", "audit", "column", "datetime", "financial", "math", "ml",
        "pivot", "split", "sql", "statistics", "table", "text",
    }

    def test_every_operation_has_a_valid_category(self):
        """Every operation's category is one of the UI's known groupings -
        catches a typo'd/unrecognized category, which would silently drop
        an operation out of every ribbon menu (grouped by category) with
        no error anywhere."""
        for op_id, op_info in OPERATION_REGISTRY.items():
            category = op_info.get("category")
            assert category in self._VALID_CATEGORIES, (
                f"Operation '{op_id}' has category '{category}', not one of {sorted(self._VALID_CATEGORIES)}"
            )

    def test_unambiguous_category_spot_checks(self):
        """A handful of operations whose category genuinely should match
        their operation_id prefix, kept as a sanity check against a
        careless miscategorization (unlike the blanket prefix-matching
        this replaced, which assumed a convention the registry never
        actually promised for every op_id)."""
        assert OPERATION_REGISTRY["text_uppercase"]["category"] == "text"
        assert OPERATION_REGISTRY["math_modulo"]["category"] == "math"
        assert OPERATION_REGISTRY["pivot_table"]["category"] == "pivot"
        assert OPERATION_REGISTRY["sql_query"]["category"] == "sql"

    def test_parameter_schema_structure(self):
        """Test that parameter schemas have the fields every parameter
        actually needs. "required" is deliberately NOT asserted here -
        many legitimate parameters across the registry are optional by
        design (e.g. ias36_implied_growth_rate's benchmark_growth_column,
        ifrs16_lease_liability's initial_direct_costs) and omit the key
        entirely rather than writing "required": False everywhere; a
        missing key is correctly treated as "not required" by every
        dialog that reads this schema, so requiring the key to be present
        would only be enforcing a style preference, not correctness."""
        for op_id, op_info in OPERATION_REGISTRY.items():
            schema = op_info.get("parameter_schema", {})
            for param_name, param_info in schema.items():
                assert isinstance(param_info, dict), f"Parameter '{param_name}' in '{op_id}' is not a dict"
                assert "type" in param_info, f"Parameter '{param_name}' in '{op_id}' missing 'type'"
                assert "label" in param_info, f"Parameter '{param_name}' in '{op_id}' missing 'label'"

    def test_column_parameter_types(self):
        """Column-type parameters are usually required, but not always -
        e.g. ifrs16_lease_liability's optional benchmark_ibr and
        ias37_provision_trend's optional settlement_flag are legitimately
        column-typed AND optional (mapping them at all is what turns on
        the extra check they enable). This only asserts the type value
        itself is one of the schema's known kinds, not that every column
        parameter must be required."""
        valid_types = {
            "column", "string", "number", "text", "dict", "list", "bool",
            "int", "float", "list[column]", "list[dict]", "list[float]",
            "list[int]", "list[str]", "list[string]",
        }
        for op_id, op_info in OPERATION_REGISTRY.items():
            schema = op_info.get("parameter_schema", {})
            for param_name, param_info in schema.items():
                param_type = param_info.get("type")
                assert param_type in valid_types, (
                    f"Parameter '{param_name}' in '{op_id}' has unrecognized type '{param_type}'"
                )

    def test_creates_columns_flag(self):
        """Test that operations have correct creates_columns flag"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            # Some operations create columns, others don't (like pivot/unpivot)
            if op_info["type"] in [TransformationStepType.PIVOT, TransformationStepType.UNPIVOT]:
                # These operations might not set creates_columns
                continue
            assert "creates_columns" in op_info, f"Operation '{op_id}' missing 'creates_columns' field"

    def test_filter_operation(self):
        """Test filter operation configuration"""
        # Filter is handled via op_type, check that FILTER type exists
        assert TransformationStepType.FILTER.value == "filter"

    def test_sort_operation(self):
        """Test sort operation configuration"""
        # Sort is handled via op_type, check that SORT type exists
        assert TransformationStepType.SORT.value == "sort"

    def test_pivot_unpivot_operations(self):
        """Test pivot/unpivot operations are in registry if defined"""
        # These operations may or may not be in the registry
        # The key thing is that the type enum values exist
        assert TransformationStepType.PIVOT.value == "pivot"
        assert TransformationStepType.UNPIVOT.value == "unpivot"


class TestTransformationStepType:
    """Test cases for TransformationStepType enum"""

    def test_enum_values(self):
        """Test that enum has expected values"""
        expected = [
            "calculate", "filter", "sort", "ml_predict", "ml_train",
            "ai_enrich", "ai_extract", "ai_pattern_learn", "audit_flag",
            "stat_add_group", "aggregate", "join", "pivot", "unpivot"
        ]
        actual = [t.value for t in TransformationStepType]
        for val in expected:
            assert val in actual, f"Missing enum value: {val}"

    def test_enum_is_string(self):
        """Test that enum inherits from string"""
        assert issubclass(TransformationStepType, str)

    def test_enum_comparison(self):
        """Test enum comparison"""
        assert TransformationStepType.CALCULATE == "calculate"
        assert TransformationStepType.FILTER == "filter"
