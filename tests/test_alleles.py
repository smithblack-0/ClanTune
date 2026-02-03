"""
Black-box tests for AbstractAllele base class.

Tests use minimal concrete implementations to verify AbstractAllele behavior
without coupling to implementation details.
"""

import pytest
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
            value=constructor_overrides.get("value", self._value),
            domain=constructor_overrides.get("domain", self._domain),
            can_mutate=constructor_overrides.get("can_mutate", self._can_mutate),
            can_crossbreed=constructor_overrides.get("can_crossbreed", self._can_crossbreed),
            metadata=constructor_overrides.get("metadata", self._metadata),
        )

    def serialize_subclass(self):
        return {
            "value": self._value,
            "domain": self.domain,
            "can_mutate": self._can_mutate,
            "can_crossbreed": self._can_crossbreed,
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


class TestAbstractAlleleRegistry:
    """Test suite for subclass registration via __init_subclass__."""

    def test_subclass_auto_registers_in_registry(self):
        """Subclass is automatically registered by name in AbstractAllele._registry."""
        assert "SimpleAllele" in AbstractAllele._registry
        assert AbstractAllele._registry["SimpleAllele"] is SimpleAllele

    def test_multiple_subclasses_all_registered(self):
        """Multiple subclasses are all registered independently."""

        class AnotherAllele(AbstractAllele):
            @property
            def domain(self):
                return {}

            def with_overrides(self, **kwargs):
                pass

            def serialize_subclass(self):
                pass

            @classmethod
            def deserialize_subclass(cls, data, metadata):
                pass

        assert "AnotherAllele" in AbstractAllele._registry
        assert AbstractAllele._registry["AnotherAllele"] is AnotherAllele
        # Original still registered
        assert "SimpleAllele" in AbstractAllele._registry


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


class TestAbstractAlleleSerialization:
    """Test suite for serialization."""

    def test_serialize_includes_type_field(self):
        """serialize() includes 'type' field with class name."""
        allele = SimpleAllele(42)
        serialized = allele.serialize()
        assert serialized["type"] == "SimpleAllele"

    def test_serialize_includes_subclass_data(self):
        """serialize() includes data from serialize_subclass()."""
        allele = SimpleAllele(42, domain={"min": 0, "max": 100})
        serialized = allele.serialize()
        assert serialized["value"] == 42
        assert serialized["domain"] == {"min": 0, "max": 100}

    def test_serialize_includes_empty_metadata(self):
        """serialize() includes metadata field even when empty."""
        allele = SimpleAllele(42)
        serialized = allele.serialize()
        assert "metadata" in serialized
        assert serialized["metadata"] == {}

    def test_serialize_includes_raw_metadata_values(self):
        """serialize() includes raw metadata values."""
        allele = SimpleAllele(42, metadata={"key": "value", "num": 123})
        serialized = allele.serialize()
        assert serialized["metadata"]["key"] == "value"
        assert serialized["metadata"]["num"] == 123

    def test_serialize_recursively_serializes_metadata_alleles(self):
        """serialize() recursively serializes alleles in metadata."""
        nested_allele = SimpleAllele(100)
        parent_allele = SimpleAllele(42, metadata={"nested": nested_allele})
        serialized = parent_allele.serialize()

        # Nested allele should be serialized
        assert isinstance(serialized["metadata"]["nested"], dict)
        assert serialized["metadata"]["nested"]["type"] == "SimpleAllele"
        assert serialized["metadata"]["nested"]["value"] == 100

    def test_serialize_handles_deeply_nested_alleles(self):
        """serialize() handles multiple levels of nested alleles."""
        level3 = SimpleAllele(3)
        level2 = SimpleAllele(2, metadata={"child": level3})
        level1 = SimpleAllele(1, metadata={"child": level2})

        serialized = level1.serialize()
        assert serialized["value"] == 1
        assert serialized["metadata"]["child"]["value"] == 2
        assert serialized["metadata"]["child"]["metadata"]["child"]["value"] == 3


class TestAbstractAlleleDeserialization:
    """Test suite for deserialization."""

    def test_deserialize_dispatches_to_correct_subclass(self):
        """deserialize() dispatches to the subclass specified by 'type' field."""
        data = {
            "type": "SimpleAllele",
            "value": 42,
            "domain": {},
            "can_mutate": True,
            "can_crossbreed": True,
            "metadata": {},
        }
        allele = AbstractAllele.deserialize(data)
        assert isinstance(allele, SimpleAllele)
        assert allele.value == 42

    def test_deserialize_raises_on_missing_type_field(self):
        """deserialize() raises ValueError if 'type' field is missing."""
        data = {"value": 42}
        with pytest.raises(ValueError, match="Missing 'type' field"):
            AbstractAllele.deserialize(data)

    def test_deserialize_raises_on_unknown_type(self):
        """deserialize() raises ValueError for unknown type."""
        data = {"type": "NonexistentAllele", "value": 42}
        with pytest.raises(ValueError, match="Unknown allele type"):
            AbstractAllele.deserialize(data)

    def test_deserialize_reconstructs_raw_metadata(self):
        """deserialize() preserves raw metadata values."""
        data = {
            "type": "SimpleAllele",
            "value": 42,
            "domain": {},
            "metadata": {"key": "value", "num": 123},
        }
        allele = AbstractAllele.deserialize(data)
        assert allele.metadata["key"] == "value"
        assert allele.metadata["num"] == 123

    def test_deserialize_recursively_deserializes_metadata_alleles(self):
        """deserialize() recursively reconstructs alleles in metadata."""
        data = {
            "type": "SimpleAllele",
            "value": 42,
            "domain": {},
            "metadata": {
                "nested": {
                    "type": "SimpleAllele",
                    "value": 100,
                    "domain": {},
                    "metadata": {},
                }
            },
        }
        allele = AbstractAllele.deserialize(data)
        nested = allele.metadata["nested"]
        assert isinstance(nested, SimpleAllele)
        assert nested.value == 100

    def test_deserialize_handles_deeply_nested_alleles(self):
        """deserialize() handles multiple levels of nested alleles."""
        data = {
            "type": "SimpleAllele",
            "value": 1,
            "domain": {},
            "metadata": {
                "child": {
                    "type": "SimpleAllele",
                    "value": 2,
                    "domain": {},
                    "metadata": {
                        "child": {
                            "type": "SimpleAllele",
                            "value": 3,
                            "domain": {},
                            "metadata": {},
                        }
                    },
                }
            },
        }
        level1 = AbstractAllele.deserialize(data)
        level2 = level1.metadata["child"]
        level3 = level2.metadata["child"]

        assert level1.value == 1
        assert level2.value == 2
        assert level3.value == 3


class TestAbstractAlleleSerializationRoundTrip:
    """Test suite for serialization round-trip."""

    def test_round_trip_preserves_value(self):
        """Serialize then deserialize preserves value."""
        original = SimpleAllele(42)
        serialized = original.serialize()
        restored = AbstractAllele.deserialize(serialized)
        assert restored.value == 42

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


class TestAbstractAlleleTreeWalking:
    """Test suite for tree walking stubs."""

    def test_walk_tree_raises_not_implemented(self):
        """walk_tree raises NotImplementedError (stub implementation)."""
        allele = SimpleAllele(42)
        with pytest.raises(NotImplementedError, match="walk_allele_trees not yet implemented"):
            list(allele.walk_tree(lambda nodes: None))

    def test_update_tree_raises_not_implemented(self):
        """update_tree raises NotImplementedError (stub implementation)."""
        allele = SimpleAllele(42)
        with pytest.raises(NotImplementedError, match="synthesize_allele_trees not yet implemented"):
            allele.update_tree(lambda nodes: nodes[0].value)
