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
    _collect_metadata_keys,
    CanMutateFilter,
    CanCrossbreedFilter,
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


class TestCanMutateFilter:
    """Test suite for CanMutateFilter callable predicate."""

    def test_construction_with_true_state(self):
        """Filter can be constructed with True state."""
        pred = CanMutateFilter(True)
        assert pred.state is True

    def test_construction_with_false_state(self):
        """Filter can be constructed with False state."""
        pred = CanMutateFilter(False)
        assert pred.state is False

    def test_returns_true_when_node_matches_true_state(self):
        """Filter returns True when node can_mutate matches filter state (True)."""
        pred = CanMutateFilter(True)
        node = FloatAllele(5.0, can_mutate=True)
        assert pred(node) is True

    def test_returns_false_when_node_mismatches_true_state(self):
        """Filter returns False when node can_mutate doesn't match filter state (True)."""
        pred = CanMutateFilter(True)
        node = FloatAllele(5.0, can_mutate=False)
        assert pred(node) is False

    def test_returns_true_when_node_matches_false_state(self):
        """Filter returns True when node can_mutate matches filter state (False)."""
        pred = CanMutateFilter(False)
        node = FloatAllele(5.0, can_mutate=False)
        assert pred(node) is True

    def test_returns_false_when_node_mismatches_false_state(self):
        """Filter returns False when node can_mutate doesn't match filter state (False)."""
        pred = CanMutateFilter(False)
        node = FloatAllele(5.0, can_mutate=True)
        assert pred(node) is False

    def test_works_with_intallele(self):
        """Filter works with different allele types."""
        pred = CanMutateFilter(True)
        node = IntAllele(42, can_mutate=True)
        assert pred(node) is True


class TestCanCrossbreedFilter:
    """Test suite for CanCrossbreedFilter callable predicate."""

    def test_construction_with_true_state(self):
        """Filter can be constructed with True state."""
        pred = CanCrossbreedFilter(True)
        assert pred.state is True

    def test_construction_with_false_state(self):
        """Filter can be constructed with False state."""
        pred = CanCrossbreedFilter(False)
        assert pred.state is False

    def test_returns_true_when_node_matches_true_state(self):
        """Filter returns True when node can_crossbreed matches filter state (True)."""
        pred = CanCrossbreedFilter(True)
        node = FloatAllele(5.0, can_crossbreed=True)
        assert pred(node) is True

    def test_returns_false_when_node_mismatches_true_state(self):
        """Filter returns False when node can_crossbreed doesn't match filter state (True)."""
        pred = CanCrossbreedFilter(True)
        node = FloatAllele(5.0, can_crossbreed=False)
        assert pred(node) is False

    def test_returns_true_when_node_matches_false_state(self):
        """Filter returns True when node can_crossbreed matches filter state (False)."""
        pred = CanCrossbreedFilter(False)
        node = FloatAllele(5.0, can_crossbreed=False)
        assert pred(node) is True

    def test_returns_false_when_node_mismatches_false_state(self):
        """Filter returns False when node can_crossbreed doesn't match filter state (False)."""
        pred = CanCrossbreedFilter(False)
        node = FloatAllele(5.0, can_crossbreed=True)
        assert pred(node) is False

    def test_works_with_intallele(self):
        """Filter works with different allele types."""
        pred = CanCrossbreedFilter(True)
        node = IntAllele(42, can_crossbreed=True)
        assert pred(node) is True
