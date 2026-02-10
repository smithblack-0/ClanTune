"""
Black-box tests for AbstractMutationStrategy.

Tests mutation orchestration, delegation to handle_mutating hook, and
population/ancestry parameter passing. Uses minimal concrete subclasses.
"""

import pytest
import random
from src.clan_tune.genetics.abstract_strategies import AbstractMutationStrategy
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele


class AdditiveMutation(AbstractMutationStrategy):
    """Test double adding fixed value to alleles."""

    def __init__(self, delta=0.01):
        self.delta = delta

    def handle_mutating(self, allele, population, ancestry):
        """Add delta to value."""
        return allele.with_value(allele.value + self.delta)


class PopulationAwareMutation(AbstractMutationStrategy):
    """Test double using population parameter (differential evolution pattern)."""

    def handle_mutating(self, allele, population, ancestry):
        """Use population mean as perturbation reference."""
        if len(population) < 2:
            return allele

        # Get mean value from population (simplified DE)
        # This requires extracting values from population genomes
        # For testing, just verify population is accessible
        return allele.with_value(allele.value + 0.001)


# AbstractMutationStrategy Tests


def test_mutation_strategy_cannot_instantiate_directly():
    """AbstractMutationStrategy.handle_mutating raises NotImplementedError."""
    strategy = AbstractMutationStrategy()
    allele = FloatAllele(1.0)

    with pytest.raises(NotImplementedError, match="Subclasses must implement handle_mutating"):
        strategy.handle_mutating(allele, [], [])


def test_apply_strategy_delegates_to_handle_mutating():
    """apply_strategy orchestrates by calling handle_mutating hook."""
    strategy = AdditiveMutation(delta=0.1)

    genome = Genome(alleles={"lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0})})
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(1.0, genome.uuid)]

    mutated = strategy.apply_strategy(genome, [genome], ancestry)

    # Value increased by delta
    assert mutated.alleles["lr"].value == pytest.approx(0.11)


def test_apply_strategy_returns_new_genome():
    """apply_strategy returns new genome (new UUID)."""
    strategy = AdditiveMutation(delta=0.01)

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(1.0, genome.uuid)]

    mutated = strategy.apply_strategy(genome, [genome], ancestry)

    # New UUID indicates new genome
    assert mutated.uuid != genome.uuid


def test_apply_strategy_preserves_parents():
    """apply_strategy preserves parents field (doesn't change ancestry)."""
    strategy = AdditiveMutation(delta=0.01)

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    ancestry = [(0.7, genome.uuid), (0.3, genome.uuid)]
    genome = genome.with_overrides(fitness=0.5, parents=ancestry)

    mutated = strategy.apply_strategy(genome, [genome], ancestry)

    # Parents preserved from input genome
    assert mutated.parents == ancestry


def test_apply_strategy_clears_fitness():
    """apply_strategy returns genome with no fitness (needs re-evaluation)."""
    strategy = AdditiveMutation(delta=0.01)

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(1.0, genome.uuid)]

    mutated = strategy.apply_strategy(genome, [genome], ancestry)

    # Fitness cleared
    assert mutated.fitness is None


def test_apply_strategy_processes_can_mutate_alleles_only():
    """apply_strategy only processes alleles with can_mutate=True."""
    strategy = AdditiveMutation(delta=0.1)

    genome = Genome(
        alleles={
            "lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0}, can_mutate=True),
            "wd": FloatAllele(0.001, domain={"min": 0.0, "max": 0.1}, can_mutate=False),
        }
    )
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(1.0, genome.uuid)]

    mutated = strategy.apply_strategy(genome, [genome], ancestry)

    # lr was mutated
    assert mutated.alleles["lr"].value == pytest.approx(0.11)
    # wd was NOT mutated (preserves original value)
    assert mutated.alleles["wd"].value == 0.001


def test_handle_mutating_receives_population_parameter():
    """handle_mutating receives population parameter for population-aware mutations."""

    class InspectingStrategy(AbstractMutationStrategy):
        def __init__(self):
            self.received_population = None

        def handle_mutating(self, allele, population, ancestry):
            self.received_population = population
            return allele

    strategy = InspectingStrategy()

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    ancestry = [(0.6, genome1.uuid), (0.4, genome2.uuid)]

    strategy.apply_strategy(genome1, population, ancestry)

    # Verify population parameter passed through
    assert strategy.received_population == population


def test_handle_mutating_receives_ancestry_parameter():
    """handle_mutating receives ancestry parameter for adaptive mutations."""

    class InspectingStrategy(AbstractMutationStrategy):
        def __init__(self):
            self.received_ancestry = None

        def handle_mutating(self, allele, population, ancestry):
            self.received_ancestry = ancestry
            return allele

    strategy = InspectingStrategy()

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(0.6, genome.uuid), (0.4, genome.uuid)]

    strategy.apply_strategy(genome, [genome], ancestry)

    # Verify ancestry parameter passed through
    assert strategy.received_ancestry == ancestry


def test_handle_mutating_receives_flattened_allele():
    """handle_mutating receives allele with flattened metadata (raw values)."""

    class InspectingStrategy(AbstractMutationStrategy):
        def __init__(self):
            self.received_allele = None

        def handle_mutating(self, allele, population, ancestry):
            self.received_allele = allele
            return allele

    strategy = InspectingStrategy()

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    strategy.apply_strategy(genome, [genome], [(1.0, genome.uuid)])

    # Verify allele received
    assert strategy.received_allele.value == 0.01


def test_mutation_with_multiple_hyperparameters():
    """Mutation processes multiple hyperparameters independently."""
    strategy = AdditiveMutation(delta=0.1)

    genome = Genome(
        alleles={
            "lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0}),
            "wd": FloatAllele(0.001, domain={"min": 0.0, "max": 1.0}),  # Fixed: max allows mutation result
        }
    )
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(1.0, genome.uuid)]

    mutated = strategy.apply_strategy(genome, [genome], ancestry)

    # Both hyperparameters mutated independently
    assert mutated.alleles["lr"].value == pytest.approx(0.11)
    assert mutated.alleles["wd"].value == pytest.approx(0.101)


def test_population_aware_mutation_can_access_population():
    """Population-aware mutations can access population parameter."""
    strategy = PopulationAwareMutation()

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    ancestry = [(0.6, genome1.uuid), (0.4, genome2.uuid)]

    mutated = strategy.apply_strategy(genome1, population, ancestry)

    # Mutation succeeded (used population parameter)
    assert mutated.alleles["lr"].value == pytest.approx(0.011)


def test_simple_mutation_can_ignore_population_ancestry():
    """Simple mutations can ignore population and ancestry parameters."""

    class SimpleMutation(AbstractMutationStrategy):
        def handle_mutating(self, allele, population, ancestry):
            # Ignore population and ancestry
            return allele.with_value(allele.value * 1.1)

    strategy = SimpleMutation()

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    # Pass arbitrary population/ancestry - should be ignored
    mutated = strategy.apply_strategy(genome, [], [])

    # Mutation applied regardless
    assert mutated.alleles["lr"].value == pytest.approx(0.011)


def test_mutation_preserves_allele_structure():
    """Mutation preserves allele domain and flags."""
    strategy = AdditiveMutation(delta=0.1)

    genome = Genome(
        alleles={
            "lr": FloatAllele(
                0.01,
                domain={"min": 0.0, "max": 1.0},
                can_mutate=True,
                can_crossbreed=True,
            )
        }
    )
    genome = genome.with_overrides(fitness=0.5)

    mutated = strategy.apply_strategy(genome, [genome], [(1.0, genome.uuid)])

    # Structure preserved
    assert mutated.alleles["lr"].domain == {"min": 0.0, "max": 1.0}
    assert mutated.alleles["lr"].can_mutate is True
    assert mutated.alleles["lr"].can_crossbreed is True


def test_metadata_get_pattern_works_with_defaults():
    """Mutations can use metadata.get(key, default) pattern safely."""

    class MetadataAwareMutation(AbstractMutationStrategy):
        def __init__(self, default_std=0.1):
            self.default_std = default_std

        def handle_mutating(self, allele, population, ancestry):
            # Use .get pattern for metalearning support
            std = allele.metadata.get("std", self.default_std)
            return allele.with_value(allele.value + std)

    strategy = MetadataAwareMutation(default_std=0.05)

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    mutated = strategy.apply_strategy(genome, [genome], [(1.0, genome.uuid)])

    # Used default std since no metadata
    assert mutated.alleles["lr"].value == pytest.approx(0.06)
