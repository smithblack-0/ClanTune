"""
Test suite for Genome construction and orchestrator methods.

Tests genome construction, property access, immutability, string-based type dispatch,
and orchestrator methods (add_hyperparameter, as_hyperparameters, set_fitness, get_fitness).
"""

import pytest
from uuid import UUID
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele, IntAllele, LogFloatAllele, BoolAllele, StringAllele


class TestGenomeConstruction:
    """Test genome construction and property access."""

    def test_empty_genome_construction(self):
        """Empty genome has generated UUID, empty alleles, no parents, no fitness."""
        genome = Genome()

        assert isinstance(genome.uuid, UUID)
        assert genome.alleles == {}
        assert genome.parents is None
        assert genome.fitness is None

    def test_construction_with_explicit_uuid(self):
        """Genome constructed with explicit UUID preserves that UUID."""
        explicit_uuid = UUID("12345678-1234-5678-1234-567812345678")
        genome = Genome(uuid=explicit_uuid)

        assert genome.uuid == explicit_uuid

    def test_construction_with_alleles(self):
        """Genome constructed with alleles dict stores those alleles."""
        alleles = {"lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0})}
        genome = Genome(alleles=alleles)

        assert genome.alleles == alleles
        assert "lr" in genome.alleles

    def test_construction_with_parents(self):
        """Genome constructed with parents preserves ancestry."""
        parent_uuid1 = UUID("11111111-1111-1111-1111-111111111111")
        parent_uuid2 = UUID("22222222-2222-2222-2222-222222222222")
        parents = [(0.7, parent_uuid1), (0.3, parent_uuid2)]
        genome = Genome(parents=parents)

        assert genome.parents == parents

    def test_construction_with_fitness(self):
        """Genome constructed with fitness preserves that fitness."""
        genome = Genome(fitness=0.95)

        assert genome.fitness == 0.95

    def test_full_construction(self):
        """Genome constructed with all fields preserves all fields."""
        explicit_uuid = UUID("12345678-1234-5678-1234-567812345678")
        alleles = {"lr": FloatAllele(0.01)}
        parents = [(1.0, UUID("11111111-1111-1111-1111-111111111111"))]
        fitness = 0.85

        genome = Genome(uuid=explicit_uuid, alleles=alleles, parents=parents, fitness=fitness)

        assert genome.uuid == explicit_uuid
        assert genome.alleles == alleles
        assert genome.parents == parents
        assert genome.fitness == fitness


class TestWithOverrides:
    """Test with_overrides rebuilding method."""

    def test_with_overrides_preserves_uuid_by_default(self):
        """with_overrides preserves UUID when not specified."""
        genome = Genome()
        original_uuid = genome.uuid

        rebuilt = genome.with_overrides(fitness=0.9)

        assert rebuilt.uuid == original_uuid

    def test_with_overrides_can_change_uuid(self):
        """with_overrides can explicitly change UUID."""
        genome = Genome()
        original_uuid = genome.uuid
        new_uuid = UUID("12345678-1234-5678-1234-567812345678")

        rebuilt = genome.with_overrides(uuid=new_uuid)

        assert rebuilt.uuid == new_uuid
        assert rebuilt.uuid != original_uuid

    def test_with_overrides_preserves_other_fields(self):
        """with_overrides preserves fields not being overridden."""
        alleles = {"lr": FloatAllele(0.01)}
        parents = [(1.0, UUID("11111111-1111-1111-1111-111111111111"))]
        genome = Genome(alleles=alleles, parents=parents, fitness=0.8)

        # Override only fitness
        rebuilt = genome.with_overrides(fitness=0.9)

        assert rebuilt.alleles == alleles
        assert rebuilt.parents == parents
        assert rebuilt.fitness == 0.9

    def test_with_overrides_is_immutable(self):
        """with_overrides returns new genome, leaves original unchanged."""
        genome = Genome(fitness=0.5)
        original_fitness = genome.fitness

        rebuilt = genome.with_overrides(fitness=0.9)

        assert genome.fitness == original_fitness  # Original unchanged
        assert rebuilt.fitness == 0.9  # New genome has new value


class TestAddHyperparameter:
    """Test add_hyperparameter method with string-based type dispatch."""

    def test_add_float_hyperparameter(self):
        """add_hyperparameter dispatches to FloatAllele for 'float' type."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float", domain={"min": 0.0, "max": 1.0})

        assert "lr" in genome.alleles
        assert isinstance(genome.alleles["lr"], FloatAllele)
        assert genome.alleles["lr"].value == 0.01

    def test_add_int_hyperparameter(self):
        """add_hyperparameter dispatches to IntAllele for 'int' type."""
        genome = Genome()
        genome = genome.add_hyperparameter("batch_size", 32, "int", domain={"min": 1, "max": 512})

        assert "batch_size" in genome.alleles
        assert isinstance(genome.alleles["batch_size"], IntAllele)
        assert genome.alleles["batch_size"].value == 32

    def test_add_logfloat_hyperparameter(self):
        """add_hyperparameter dispatches to LogFloatAllele for 'logfloat' type."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.001, "logfloat", domain={"min": 1e-5, "max": 1.0})

        assert "lr" in genome.alleles
        assert isinstance(genome.alleles["lr"], LogFloatAllele)
        assert genome.alleles["lr"].value == 0.001

    def test_add_bool_hyperparameter(self):
        """add_hyperparameter dispatches to BoolAllele for 'bool' type."""
        genome = Genome()
        genome = genome.add_hyperparameter("nesterov", True, "bool")

        assert "nesterov" in genome.alleles
        assert isinstance(genome.alleles["nesterov"], BoolAllele)
        assert genome.alleles["nesterov"].value is True

    def test_add_string_hyperparameter(self):
        """add_hyperparameter dispatches to StringAllele for 'string' type."""
        genome = Genome()
        genome = genome.add_hyperparameter("optimizer", "adam", "string", domain={"adam", "sgd"})

        assert "optimizer" in genome.alleles
        assert isinstance(genome.alleles["optimizer"], StringAllele)
        assert genome.alleles["optimizer"].value == "adam"

    def test_add_hyperparameter_generates_new_uuid(self):
        """add_hyperparameter generates new UUID."""
        genome = Genome()
        original_uuid = genome.uuid

        genome = genome.add_hyperparameter("lr", 0.01, "float")

        assert genome.uuid != original_uuid

    def test_add_hyperparameter_preserves_existing_alleles(self):
        """add_hyperparameter preserves existing hyperparameters."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")
        genome = genome.add_hyperparameter("wd", 0.001, "float")

        assert "lr" in genome.alleles
        assert "wd" in genome.alleles
        assert genome.alleles["lr"].value == 0.01
        assert genome.alleles["wd"].value == 0.001

    def test_add_hyperparameter_preserves_parents(self):
        """add_hyperparameter preserves parent ancestry."""
        parents = [(1.0, UUID("11111111-1111-1111-1111-111111111111"))]
        genome = Genome(parents=parents)

        genome = genome.add_hyperparameter("lr", 0.01, "float")

        assert genome.parents == parents

    def test_add_hyperparameter_preserves_fitness(self):
        """add_hyperparameter preserves fitness."""
        genome = Genome(fitness=0.85)

        genome = genome.add_hyperparameter("lr", 0.01, "float")

        assert genome.fitness == 0.85

    def test_add_hyperparameter_with_allele_kwargs(self):
        """add_hyperparameter forwards kwargs to allele constructor."""
        genome = Genome()
        genome = genome.add_hyperparameter(
            "lr",
            0.01,
            "float",
            domain={"min": 0.0, "max": 1.0},
            can_mutate=False,
            can_crossbreed=True
        )

        allele = genome.alleles["lr"]
        assert allele.domain == {"min": 0.0, "max": 1.0}
        assert allele.can_mutate is False
        assert allele.can_crossbreed is True

    def test_add_hyperparameter_invalid_type_raises_error(self):
        """add_hyperparameter raises KeyError for invalid type string."""
        genome = Genome()

        with pytest.raises(KeyError):
            genome.add_hyperparameter("lr", 0.01, "invalid_type")


class TestAsHyperparameters:
    """Test as_hyperparameters extraction method."""

    def test_as_hyperparameters_empty_genome(self):
        """as_hyperparameters returns empty dict for empty genome."""
        genome = Genome()

        hyperparams = genome.as_hyperparameters()

        assert hyperparams == {}

    def test_as_hyperparameters_extracts_values(self):
        """as_hyperparameters returns values, not alleles."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")
        genome = genome.add_hyperparameter("wd", 0.001, "float")

        hyperparams = genome.as_hyperparameters()

        assert hyperparams == {"lr": 0.01, "wd": 0.001}
        assert not isinstance(hyperparams["lr"], FloatAllele)  # Values, not alleles

    def test_as_hyperparameters_multiple_types(self):
        """as_hyperparameters extracts values from different allele types."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.01, "float")
        genome = genome.add_hyperparameter("batch_size", 32, "int")
        genome = genome.add_hyperparameter("nesterov", True, "bool")
        genome = genome.add_hyperparameter("optimizer", "adam", "string", domain={"adam", "sgd"})

        hyperparams = genome.as_hyperparameters()

        assert hyperparams == {
            "lr": 0.01,
            "batch_size": 32,
            "nesterov": True,
            "optimizer": "adam"
        }


class TestSetAndGetFitness:
    """Test set_fitness and get_fitness methods."""

    def test_get_fitness_unassigned(self):
        """get_fitness returns None for genome without fitness."""
        genome = Genome()

        assert genome.get_fitness() is None

    def test_set_fitness_assigns_value(self):
        """set_fitness assigns fitness value."""
        genome = Genome()
        genome = genome.set_fitness(0.85)

        assert genome.get_fitness() == 0.85

    def test_set_fitness_preserves_uuid_by_default(self):
        """set_fitness preserves UUID by default."""
        genome = Genome()
        original_uuid = genome.uuid

        genome = genome.set_fitness(0.85)

        assert genome.uuid == original_uuid

    def test_set_fitness_with_new_uuid(self):
        """set_fitness with new_uuid=True generates new UUID."""
        genome = Genome()
        original_uuid = genome.uuid

        genome = genome.set_fitness(0.85, new_uuid=True)

        assert genome.uuid != original_uuid
        assert genome.get_fitness() == 0.85

    def test_set_fitness_preserves_other_fields(self):
        """set_fitness preserves alleles and parents."""
        alleles = {"lr": FloatAllele(0.01)}
        parents = [(1.0, UUID("11111111-1111-1111-1111-111111111111"))]
        genome = Genome(alleles=alleles, parents=parents)

        genome = genome.set_fitness(0.85)

        assert genome.alleles == alleles
        assert genome.parents == parents

    def test_set_fitness_is_immutable(self):
        """set_fitness returns new genome, leaves original unchanged."""
        genome = Genome()

        new_genome = genome.set_fitness(0.85)

        assert genome.get_fitness() is None  # Original unchanged
        assert new_genome.get_fitness() == 0.85


class TestMetadata:
    """Test genome-level metadata storage."""

    def test_default_metadata_empty(self):
        """Genome constructed without metadata has empty dict."""
        genome = Genome()
        assert genome.metadata == {}

    def test_construction_with_metadata(self):
        """Genome constructed with metadata preserves it."""
        genome = Genome(metadata={"key": "value"})
        assert genome.metadata == {"key": "value"}

    def test_set_metadata_adds_key(self):
        """set_metadata returns new genome with key set."""
        genome = Genome()
        genome = genome.set_metadata("expression_config", {"lr_path": "optimizer/0/lr"})
        assert genome.get_metadata("expression_config") == {"lr_path": "optimizer/0/lr"}

    def test_set_metadata_preserves_uuid(self):
        """set_metadata preserves UUID."""
        genome = Genome()
        original_uuid = genome.uuid
        genome = genome.set_metadata("key", "value")
        assert genome.uuid == original_uuid

    def test_set_metadata_preserves_existing_keys(self):
        """set_metadata preserves other metadata keys."""
        genome = Genome(metadata={"a": 1})
        genome = genome.set_metadata("b", 2)
        assert genome.get_metadata("a") == 1
        assert genome.get_metadata("b") == 2

    def test_set_metadata_overwrites_existing_key(self):
        """set_metadata overwrites value for existing key."""
        genome = Genome(metadata={"key": "old"})
        genome = genome.set_metadata("key", "new")
        assert genome.get_metadata("key") == "new"

    def test_get_metadata_missing_key_raises(self):
        """get_metadata raises KeyError for absent key."""
        genome = Genome()
        with pytest.raises(KeyError):
            genome.get_metadata("nonexistent")

    def test_set_metadata_is_immutable(self):
        """set_metadata returns new genome, leaves original unchanged."""
        genome1 = Genome()
        genome2 = genome1.set_metadata("key", "value")
        assert genome1.metadata == {}
        assert genome2.get_metadata("key") == "value"

    def test_with_overrides_preserves_metadata(self):
        """with_overrides preserves metadata when not overridden."""
        genome = Genome(metadata={"key": "value"}, fitness=0.5)
        rebuilt = genome.with_overrides(fitness=0.9)
        assert rebuilt.get_metadata("key") == "value"

    def test_with_overrides_can_replace_metadata(self):
        """with_overrides can replace metadata."""
        genome = Genome(metadata={"old": 1})
        rebuilt = genome.with_overrides(metadata={"new": 2})
        assert rebuilt.metadata == {"new": 2}


class TestImmutability:
    """Test immutability guarantees across all operations."""

    def test_add_hyperparameter_immutability(self):
        """add_hyperparameter leaves original genome unchanged."""
        genome1 = Genome()
        genome2 = genome1.add_hyperparameter("lr", 0.01, "float")

        assert genome1.alleles == {}
        assert "lr" in genome2.alleles
