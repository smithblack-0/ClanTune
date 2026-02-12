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
    """Test double demonstrating population-aware mutation using allele values directly."""

    def handle_mutating(self, allele, population, ancestry):
        """Perturb value toward population mean."""
        if len(population) < 2:
            return allele

        # population is List[AbstractAllele] — values accessible without navigating Genome
        mean_value = sum(a.value for a in population) / len(population)
        return allele.with_value(mean_value)


# AbstractMutationStrategy Tests


def test_mutation_strategy_cannot_instantiate_directly():
    """AbstractMutationStrategy cannot be instantiated without implementing handle_mutating."""
    with pytest.raises(TypeError):
        AbstractMutationStrategy()


def test_apply_strategy_delegates_to_handle_mutating():
    """apply_strategy orchestrates by calling handle_mutating hook."""
    strategy = AdditiveMutation(delta=0.1)

    genome = Genome(alleles={"lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0})})
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(1.0, genome.uuid)]

    mutated = strategy.apply_strategy(genome, [genome], ancestry)

    # Value increased by delta
    assert mutated.alleles["lr"].value == pytest.approx(0.11)



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


def test_handle_mutating_receives_allele_population():
    """handle_mutating receives allele_population: parallel AbstractAlleles from population at same tree position."""

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

    # Received alleles, not Genome objects
    assert len(strategy.received_population) == len(population)
    assert all(isinstance(a, FloatAllele) for a in strategy.received_population)
    # Values correspond to population members' lr alleles in population order
    assert strategy.received_population[0].value == pytest.approx(0.01)
    assert strategy.received_population[1].value == pytest.approx(0.02)


def test_allele_population_excludes_genome_being_mutated():
    """allele_population does not include the allele from the genome being mutated.

    This is critical for DifferentialEvolution: the three donor vectors must be
    drawn from the population, not the offspring being mutated.
    """

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

    # offspring is separate from the parent population (as in StrategyOrchestrator)
    offspring = Genome(alleles={"lr": FloatAllele(0.015)})

    population = [genome1, genome2]
    ancestry = [(0.6, genome1.uuid), (0.4, genome2.uuid)]

    strategy.apply_strategy(offspring, population, ancestry)

    # allele_population has one entry per population member, not population+1
    assert len(strategy.received_population) == len(population)
    # offspring's allele value (0.015) is absent
    population_values = [a.value for a in strategy.received_population]
    assert pytest.approx(0.015) not in population_values
    # Parent population values are present
    assert population_values[0] == pytest.approx(0.01)
    assert population_values[1] == pytest.approx(0.02)


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
    """Population-aware mutations can read allele values directly from allele_population."""
    strategy = PopulationAwareMutation()

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    ancestry = [(0.6, genome1.uuid), (0.4, genome2.uuid)]

    offspring = Genome(alleles={"lr": FloatAllele(0.01)})
    mutated = strategy.apply_strategy(offspring, population, ancestry)

    # Result is mean of population allele values: (0.01 + 0.02) / 2 = 0.015
    assert mutated.alleles["lr"].value == pytest.approx(0.015)


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
