"""
Black-box tests for AbstractAllele base class.

Tests validate public API contracts without coupling to implementation details.
Tests use minimal concrete implementations to verify AbstractAllele behavior.
"""

import pytest
from unittest.mock import Mock
from src.clan_tune.genetics.alleles import AbstractAllele


# Minimal concrete allele for testing AbstractAllele behavior
class SimpleAllele(AbstractAllele):
    """Minimal concrete allele for testing."""

    def __init__(
        self,
        value,
        domain=None,
        can_mutate=True,
        can_crossbreed=True,
        metadata=None,
    ):
        self._domain = domain if domain is not None else {}
        super().__init__(value, can_mutate, can_crossbreed, metadata)

    @property
    def domain(self):
        return self._domain.copy() if isinstance(self._domain, dict) else self._domain

    def with_overrides(self, **constructor_overrides):
        return SimpleAllele(
            value=constructor_overrides.get("value", self.value),
            domain=constructor_overrides.get("domain", self._domain),
            can_mutate=constructor_overrides.get("can_mutate", self.can_mutate),
            can_crossbreed=constructor_overrides.get("can_crossbreed", self.can_crossbreed),
            metadata=constructor_overrides.get("metadata", self._metadata),
        )

    def serialize_subclass(self):
        return {
            "value": self.value,
            "domain": self.domain,
            "can_mutate": self.can_mutate,
            "can_crossbreed": self.can_crossbreed,
        }

    @classmethod
    def deserialize_subclass(cls, data, metadata):
        return cls(
            value=data["value"],
            domain=data["domain"],
            can_mutate=data.get("can_mutate", True),
            can_crossbreed=data.get("can_crossbreed", True),
            metadata=metadata,
        )


class TestAbstractAlleleConstruction:
    """Test suite for allele construction and immutability."""

    def test_construction_stores_value(self):
        """Constructed allele stores the provided value."""
        allele = SimpleAllele(42)
        assert allele.value == 42

    def test_construction_defaults_can_mutate_true(self):
        """can_mutate defaults to True if not specified."""
        allele = SimpleAllele(42)
        assert allele.can_mutate is True

    def test_construction_defaults_can_crossbreed_true(self):
        """can_crossbreed defaults to True if not specified."""
        allele = SimpleAllele(42)
        assert allele.can_crossbreed is True

    def test_construction_defaults_empty_metadata(self):
        """metadata defaults to empty dict if not specified."""
        allele = SimpleAllele(42)
        assert allele.metadata == {}

    def test_construction_accepts_can_mutate_false(self):
        """can_mutate can be set to False."""
        allele = SimpleAllele(42, can_mutate=False)
        assert allele.can_mutate is False

    def test_construction_accepts_can_crossbreed_false(self):
        """can_crossbreed can be set to False."""
        allele = SimpleAllele(42, can_crossbreed=False)
        assert allele.can_crossbreed is False

    def test_construction_accepts_metadata_dict(self):
        """metadata can be provided as dict."""
        metadata = {"key": "value"}
        allele = SimpleAllele(42, metadata=metadata)
        assert allele.metadata == metadata

    def test_metadata_property_returns_copy(self):
        """metadata property returns a copy, not the internal dict."""
        allele = SimpleAllele(42, metadata={"key": "value"})
        metadata_copy = allele.metadata
        metadata_copy["new_key"] = "new_value"
        # Original metadata unchanged
        assert allele.metadata == {"key": "value"}


class TestAbstractAlleleWithValue:
    """Test suite for with_value method."""

    def test_with_value_returns_new_instance(self):
        """with_value returns a new allele instance."""
        original = SimpleAllele(42)
        new_allele = original.with_value(100)
        assert new_allele is not original

    def test_with_value_updates_value(self):
        """with_value returns allele with updated value."""
        original = SimpleAllele(42)
        new_allele = original.with_value(100)
        assert new_allele.value == 100

    def test_with_value_preserves_original(self):
        """with_value does not modify the original allele."""
        original = SimpleAllele(42)
        original.with_value(100)
        assert original.value == 42

    def test_with_value_preserves_flags(self):
        """with_value preserves can_mutate and can_crossbreed flags."""
        original = SimpleAllele(42, can_mutate=False, can_crossbreed=False)
        new_allele = original.with_value(100)
        assert new_allele.can_mutate is False
        assert new_allele.can_crossbreed is False

    def test_with_value_preserves_metadata(self):
        """with_value preserves metadata."""
        original = SimpleAllele(42, metadata={"key": "value"})
        new_allele = original.with_value(100)
        assert new_allele.metadata == {"key": "value"}


class TestAbstractAlleleWithMetadata:
    """Test suite for with_metadata method."""

    def test_with_metadata_returns_new_instance(self):
        """with_metadata returns a new allele instance."""
        original = SimpleAllele(42)
        new_allele = original.with_metadata(key="value")
        assert new_allele is not original

    def test_with_metadata_adds_new_entry(self):
        """with_metadata adds new metadata entry."""
        original = SimpleAllele(42)
        new_allele = original.with_metadata(key="value")
        assert new_allele.metadata["key"] == "value"

    def test_with_metadata_updates_existing_entry(self):
        """with_metadata updates existing metadata entry."""
        original = SimpleAllele(42, metadata={"key": "old_value"})
        new_allele = original.with_metadata(key="new_value")
        assert new_allele.metadata["key"] == "new_value"

    def test_with_metadata_preserves_original(self):
        """with_metadata does not modify the original allele."""
        original = SimpleAllele(42, metadata={"key": "value"})
        original.with_metadata(new_key="new_value")
        assert original.metadata == {"key": "value"}

    def test_with_metadata_preserves_value(self):
        """with_metadata preserves the value."""
        original = SimpleAllele(42)
        new_allele = original.with_metadata(key="value")
        assert new_allele.value == 42

    def test_with_metadata_preserves_flags(self):
        """with_metadata preserves can_mutate and can_crossbreed flags."""
        original = SimpleAllele(42, can_mutate=False, can_crossbreed=False)
        new_allele = original.with_metadata(key="value")
        assert new_allele.can_mutate is False
        assert new_allele.can_crossbreed is False

    def test_with_metadata_accepts_multiple_updates(self):
        """with_metadata can update multiple entries at once."""
        original = SimpleAllele(42)
        new_allele = original.with_metadata(key1="value1", key2="value2")
        assert new_allele.metadata["key1"] == "value1"
        assert new_allele.metadata["key2"] == "value2"


class TestAbstractAlleleSerializationRoundTrip:
    """Test suite for serialization round-trip behavior."""

    def test_round_trip_preserves_value(self):
        """Serialize then deserialize preserves value."""
        original = SimpleAllele(42)
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.value == 42

    def test_round_trip_preserves_domain(self):
        """Serialize then deserialize preserves domain."""
        original = SimpleAllele(42, domain={"min": 0, "max": 100})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.domain == {"min": 0, "max": 100}

    def test_round_trip_preserves_flags(self):
        """Serialize then deserialize preserves flags."""
        original = SimpleAllele(42, can_mutate=False, can_crossbreed=False)
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.can_mutate is False
        assert restored.can_crossbreed is False

    def test_round_trip_preserves_raw_metadata(self):
        """Serialize then deserialize preserves raw metadata values."""
        original = SimpleAllele(42, metadata={"key": "value", "num": 123})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.metadata["key"] == "value"
        assert restored.metadata["num"] == 123

    def test_round_trip_preserves_nested_alleles(self):
        """Serialize then deserialize preserves nested alleles."""
        nested = SimpleAllele(100, can_mutate=False)
        original = SimpleAllele(42, metadata={"nested": nested})

        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)

        restored_nested = restored.metadata["nested"]
        assert isinstance(restored_nested, SimpleAllele)
        assert restored_nested.value == 100
        assert restored_nested.can_mutate is False

    def test_round_trip_preserves_deeply_nested_alleles(self):
        """Serialize then deserialize preserves deeply nested allele trees."""
        level3 = SimpleAllele(3, can_mutate=False)
        level2 = SimpleAllele(2, metadata={"child": level3}, can_crossbreed=False)
        level1 = SimpleAllele(1, metadata={"child": level2})

        serialized = level1.serialize()
        restored = AbstractAllele.deserialize(serialized)

        assert restored.value == 1
        assert restored.can_mutate is True

        level2_restored = restored.metadata["child"]
        assert isinstance(level2_restored, SimpleAllele)
        assert level2_restored.value == 2
        assert level2_restored.can_crossbreed is False

        level3_restored = level2_restored.metadata["child"]
        assert isinstance(level3_restored, SimpleAllele)
        assert level3_restored.value == 3
        assert level3_restored.can_mutate is False

    def test_round_trip_reconstructs_correct_subclass_type(self):
        """Serialize then deserialize reconstructs the correct concrete type."""
        original = SimpleAllele(42, domain={"min": 0, "max": 100})
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert type(restored) is type(original)
        assert isinstance(restored, SimpleAllele)

    def test_serialize_returns_dict(self):
        """Serialize returns a dict suitable for deserialization."""
        allele = SimpleAllele(42, metadata={"nested": SimpleAllele(100)})
        serialized = allele.serialize()
        assert isinstance(serialized, dict)
        # Round-trip validates it's in correct format
        restored = AbstractAllele.deserialize(serialized)
        assert restored.value == 42


class TestAbstractAlleleDeserializationErrors:
    """Test suite for deserialization error conditions."""

    def test_deserialize_raises_on_missing_type_field(self):
        """Deserialize raises ValueError when 'type' field is missing."""
        data = {"value": 42}
        with pytest.raises(ValueError) as exc_info:
            AbstractAllele.deserialize(data)
        # Error message should mention the problem
        assert "type" in str(exc_info.value).lower()
        assert "missing" in str(exc_info.value).lower()

    def test_deserialize_raises_on_unknown_type(self):
        """Deserialize raises ValueError for unknown allele type."""
        data = {"type": "NonexistentAllele", "value": 42}
        with pytest.raises(ValueError) as exc_info:
            AbstractAllele.deserialize(data)
        # Error message should mention the problem
        assert "type" in str(exc_info.value).lower()
        assert "unknown" in str(exc_info.value).lower()


class TestAbstractAlleleTreeWalking:
    """Test suite for tree walking wrapper contract."""

    def test_walk_tree_wraps_self_in_list(self):
        """walk_tree wraps self in list when calling walker function."""
        allele = SimpleAllele(42)
        mock_walker = Mock(return_value=iter([]))
        handler = lambda nodes: None

        list(allele.walk_tree(handler, _walker=mock_walker))

        # Verify walker called with self wrapped in list
        call_args = mock_walker.call_args
        assert call_args[0][0] == [allele]

    def test_walk_tree_passes_handler_to_walker(self):
        """walk_tree passes handler function to walker."""
        allele = SimpleAllele(42)
        mock_walker = Mock(return_value=iter([]))
        handler = lambda nodes: "test"

        list(allele.walk_tree(handler, _walker=mock_walker))

        # Verify handler passed through
        call_args = mock_walker.call_args
        assert call_args[0][1] is handler

    def test_walk_tree_passes_flags_to_walker(self):
        """walk_tree passes include flags to walker."""
        allele = SimpleAllele(42)
        mock_walker = Mock(return_value=iter([]))

        list(allele.walk_tree(
            lambda nodes: None,
            include_can_mutate=False,
            include_can_crossbreed=False,
            _walker=mock_walker
        ))

        # Verify flags passed through
        call_args = mock_walker.call_args
        assert call_args[1]["include_can_mutate"] is False
        assert call_args[1]["include_can_crossbreed"] is False

    def test_walk_tree_yields_walker_results(self):
        """walk_tree yields results from walker function."""
        allele = SimpleAllele(42)
        mock_walker = Mock(return_value=iter([1, 2, 3]))

        results = list(allele.walk_tree(lambda nodes: None, _walker=mock_walker))

        assert results == [1, 2, 3]

    def test_update_tree_wraps_self_in_list(self):
        """update_tree wraps self in list when calling updater function."""
        allele = SimpleAllele(42)
        mock_updater = Mock(return_value=SimpleAllele(100))
        handler = lambda nodes: 100

        allele.update_tree(handler, _updater=mock_updater)

        # Verify updater called with self wrapped in list
        call_args = mock_updater.call_args
        assert call_args[0][0] == [allele]

    def test_update_tree_passes_handler_to_updater(self):
        """update_tree passes handler function to updater."""
        allele = SimpleAllele(42)
        mock_updater = Mock(return_value=SimpleAllele(100))
        handler = lambda nodes: 100

        allele.update_tree(handler, _updater=mock_updater)

        # Verify handler passed through
        call_args = mock_updater.call_args
        assert call_args[0][1] is handler

    def test_update_tree_passes_flags_to_updater(self):
        """update_tree passes include flags to updater."""
        allele = SimpleAllele(42)
        mock_updater = Mock(return_value=SimpleAllele(100))

        allele.update_tree(
            lambda nodes: 100,
            include_can_mutate=False,
            include_can_crossbreed=False,
            _updater=mock_updater
        )

        # Verify flags passed through
        call_args = mock_updater.call_args
        assert call_args[1]["include_can_mutate"] is False
        assert call_args[1]["include_can_crossbreed"] is False

    def test_update_tree_returns_updater_result(self):
        """update_tree returns result from updater function."""
        allele = SimpleAllele(42)
        new_allele = SimpleAllele(100)
        mock_updater = Mock(return_value=new_allele)

        result = allele.update_tree(lambda nodes: 100, _updater=mock_updater)

        assert result is new_allele


class TestFlattenUnflatten:
    """Test suite for flatten() and unflatten() methods."""

    def test_flatten_replaces_allele_with_raw_value(self):
        """flatten() replaces allele in metadata with its value."""
        child = SimpleAllele(10.0)
        parent = SimpleAllele(5.0, metadata={"std": child})

        flat = parent.flatten()

        # Metadata should contain raw value, not allele
        assert flat.metadata["std"] == 10.0
        assert not isinstance(flat.metadata["std"], AbstractAllele)

    def test_flatten_preserves_raw_values_unchanged(self):
        """flatten() leaves raw metadata values unchanged."""
        parent = SimpleAllele(5.0, metadata={"rate": 0.1, "name": "test"})

        flat = parent.flatten()

        assert flat.metadata["rate"] == 0.1
        assert flat.metadata["name"] == "test"

    def test_flatten_handles_mixed_metadata(self):
        """flatten() correctly handles metadata with both alleles and raw values."""
        child = SimpleAllele(10.0)
        parent = SimpleAllele(5.0, metadata={"std": child, "rate": 0.1})

        flat = parent.flatten()

        # Allele replaced with value
        assert flat.metadata["std"] == 10.0
        assert not isinstance(flat.metadata["std"], AbstractAllele)
        # Raw value unchanged
        assert flat.metadata["rate"] == 0.1

    def test_flatten_returns_new_instance(self):
        """flatten() returns a new allele instance."""
        child = SimpleAllele(10.0)
        parent = SimpleAllele(5.0, metadata={"std": child})

        flat = parent.flatten()

        assert flat is not parent

    def test_flatten_preserves_original_unchanged(self):
        """flatten() does not modify the original allele."""
        child = SimpleAllele(10.0)
        parent = SimpleAllele(5.0, metadata={"std": child})

        flat = parent.flatten()

        # Original still has allele in metadata
        assert isinstance(parent.metadata["std"], AbstractAllele)
        assert parent.metadata["std"] is child

    def test_flatten_preserves_value(self):
        """flatten() preserves the allele's value."""
        child = SimpleAllele(10.0)
        parent = SimpleAllele(5.0, metadata={"std": child})

        flat = parent.flatten()

        assert flat.value == parent.value

    def test_flatten_preserves_flags(self):
        """flatten() preserves can_mutate and can_crossbreed flags."""
        child = SimpleAllele(10.0)
        parent = SimpleAllele(
            5.0,
            can_mutate=False,
            can_crossbreed=False,
            metadata={"std": child}
        )

        flat = parent.flatten()

        assert flat.can_mutate is False
        assert flat.can_crossbreed is False

    def test_flatten_with_empty_metadata(self):
        """flatten() works correctly with empty metadata."""
        allele = SimpleAllele(5.0)

        flat = allele.flatten()

        assert flat.metadata == {}

    def test_flatten_with_nested_alleles(self):
        """flatten() replaces nested alleles at single level (non-recursive)."""
        grandchild = SimpleAllele(20.0)
        child = SimpleAllele(10.0, metadata={"mutation_std": grandchild})
        parent = SimpleAllele(5.0, metadata={"std": child})

        flat = parent.flatten()

        # Child allele is replaced with its value (which contains nested metadata)
        assert flat.metadata["std"] == 10.0

    def test_unflatten_restores_alleles(self):
        """unflatten() replaces flattened values with resolved allele objects."""
        flat = SimpleAllele(5.0, metadata={"std": 10.0, "rate": 0.1})
        resolved = {"std": SimpleAllele(20.0)}

        unflat = flat.unflatten(resolved)

        # std should now be an allele
        assert isinstance(unflat.metadata["std"], AbstractAllele)
        assert unflat.metadata["std"].value == 20.0

    def test_unflatten_preserves_unresolved_keys(self):
        """unflatten() preserves metadata keys not in resolved_metadata."""
        flat = SimpleAllele(5.0, metadata={"std": 10.0, "rate": 0.1})
        resolved = {"std": SimpleAllele(20.0)}

        unflat = flat.unflatten(resolved)

        # rate unchanged
        assert unflat.metadata["rate"] == 0.1

    def test_unflatten_returns_new_instance(self):
        """unflatten() returns a new allele instance."""
        flat = SimpleAllele(5.0, metadata={"std": 10.0})
        resolved = {"std": SimpleAllele(20.0)}

        unflat = flat.unflatten(resolved)

        assert unflat is not flat

    def test_unflatten_preserves_original_unchanged(self):
        """unflatten() does not modify the original allele."""
        flat = SimpleAllele(5.0, metadata={"std": 10.0, "rate": 0.1})
        resolved = {"std": SimpleAllele(20.0)}

        unflat = flat.unflatten(resolved)

        # Original unchanged
        assert flat.metadata["std"] == 10.0
        assert not isinstance(flat.metadata["std"], AbstractAllele)

    def test_unflatten_preserves_value(self):
        """unflatten() preserves the allele's value."""
        flat = SimpleAllele(5.0, metadata={"std": 10.0})
        resolved = {"std": SimpleAllele(20.0)}

        unflat = flat.unflatten(resolved)

        assert unflat.value == flat.value

    def test_unflatten_preserves_flags(self):
        """unflatten() preserves can_mutate and can_crossbreed flags."""
        flat = SimpleAllele(
            5.0,
            can_mutate=False,
            can_crossbreed=False,
            metadata={"std": 10.0}
        )
        resolved = {"std": SimpleAllele(20.0)}

        unflat = flat.unflatten(resolved)

        assert unflat.can_mutate is False
        assert unflat.can_crossbreed is False

    def test_unflatten_with_empty_resolved_metadata(self):
        """unflatten() with empty resolved_metadata leaves metadata unchanged."""
        flat = SimpleAllele(5.0, metadata={"std": 10.0, "rate": 0.1})
        resolved = {}

        unflat = flat.unflatten(resolved)

        assert unflat.metadata == flat.metadata

    def test_unflatten_can_add_new_keys(self):
        """unflatten() can add new metadata keys not present in original."""
        flat = SimpleAllele(5.0, metadata={"rate": 0.1})
        resolved = {"std": SimpleAllele(20.0)}

        unflat = flat.unflatten(resolved)

        # New key added
        assert isinstance(unflat.metadata["std"], AbstractAllele)
        assert unflat.metadata["std"].value == 20.0
        # Old key preserved
        assert unflat.metadata["rate"] == 0.1

    def test_round_trip_preserves_structure(self):
        """Round-trip flatten -> unflatten preserves allele tree structure."""
        child = SimpleAllele(10.0)
        parent = SimpleAllele(5.0, metadata={"std": child, "rate": 0.1})

        # Flatten
        flat = parent.flatten()
        assert flat.metadata["std"] == 10.0  # Raw value

        # Prepare resolved metadata (simulate tree synthesis)
        resolved = {"std": SimpleAllele(10.0)}  # Restore allele

        # Unflatten
        unflat = flat.unflatten(resolved)

        # Structure preserved
        assert isinstance(unflat.metadata["std"], AbstractAllele)
        assert unflat.metadata["std"].value == 10.0
        assert unflat.metadata["rate"] == 0.1

    def test_flatten_multiple_alleles_in_metadata(self):
        """flatten() replaces all alleles in metadata with their values."""
        child1 = SimpleAllele(10.0)
        child2 = SimpleAllele(20.0)
        child3 = SimpleAllele(30.0)
        parent = SimpleAllele(
            5.0,
            metadata={"std": child1, "scale": child2, "rate": child3}
        )

        flat = parent.flatten()

        assert flat.metadata["std"] == 10.0
        assert flat.metadata["scale"] == 20.0
        assert flat.metadata["rate"] == 30.0
        # All should be raw values
        assert not isinstance(flat.metadata["std"], AbstractAllele)
        assert not isinstance(flat.metadata["scale"], AbstractAllele)
        assert not isinstance(flat.metadata["rate"], AbstractAllele)

    def test_unflatten_multiple_alleles(self):
        """unflatten() restores multiple alleles from resolved_metadata."""
        flat = SimpleAllele(5.0, metadata={"std": 10.0, "scale": 20.0, "rate": 0.1})
        resolved = {
            "std": SimpleAllele(15.0),
            "scale": SimpleAllele(25.0)
        }

        unflat = flat.unflatten(resolved)

        # Resolved keys are alleles
        assert isinstance(unflat.metadata["std"], AbstractAllele)
        assert unflat.metadata["std"].value == 15.0
        assert isinstance(unflat.metadata["scale"], AbstractAllele)
        assert unflat.metadata["scale"].value == 25.0
        # Unresolved key unchanged
        assert unflat.metadata["rate"] == 0.1
