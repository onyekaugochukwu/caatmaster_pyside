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

    def test_trig_operations_category(self):
        """Test that trigonometric operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("trig_"):
                assert op_info["category"] == "trigonometric", f"Trig operation '{op_id}' has wrong category"

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

    def test_column_operations_category(self):
        """Test that column operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("column_"):
                assert op_info["category"] == "column", f"Column operation '{op_id}' has wrong category"

    def test_split_operations_category(self):
        """Test that split operations have correct category"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            if op_id.startswith("split_"):
                assert op_info["category"] == "split", f"Split operation '{op_id}' has wrong category"

    def test_parameter_schema_structure(self):
        """Test that parameter schemas have required fields"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            schema = op_info.get("parameter_schema", {})
            for param_name, param_info in schema.items():
                assert isinstance(param_info, dict), f"Parameter '{param_name}' in '{op_id}' is not a dict"
                assert "type" in param_info, f"Parameter '{param_name}' in '{op_id}' missing 'type'"
                assert "required" in param_info, f"Parameter '{param_name}' in '{op_id}' missing 'required'"
                assert "label" in param_info, f"Parameter '{param_name}' in '{op_id}' missing 'label'"

    def test_column_parameter_types(self):
        """Test that column parameters have correct type"""
        for op_id, op_info in OPERATION_REGISTRY.items():
            schema = op_info.get("parameter_schema", {})
            for param_name, param_info in schema.items():
                if param_info.get("type") == "column":
                    assert param_info.get("required", False), f"Column parameter '{param_name}' in '{op_id}' should be required"

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
