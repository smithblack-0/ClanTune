"""
Black-box tests for AbstractAncestryStrategy.

Tests parent selection orchestration, validation, and contracts. Uses minimal
concrete subclass for testing abstract functionality.
"""

import pytest
from src.clan_tune.genetics.abstract_strategies import AbstractAncestryStrategy
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele


class MinimalAncestryStrategy(AbstractAncestryStrategy):
    """
    Test double implementing simplest possible ancestry selection.

    Returns 100% probability for my_genome, 0% for all others.
    """

    def select_ancestry(self, my_genome, population):
        """Minimal implementation: self-reproduce."""
        ancestry = []
        for genome in population:
            if genome == my_genome:
                prob = 1.0
            else:
                prob = 0.0
            ancestry.append((prob, genome.uuid))
        return ancestry


class EqualAncestryStrategy(AbstractAncestryStrategy):
    """Test double that assigns equal probability to all genomes."""

    def select_ancestry(self, my_genome, population):
        """Equal probability for all members."""
        prob = 1.0 / len(population)
        return [(prob, genome.uuid) for genome in population]


# AbstractAncestryStrategy Tests - Orchestration and Validation


def test_ancestry_strategy_cannot_instantiate_directly():
    """AbstractAncestryStrategy cannot be instantiated without implementing select_ancestry."""
    with pytest.raises(TypeError):
        AbstractAncestryStrategy()


def test_apply_strategy_calls_select_ancestry_hook():
    """apply_strategy orchestrates by calling select_ancestry."""
    strategy = MinimalAncestryStrategy()
    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    ancestry = strategy.apply_strategy(genome, [genome])

    # Verify ancestry structure
    assert len(ancestry) == 1
    assert ancestry[0] == (1.0, genome.uuid)


def test_apply_strategy_validates_fitness_set():
    """apply_strategy raises ValueError if any genome lacks fitness."""
    strategy = MinimalAncestryStrategy()
    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.5)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})  # No fitness

    with pytest.raises(ValueError, match="All genomes must have fitness set"):
        strategy.apply_strategy(genome1, [genome1, genome2])


def test_apply_strategy_validates_my_genome_in_population():
    """apply_strategy raises ValueError if my_genome not in population."""
    strategy = MinimalAncestryStrategy()
    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.5)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.6)

    with pytest.raises(ValueError, match="my_genome must be in population"):
        strategy.apply_strategy(genome1, [genome2])  # genome1 not in list


def test_apply_strategy_validates_ancestry_length():
    """apply_strategy raises ValueError if ancestry length doesn't match population."""

    class WrongLengthStrategy(AbstractAncestryStrategy):
        def select_ancestry(self, my_genome, population):
            # Return wrong length (too short)
            return [(1.0, my_genome.uuid)]

    strategy = WrongLengthStrategy()
    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.5)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.6)

    with pytest.raises(ValueError, match="Ancestry length .* must equal population size"):
        strategy.apply_strategy(genome1, [genome1, genome2])


def test_apply_strategy_preserves_rank_order():
    """apply_strategy returns ancestry in population rank order."""
    strategy = EqualAncestryStrategy()

    # Create population in specific order
    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)
    genome3 = Genome(alleles={"lr": FloatAllele(0.03)})
    genome3 = genome3.with_overrides(fitness=0.7)

    population = [genome1, genome2, genome3]
    ancestry = strategy.apply_strategy(genome1, population)

    # Verify ancestry preserves order (UUIDs match population order)
    assert ancestry[0][1] == genome1.uuid
    assert ancestry[1][1] == genome2.uuid
    assert ancestry[2][1] == genome3.uuid


def test_apply_strategy_allows_zero_probabilities():
    """Ancestry can include 0.0 probabilities (excluded parents)."""
    strategy = MinimalAncestryStrategy()

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    ancestry = strategy.apply_strategy(genome1, [genome1, genome2])

    # genome1 gets 1.0, genome2 gets 0.0
    assert ancestry[0] == (1.0, genome1.uuid)
    assert ancestry[1] == (0.0, genome2.uuid)


def test_apply_strategy_enforces_probability_sum():
    """Ancestry probabilities must sum to 1.0; non-1.0 sum raises ValueError."""

    class BadSumStrategy(AbstractAncestryStrategy):
        def select_ancestry(self, my_genome, population):
            # Return probabilities that sum to 2.0
            return [(1.0, genome.uuid) for genome in population]

    strategy = BadSumStrategy()
    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    with pytest.raises(ValueError, match="Ancestry probabilities must sum to 1.0"):
        strategy.apply_strategy(genome1, [genome1, genome2])


def test_apply_strategy_works_with_single_genome():
    """Ancestry selection works with population size 1."""
    strategy = MinimalAncestryStrategy()
    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    ancestry = strategy.apply_strategy(genome, [genome])

    assert len(ancestry) == 1
    assert ancestry[0] == (1.0, genome.uuid)


def test_apply_strategy_works_with_large_population():
    """Ancestry selection works with large populations."""
    strategy = EqualAncestryStrategy()

    # Create 100 genomes
    population = []
    for i in range(100):
        genome = Genome(alleles={"lr": FloatAllele(0.01 + i * 0.001)})
        genome = genome.with_overrides(fitness=0.1 + i * 0.01)
        population.append(genome)

    ancestry = strategy.apply_strategy(population[0], population)

    # Verify length and structure
    assert len(ancestry) == 100
    for i, (prob, uuid) in enumerate(ancestry):
        assert uuid == population[i].uuid
        assert prob == pytest.approx(0.01)  # 1/100


def test_select_ancestry_receives_my_genome_and_population():
    """select_ancestry hook receives my_genome and population parameters."""

    class InspectingStrategy(AbstractAncestryStrategy):
        def __init__(self):
            self.received_my_genome = None
            self.received_population = None

        def select_ancestry(self, my_genome, population):
            self.received_my_genome = my_genome
            self.received_population = population
            return [(1.0, my_genome.uuid)] + [(0.0, g.uuid) for g in population if g != my_genome]

    strategy = InspectingStrategy()
    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    strategy.apply_strategy(genome1, [genome1, genome2])

    # Verify hook received correct parameters
    assert strategy.received_my_genome == genome1
    assert strategy.received_population == [genome1, genome2]


def test_ancestry_uses_fitness_for_selection():
    """Concrete strategies can use fitness values for selection decisions."""

    class FitnessAwareStrategy(AbstractAncestryStrategy):
        """Selects best genome (lowest fitness)."""

        def select_ancestry(self, my_genome, population):
            best = min(population, key=lambda g: g.fitness)
            return [
                (1.0, best.uuid) if genome == best else (0.0, genome.uuid)
                for genome in population
            ]

    strategy = FitnessAwareStrategy()
    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)  # Best
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    ancestry = strategy.apply_strategy(genome1, [genome1, genome2])

    # Best genome (lowest fitness) gets 1.0
    assert ancestry[0] == (1.0, genome1.uuid)
    assert ancestry[1] == (0.0, genome2.uuid)
