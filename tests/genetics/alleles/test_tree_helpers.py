"""
Black-box tests for tree walking helper functions.

Tests validate stateless helper functions used by walk_allele_trees and
synthesize_allele_trees through their public contracts.
"""

import pytest
from src.clan_tune.genetics.alleles import (
    FloatAllele,
    IntAllele,
    _validate_parallel_types,
    _validate_schemas_match,
    _should_include_node,
    _collect_metadata_keys,
)


class TestValidateParallelTypes:
    """Test suite for _validate_parallel_types helper."""

    def test_passes_for_single_allele(self):
        """Single allele passes validation."""
        alleles = [FloatAllele(5.0)]
        _validate_parallel_types(alleles)  # Should not raise

    def test_passes_for_matching_types(self):
        """Multiple alleles of same type pass validation."""
        alleles = [FloatAllele(1.0), FloatAllele(2.0), FloatAllele(3.0)]
        _validate_parallel_types(alleles)  # Should not raise

    def test_raises_on_mismatched_types(self):
        """Raises TypeError when types don't match."""
        alleles = [FloatAllele(1.0), IntAllele(2)]

        with pytest.raises(TypeError) as exc_info:
            _validate_parallel_types(alleles)

        assert "same type" in str(exc_info.value).lower()

    def test_error_message_includes_type_names(self):
        """Error message includes actual type names."""
        alleles = [FloatAllele(1.0), IntAllele(2), FloatAllele(3.0)]

        with pytest.raises(TypeError) as exc_info:
            _validate_parallel_types(alleles)

        error_msg = str(exc_info.value)
        assert "FloatAllele" in error_msg or "IntAllele" in error_msg

    def test_passes_for_empty_list(self):
        """Empty list passes validation (vacuously true)."""
        _validate_parallel_types([])  # Should not raise


class TestFlattenMetadata:
    """Test suite for _flatten_metadata helper."""

    def test_flattens_allele_to_value(self):
        """Alleles in metadata replaced with their .value property."""
        child = FloatAllele(10.0)
        metadata = {"std": child}

        result = _flatten_metadata(metadata)

        assert result["std"] == 10.0
        assert not isinstance(result["std"], FloatAllele)

    def test_preserves_raw_values(self):
        """Raw values in metadata are preserved unchanged."""
        metadata = {"raw_int": 42, "raw_str": "test", "raw_float": 3.14}

        result = _flatten_metadata(metadata)

        assert result["raw_int"] == 42
        assert result["raw_str"] == "test"
        assert result["raw_float"] == 3.14

    def test_handles_mixed_metadata(self):
        """Correctly handles metadata with both alleles and raw values."""
        child = FloatAllele(10.0)
        metadata = {"allele": child, "raw": 99}

        result = _flatten_metadata(metadata)

        assert result["allele"] == 10.0
        assert result["raw"] == 99

    def test_flattens_multiple_alleles(self):
        """Multiple alleles in metadata all flattened."""
        child1 = FloatAllele(10.0)
        child2 = IntAllele(20)
        metadata = {"std": child1, "rate": child2}

        result = _flatten_metadata(metadata)

        assert result["std"] == 10.0
        assert result["rate"] == 20

    def test_returns_new_dict(self):
        """Returns a new dict, doesn't modify original."""
        child = FloatAllele(10.0)
        original = {"std": child}

        result = _flatten_metadata(original)

        assert result is not original
        assert isinstance(original["std"], FloatAllele)  # Original unchanged

    def test_handles_empty_metadata(self):
        """Empty metadata returns empty dict."""
        result = _flatten_metadata({})
        assert result == {}


class TestShouldIncludeNode:
    """Test suite for _should_include_node helper."""

    def test_includes_node_by_default(self):
        """Node included when both filters are True."""
        allele = FloatAllele(5.0)
        assert _should_include_node(allele, True, True) is True

    def test_excludes_when_can_mutate_false_and_filter_false(self):
        """Node excluded when can_mutate=False and include_can_mutate=False."""
        allele = FloatAllele(5.0, can_mutate=False)
        assert _should_include_node(allele, False, True) is False

    def test_includes_when_can_mutate_false_but_filter_true(self):
        """Node included when can_mutate=False but include_can_mutate=True."""
        allele = FloatAllele(5.0, can_mutate=False)
        assert _should_include_node(allele, True, True) is True

    def test_excludes_when_can_crossbreed_false_and_filter_false(self):
        """Node excluded when can_crossbreed=False and include_can_crossbreed=False."""
        allele = FloatAllele(5.0, can_crossbreed=False)
        assert _should_include_node(allele, True, False) is False

    def test_includes_when_can_crossbreed_false_but_filter_true(self):
        """Node included when can_crossbreed=False but include_can_crossbreed=True."""
        allele = FloatAllele(5.0, can_crossbreed=False)
        assert _should_include_node(allele, True, True) is True

    def test_excludes_when_both_false(self):
        """Node excluded when both flags False and both filters False."""
        allele = FloatAllele(5.0, can_mutate=False, can_crossbreed=False)
        assert _should_include_node(allele, False, False) is False

    def test_includes_when_can_mutate_true(self):
        """Node included when can_mutate=True regardless of filter."""
        allele = FloatAllele(5.0, can_mutate=True)
        assert _should_include_node(allele, False, True) is True


class TestCollectMetadataKeys:
    """Test suite for _collect_metadata_keys helper."""

    def test_collects_keys_from_single_allele(self):
        """Collects all keys from single allele's metadata."""
        allele = FloatAllele(5.0, metadata={"a": 1, "b": 2})
        keys = _collect_metadata_keys([allele])

        assert set(keys) == {"a", "b"}

    def test_collects_union_of_keys_from_multiple_alleles(self):
        """Collects union of all keys across multiple alleles."""
        allele1 = FloatAllele(1.0, metadata={"a": 1, "b": 2})
        allele2 = FloatAllele(2.0, metadata={"b": 3, "c": 4})

        keys = _collect_metadata_keys([allele1, allele2])

        assert set(keys) == {"a", "b", "c"}

    def test_returns_sorted_keys(self):
        """Returns keys in sorted order for deterministic traversal."""
        allele = FloatAllele(5.0, metadata={"z": 1, "a": 2, "m": 3})
        keys = _collect_metadata_keys([allele])

        assert keys == ["a", "m", "z"]

    def test_handles_empty_metadata(self):
        """Returns empty list when alleles have no metadata."""
        allele1 = FloatAllele(1.0)
        allele2 = FloatAllele(2.0)

        keys = _collect_metadata_keys([allele1, allele2])

        assert keys == []

    def test_handles_empty_allele_list(self):
        """Returns empty list when given empty allele list."""
        keys = _collect_metadata_keys([])
        assert keys == []

    def test_removes_duplicates(self):
        """Returns each key only once even if in multiple trees."""
        allele1 = FloatAllele(1.0, metadata={"a": 1})
        allele2 = FloatAllele(2.0, metadata={"a": 2})

        keys = _collect_metadata_keys([allele1, allele2])

        assert keys == ["a"]


class TestValidateSchemasMatch:
    """Test suite for _validate_schemas_match helper function."""

    def test_passes_when_all_schemas_match(self):
        """No exception when all alleles have matching schemas."""
        alleles = [
            FloatAllele(1.0, domain={"min": 0.0, "max": 10.0}, can_mutate=True, can_crossbreed=True),
            FloatAllele(2.0, domain={"min": 0.0, "max": 10.0}, can_mutate=True, can_crossbreed=True),
            FloatAllele(3.0, domain={"min": 0.0, "max": 10.0}, can_mutate=True, can_crossbreed=True),
        ]

        # Should not raise
        _validate_schemas_match(alleles)

    def test_raises_on_domain_mismatch(self):
        """Raises ValueError when domains don't match."""
        alleles = [
            FloatAllele(1.0, domain={"min": 0.0, "max": 10.0}),
            FloatAllele(2.0, domain={"min": 0.0, "max": 20.0}),  # Different max
        ]

        with pytest.raises(ValueError, match="Domain mismatch"):
            _validate_schemas_match(alleles)

    def test_raises_on_can_mutate_mismatch(self):
        """Raises ValueError when can_mutate flags don't match."""
        alleles = [
            FloatAllele(1.0, can_mutate=True),
            FloatAllele(2.0, can_mutate=False),  # Different flag
        ]

        with pytest.raises(ValueError, match="can_mutate mismatch"):
            _validate_schemas_match(alleles)

    def test_raises_on_can_crossbreed_mismatch(self):
        """Raises ValueError when can_crossbreed flags don't match."""
        alleles = [
            FloatAllele(1.0, can_crossbreed=True),
            FloatAllele(2.0, can_crossbreed=False),  # Different flag
        ]

        with pytest.raises(ValueError, match="can_crossbreed mismatch"):
            _validate_schemas_match(alleles)

    def test_error_message_includes_mismatched_values(self):
        """Error message includes the actual mismatched values."""
        alleles = [
            FloatAllele(1.0, domain={"min": 0.0, "max": 10.0}),
            FloatAllele(2.0, domain={"min": 0.0, "max": 20.0}),
        ]

        with pytest.raises(ValueError) as exc_info:
            _validate_schemas_match(alleles)

        # Error message should include both domains
        error_msg = str(exc_info.value)
        assert "10.0" in error_msg or "10" in error_msg
        assert "20.0" in error_msg or "20" in error_msg
