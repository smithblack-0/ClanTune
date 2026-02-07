"""
Comprehensive integration tests for Genome system.

Tests multi-hyperparameter scenarios, nested alleles, error handling, complex
predicate filtering, and full end-to-end workflows.
"""

import pytest
from uuid import UUID
from src.clan_tune.genetics.genome import Genome, walk_genome_alleles, synthesize_genomes
from src.clan_tune.genetics.alleles import FloatAllele, IntAllele, LogFloatAllele, BoolAllele, StringAllele, CanMutateFilter, CanCrossbreedFilter


class TestMultiHyperparameterScenarios:
    """Test scenarios with multiple hyperparameters of different types."""

    def test_full_optimizer_config_genome(self):
        """Create genome representing full optimizer configuration."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.001, "logfloat", domain={"min": 1e-5, "max": 1.0})
        genome = genome.add_hyperparameter("weight_decay", 0.01, "float", domain={"min": 0.0, "max": 0.1})
        genome = genome.add_hyperparameter("batch_size", 32, "int", domain={"min": 1, "max": 512})
        genome = genome.add_hyperparameter("use_nesterov", True, "bool")
        genome = genome.add_hyperparameter("optimizer", "adam", "string", domain={"adam", "sgd", "rmsprop"})

        hyperparams = genome.as_hyperparameters()

        assert hyperparams["lr"] == 0.001
        assert hyperparams["weight_decay"] == 0.01
        assert hyperparams["batch_size"] == 32
        assert hyperparams["use_nesterov"] is True
        assert hyperparams["optimizer"] == "adam"

    def test_serialization_preserves_complex_genome(self):
        """Complex genome with multiple types survives serialization."""
        genome = Genome()
        genome = genome.add_hyperparameter("lr", 0.001, "logfloat", domain={"min": 1e-5, "max": 1.0})
        genome = genome.add_hyperparameter("batch_size", 32, "int", domain={"min": 1, "max": 512})
        genome = genome.add_hyperparameter("optimizer", "adam", "string", domain={"adam", "sgd"})
        genome = genome.set_fitness(0.95)

        parent_uuid = UUID("11111111-1111-1111-1111-111111111111")
        genome = genome.with_overrides(parents=[(1.0, parent_uuid)])

        # Round-trip
        restored = Genome.deserialize(genome.serialize())

        # Verify everything preserved
        assert restored.uuid == genome.uuid
        assert restored.as_hyperparameters() == genome.as_hyperparameters()
        assert restored.parents == genome.parents
        assert restored.fitness == genome.fitness

        # Verify types preserved
        assert isinstance(restored.alleles["lr"], LogFloatAllele)
        assert isinstance(restored.alleles["batch_size"], IntAllele)
        assert isinstance(restored.alleles["optimizer"], StringAllele)


class TestNestedAlleleScenarios:
    """Test scenarios with deeply nested metadata alleles."""

    def test_three_level_metalearning_hierarchy(self):
        """Create three-level metalearning hierarchy."""
        # Level 3: std's std
        std_std = FloatAllele(0.01, domain={"min": 0.001, "max": 0.1})

        # Level 2: lr's std with its own std
        lr_std = FloatAllele(
            0.1,
            domain={"min": 0.01, "max": 1.0},
            metadata={"std": std_std, "mutation_chance": 0.1}
        )

        # Level 1: lr with nested std
        lr_allele = FloatAllele(
            0.01,
            domain={"min": 1e-5, "max": 1.0},
            metadata={"std": lr_std, "mutation_chance": 0.2}
        )

        genome = Genome(alleles={"lr": lr_allele})

        # Verify structure via serialization round-trip
        restored = Genome.deserialize(genome.serialize())

        # Navigate down the hierarchy
        lr = restored.alleles["lr"]
        assert lr.value == 0.01
        assert lr.metadata["mutation_chance"] == 0.2

        std = lr.metadata["std"]
        assert isinstance(std, FloatAllele)
        assert std.value == 0.1
        assert std.metadata["mutation_chance"] == 0.1

        std_std = std.metadata["std"]
        assert isinstance(std_std, FloatAllele)
        assert std_std.value == 0.01

    def test_update_alleles_walks_nested_structure(self):
        """update_alleles walks and updates nested alleles."""
        lr_std = FloatAllele(0.1, metadata={"mutation_chance": 0.1})
        lr_allele = FloatAllele(0.01, metadata={"std": lr_std})
        genome = Genome(alleles={"lr": lr_allele})

        # Multiply all float values by 10
        def multiply_by_10(allele):
            if isinstance(allele, FloatAllele):
                return allele.with_value(allele.value * 10)
            return allele

        result = genome.update_alleles(multiply_by_10)

        # All levels should be multiplied
        assert result.alleles["lr"].value == 0.1
        assert result.alleles["lr"].metadata["std"].value == 1.0
        # Raw value unchanged
        assert result.alleles["lr"].metadata["std"].metadata["mutation_chance"] == 0.1

    def test_synthesize_with_nested_alleles_across_population(self):
        """synthesize_genomes handles nested alleles across population."""
        # Create two genomes with nested structures
        lr1 = FloatAllele(0.01, metadata={"std": FloatAllele(0.1)})
        genome1 = Genome(alleles={"lr": lr1})

        lr2 = FloatAllele(0.02, metadata={"std": FloatAllele(0.2)})
        genome2 = Genome(alleles={"lr": lr2})

        # Average all values
        def average(template, sources):
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        result = synthesize_genomes(genome1, [genome1, genome2], average)

        # Both lr and nested std should be averaged
        assert result.alleles["lr"].value == pytest.approx(0.015)
        assert result.alleles["lr"].metadata["std"].value == pytest.approx(0.15)


class TestErrorHandling:
    """Test error messages and validation."""

    def test_invalid_allele_type_string_raises_clear_error(self):
        """add_hyperparameter with invalid type string raises KeyError."""
        genome = Genome()

        with pytest.raises(KeyError):
            genome.add_hyperparameter("lr", 0.01, "invalid_type")

    def test_walk_mismatched_schemas_raises_error(self):
        """walk_genome_alleles raises error for mismatched hyperparameter keys."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("different_key", 0.02, "float")

        with pytest.raises(ValueError, match="same hyperparameter keys"):
            list(walk_genome_alleles([genome1, genome2], lambda a: a[0].value))

    def test_synthesize_main_genome_not_in_population_raises_error(self):
        """synthesize_genomes raises error if main_genome not in population."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        with pytest.raises(ValueError, match="main_genome must be present"):
            synthesize_genomes(genome1, [genome2], lambda t, s: t)

    def test_synthesize_empty_population_raises_error(self):
        """synthesize_genomes raises error for empty population."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")

        with pytest.raises(ValueError, match="non-empty population"):
            synthesize_genomes(genome, [], lambda t, s: t)

    def test_type_mismatch_in_walk_raises_error(self):
        """walk_genome_alleles raises TypeError for type mismatches."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 32, "int")

        # Different types at same hyperparameter
        with pytest.raises(TypeError):
            list(walk_genome_alleles([genome1, genome2], lambda a: a[0].value))


class TestComplexPredicateFiltering:
    """Test complex predicate filtering scenarios."""

    def test_filter_different_flags_independently(self):
        """Test filtering by can_mutate and can_crossbreed independently."""
        genome1 = Genome()
        genome1 = genome1.add_hyperparameter("lr", 0.01, "float", can_mutate=True, can_crossbreed=True)
        genome1 = genome1.add_hyperparameter("wd", 0.001, "float", can_mutate=True, can_crossbreed=False)
        genome1 = genome1.add_hyperparameter("bs", 32, "int", can_mutate=False, can_crossbreed=True)

        genome2 = Genome()
        genome2 = genome2.add_hyperparameter("lr", 0.02, "float", can_mutate=True, can_crossbreed=True)
        genome2 = genome2.add_hyperparameter("wd", 0.002, "float", can_mutate=True, can_crossbreed=False)
        genome2 = genome2.add_hyperparameter("bs", 64, "int", can_mutate=False, can_crossbreed=True)

        # Filter by can_mutate=True
        def double(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_genomes(
            genome1,
            [genome1, genome2],
            double,
            predicate=CanMutateFilter(True)
        )

        hyperparams = result.as_hyperparameters()
        # lr and wd should be doubled (can_mutate=True)
        assert hyperparams["lr"] == 0.02
        assert hyperparams["wd"] == 0.002
        # bs unchanged (can_mutate=False, filtered out)
        assert hyperparams["bs"] == 32

        # Filter by can_crossbreed=True
        result2 = synthesize_genomes(
            genome1,
            [genome1, genome2],
            double,
            predicate=CanCrossbreedFilter(True)
        )

        hyperparams2 = result2.as_hyperparameters()
        # lr and bs should be doubled (can_crossbreed=True)
        assert hyperparams2["lr"] == 0.02
        assert hyperparams2["bs"] == 64
        # wd unchanged (can_crossbreed=False, filtered out)
        assert hyperparams2["wd"] == 0.001

    def test_nested_alleles_respect_predicates(self):
        """Predicates filter at all levels of nested structure."""
        # Nested structure with different flags
        lr_std = FloatAllele(0.1, can_mutate=True)
        lr_allele = FloatAllele(0.01, can_mutate=False, metadata={"std": lr_std})
        genome = Genome(alleles={"lr": lr_allele})

        def double(allele):
            return allele.with_value(allele.value * 2)

        result = genome.update_alleles(double, predicate=CanMutateFilter(True))

        # lr unchanged (can_mutate=False)
        assert result.alleles["lr"].value == 0.01
        # But nested std is doubled (can_mutate=True)
        assert result.alleles["lr"].metadata["std"].value == 0.2


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    def test_full_evolution_cycle(self):
        """Simulate full evolution cycle: setup -> evaluate -> crossbreed -> mutate."""
        # Initial population setup
        genome1 = Genome()
        genome1 = genome1.add_hyperparameter("lr", 0.01, "float", can_mutate=True, can_crossbreed=True)
        genome1 = genome1.add_hyperparameter("wd", 0.001, "float", can_mutate=True, can_crossbreed=True)

        genome2 = Genome()
        genome2 = genome2.add_hyperparameter("lr", 0.02, "float", can_mutate=True, can_crossbreed=True)
        genome2 = genome2.add_hyperparameter("wd", 0.002, "float", can_mutate=True, can_crossbreed=True)

        # Evaluate (assign fitness)
        genome1 = genome1.set_fitness(0.9)
        genome2 = genome2.set_fitness(0.85)

        population = [genome1, genome2]

        # Crossbreed: create offspring
        def weighted_average(template, sources):
            # Weight by fitness (would normally be computed from self.parents)
            # For this test, simple average
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        offspring = genome1.synthesize_new_alleles(
            population,
            weighted_average,
            predicate=CanCrossbreedFilter(True)
        )

        # Add ancestry
        ancestry = [(0.6, genome1.uuid), (0.4, genome2.uuid)]
        offspring = offspring.with_ancestry(ancestry)

        # Mutate
        def mutate(allele):
            return allele.with_value(allele.value * 1.1)

        mutated = offspring.update_alleles(mutate, predicate=CanMutateFilter(True))

        # Verify final state
        hyperparams = mutated.as_hyperparameters()
        # Values should be averaged (0.015, 0.0015) then mutated (×1.1)
        assert hyperparams["lr"] == pytest.approx(0.0165)
        assert hyperparams["wd"] == pytest.approx(0.00165)

        # Offspring ready for evaluation (no fitness)
        assert mutated.fitness is None

    def test_population_synchronization_workflow(self):
        """Test synchronizing population to shared values."""
        # Population with different values
        genomes = [
            Genome().add_hyperparameter("lr", 0.01, "float"),
            Genome().add_hyperparameter("lr", 0.02, "float"),
            Genome().add_hyperparameter("lr", 0.03, "float"),
        ]

        # Extract average across population
        def compute_average(alleles):
            return sum(a.value for a in alleles) / len(alleles)

        averages = list(walk_genome_alleles(genomes, compute_average))
        avg_lr = averages[0]

        # Apply average to all genomes
        def set_to_average(allele, target_value):
            return allele.with_value(target_value)

        synchronized = [
            genome.update_alleles(set_to_average, target_value=avg_lr)
            for genome in genomes
        ]

        # All genomes now have same lr value
        assert all(g.as_hyperparameters()["lr"] == 0.02 for g in synchronized)

    def test_progressive_metalearning_evolution(self):
        """Test evolution of all alleles over generations including nested ones."""
        # Initial genome with metalearning
        lr_std = FloatAllele(0.1, can_mutate=True, domain={"min": 0.01, "max": 1.0})
        lr = FloatAllele(0.01, can_mutate=True, metadata={"std": lr_std}, domain={"min": 1e-5, "max": 1.0})
        genome = Genome(alleles={"lr": lr})

        # Reduce ALL alleles by 10% each generation (recursive)
        def reduce_all(allele):
            return allele.with_value(allele.value * 0.9)

        # Evolve over 5 generations
        for generation in range(5):
            genome = genome.update_alleles(reduce_all)

        # Both lr and its nested std should have decreased
        final_lr = genome.alleles["lr"].value
        final_std = genome.alleles["lr"].metadata["std"].value

        assert final_lr == pytest.approx(0.01 * (0.9 ** 5))
        assert final_std == pytest.approx(0.1 * (0.9 ** 5))
