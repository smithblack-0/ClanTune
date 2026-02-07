"""
Test suite for Genome serialization and deserialization.

Tests round-trip preservation of UUID, alleles, parents, fitness, and nested alleles.
All tests use black-box methodology - no inspection of serialization schema.
"""

import pytest
from uuid import UUID
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele, IntAllele, LogFloatAllele, BoolAllele, StringAllele


class TestGenomeSerialization:
    """Test genome serialize/deserialize round-trip preservation."""

    def test_empty_genome_round_trip(self):
        """Empty genome survives serialization round-trip."""
        genome = Genome()

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.uuid == genome.uuid
        assert restored.alleles == {}
        assert restored.parents is None
        assert restored.fitness is None

    def test_genome_with_single_allele_round_trip(self):
        """Genome with one allele survives round-trip."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float", domain={"min": 0.0, "max": 1.0})

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.uuid == genome.uuid
        assert "lr" in restored.alleles
        assert restored.alleles["lr"].value == 0.01
        assert restored.alleles["lr"].domain == {"min": 0.0, "max": 1.0}

    def test_genome_with_multiple_allele_types_round_trip(self):
        """Genome with multiple allele types survives round-trip."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")
        genome = genome.add_hyperparameter("batch_size", 32, "int")
        genome = genome.add_hyperparameter("nesterov", True, "bool")
        genome = genome.add_hyperparameter("optimizer", "adam", "string", domain={"adam", "sgd"})

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.uuid == genome.uuid
        hyperparams = restored.as_hyperparameters()
        assert hyperparams == {
            "lr": 0.01,
            "batch_size": 32,
            "nesterov": True,
            "optimizer": "adam"
        }

    def test_genome_with_parents_round_trip(self):
        """Genome with parent ancestry survives round-trip."""
        parent_uuid1 = UUID("11111111-1111-1111-1111-111111111111")
        parent_uuid2 = UUID("22222222-2222-2222-2222-222222222222")
        parents = [(0.7, parent_uuid1), (0.3, parent_uuid2)]

        genome = Genome(parents=parents)

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.parents == parents

    def test_genome_with_fitness_round_trip(self):
        """Genome with fitness survives round-trip."""
        genome = Genome(fitness=0.85)

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.fitness == 0.85

    def test_full_genome_round_trip(self):
        """Genome with all fields populated survives round-trip."""
        # Create genome with everything
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")
        genome = genome.add_hyperparameter("wd", 0.001, "float")

        parent_uuid = UUID("11111111-1111-1111-1111-111111111111")
        genome = genome.with_overrides(parents=[(1.0, parent_uuid)])
        genome = genome.set_fitness(0.95)

        original_uuid = genome.uuid

        data = genome.serialize()
        restored = Genome.deserialize(data)

        # Verify all fields preserved
        assert restored.uuid == original_uuid
        assert restored.as_hyperparameters() == {"lr": 0.01, "wd": 0.001}
        assert restored.parents == [(1.0, parent_uuid)]
        assert restored.fitness == 0.95

    def test_nested_alleles_round_trip(self):
        """Genome with nested alleles (metadata containing alleles) survives round-trip."""
        # Create allele with nested metadata allele
        lr_allele = FloatAllele(
            0.01,
            domain={"min": 0.0, "max": 1.0},
            metadata={
                "mutation_std": FloatAllele(0.001, domain={"min": 0.0, "max": 0.1}),
                "mutation_chance": 0.15  # Raw value
            }
        )

        genome = Genome(alleles={"lr": lr_allele})

        data = genome.serialize()
        restored = Genome.deserialize(data)

        # Verify nested structure preserved
        restored_lr = restored.alleles["lr"]
        assert restored_lr.value == 0.01
        assert "mutation_std" in restored_lr.metadata
        assert isinstance(restored_lr.metadata["mutation_std"], FloatAllele)
        assert restored_lr.metadata["mutation_std"].value == 0.001
        assert restored_lr.metadata["mutation_chance"] == 0.15

    def test_logfloat_allele_round_trip(self):
        """LogFloatAllele in genome survives round-trip."""
        genome = Genome()
        genome = genome.add_hyperparameter(
            "lr",
            0.001,
            "logfloat",
            domain={"min": 1e-5, "max": 1.0}
        )

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.alleles["lr"].value == 0.001
        assert isinstance(restored.alleles["lr"], LogFloatAllele)

    def test_uuid_preservation_exact(self):
        """Deserialization preserves exact UUID."""
        explicit_uuid = UUID("12345678-1234-5678-1234-567812345678")
        genome = Genome(uuid=explicit_uuid)

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.uuid == explicit_uuid
        assert str(restored.uuid) == str(explicit_uuid)

    def test_serialization_is_dict(self):
        """serialize() returns a dict (for JSON compatibility)."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")

        data = genome.serialize()

        assert isinstance(data, dict)

    def test_none_fitness_round_trip(self):
        """Genome with explicitly None fitness survives round-trip."""
        genome = Genome(fitness=None)

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.fitness is None

    def test_zero_probability_parents_round_trip(self):
        """Parents with 0.0 probability survive round-trip."""
        parent_uuid1 = UUID("11111111-1111-1111-1111-111111111111")
        parent_uuid2 = UUID("22222222-2222-2222-2222-222222222222")
        parents = [(0.0, parent_uuid1), (1.0, parent_uuid2)]

        genome = Genome(parents=parents)

        data = genome.serialize()
        restored = Genome.deserialize(data)

        assert restored.parents == parents

    def test_multiple_nested_levels_round_trip(self):
        """Genome with multiple levels of nested alleles survives round-trip."""
        # Create deeply nested allele structure
        deep_std = FloatAllele(
            0.05,
            metadata={"mutation_chance": 0.1}  # Level 3
        )
        mid_std = FloatAllele(
            0.01,
            metadata={
                "std": deep_std,  # Level 2 containing Level 3
                "mutation_chance": 0.15
            }
        )
        lr_allele = FloatAllele(
            0.1,
            metadata={
                "std": mid_std,  # Level 1 containing Level 2
                "mutation_chance": 0.2
            }
        )

        genome = Genome(alleles={"lr": lr_allele})

        data = genome.serialize()
        restored = Genome.deserialize(data)

        # Verify deep nesting preserved
        restored_lr = restored.alleles["lr"]
        assert restored_lr.value == 0.1
        assert restored_lr.metadata["mutation_chance"] == 0.2

        mid_level = restored_lr.metadata["std"]
        assert isinstance(mid_level, FloatAllele)
        assert mid_level.value == 0.01
        assert mid_level.metadata["mutation_chance"] == 0.15

        deep_level = mid_level.metadata["std"]
        assert isinstance(deep_level, FloatAllele)
        assert deep_level.value == 0.05
        assert deep_level.metadata["mutation_chance"] == 0.1


class TestSerializationContract:
    """Test serialization contract requirements."""

    def test_serialize_then_deserialize_is_identity(self):
        """serialize() followed by deserialize() recreates equivalent genome."""
        # Create complex genome
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")
        genome = genome.add_hyperparameter("wd", 0.001, "float")
        genome = genome.set_fitness(0.85)

        # Round-trip
        restored = Genome.deserialize(genome.serialize())

        # Test equivalence via observable behavior
        assert restored.uuid == genome.uuid
        assert restored.as_hyperparameters() == genome.as_hyperparameters()
        assert restored.parents == genome.parents
        assert restored.fitness == genome.fitness

    def test_deserialize_reconstructs_allele_types(self):
        """Deserialization reconstructs correct allele types."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")
        genome = genome.add_hyperparameter("bs", 32, "int")
        genome = genome.add_hyperparameter("use_nesterov", True, "bool")

        restored = Genome.deserialize(genome.serialize())

        # Verify types via isinstance (observable via public alleles property)
        assert isinstance(restored.alleles["lr"], FloatAllele)
        assert isinstance(restored.alleles["bs"], IntAllele)
        assert isinstance(restored.alleles["use_nesterov"], BoolAllele)
