"""
Black-box tests for StrategyOrchestrator.

Tests composition of ancestry, crossbreeding, and mutation strategies into
complete evolution cycle. Verifies sequencing and ancestry recording.
"""

import pytest
from src.clan_tune.genetics.abstract_strategies import (
    StrategyOrchestrator,
    AbstractAncestryStrategy,
    AbstractCrossbreedingStrategy,
    AbstractMutationStrategy,
)
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele


# Test double strategies


class SelfReproduceAncestry(AbstractAncestryStrategy):
    """Always selects my_genome with 100% probability."""

    def select_ancestry(self, my_genome, population):
        return [
            (1.0, my_genome.uuid) if g == my_genome else (0.0, g.uuid)
            for g in population
        ]


class WeightedAverageCrossbreeding(AbstractCrossbreedingStrategy):
    """Weighted average using ancestry probabilities."""

    def handle_crossbreeding(self, template, allele_population, ancestry):
        new_value = sum(prob * source.value for (prob, _), source in zip(ancestry, allele_population))
        return template.with_value(new_value)


class AdditiveMutation(AbstractMutationStrategy):
    """Adds fixed delta to all values."""

    def __init__(self, delta=0.01):
        self.delta = delta

    def handle_mutating(self, allele, population, ancestry):
        return allele.with_value(allele.value + self.delta)


class MetadataInjectingStrategy(AbstractAncestryStrategy):
    """Test double that injects metadata during setup."""

    def handle_setup(self, allele):
        return allele.with_metadata(test_param=42.0)

    def select_ancestry(self, my_genome, population):
        return [(1.0, my_genome.uuid)] + [(0.0, g.uuid) for g in population if g != my_genome]


# StrategyOrchestrator Tests


def test_orchestrator_construction():
    """Orchestrator stores strategy dependencies."""
    ancestry = SelfReproduceAncestry()
    crossbreeding = WeightedAverageCrossbreeding()
    mutation = AdditiveMutation(delta=0.1)

    orchestrator = StrategyOrchestrator(ancestry, crossbreeding, mutation)

    assert orchestrator.ancestry_strategy is ancestry
    assert orchestrator.crossbreeding_strategy is crossbreeding
    assert orchestrator.mutation_strategy is mutation


def test_orchestrator_call_executes_evolution_cycle():
    """__call__ executes full evolution: ancestry → crossbreeding → mutation."""
    ancestry = SelfReproduceAncestry()
    crossbreeding = WeightedAverageCrossbreeding()
    mutation = AdditiveMutation(delta=0.1)
    orchestrator = StrategyOrchestrator(ancestry, crossbreeding, mutation)

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    offspring = orchestrator(genome, [genome])

    # Crossbreeding: self-reproduce (1.0 * 0.01 = 0.01)
    # Mutation: add 0.1 (0.01 + 0.1 = 0.11)
    assert offspring.alleles["lr"].value == pytest.approx(0.11)


def test_orchestrator_returns_new_genome():
    """Orchestrator returns new genome (new UUID)."""
    orchestrator = StrategyOrchestrator(
        SelfReproduceAncestry(),
        WeightedAverageCrossbreeding(),
        AdditiveMutation(delta=0.01),
    )

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    offspring = orchestrator(genome, [genome])

    assert offspring.uuid != genome.uuid


def test_orchestrator_records_ancestry_on_offspring():
    """Orchestrator attaches ancestry to final offspring."""
    orchestrator = StrategyOrchestrator(
        SelfReproduceAncestry(),
        WeightedAverageCrossbreeding(),
        AdditiveMutation(delta=0.01),
    )

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    offspring = orchestrator(genome1, population)

    # Ancestry recorded
    assert offspring.parents == [(1.0, genome1.uuid), (0.0, genome2.uuid)]


def test_orchestrator_clears_fitness():
    """Orchestrator returns offspring with no fitness."""
    orchestrator = StrategyOrchestrator(
        SelfReproduceAncestry(),
        WeightedAverageCrossbreeding(),
        AdditiveMutation(delta=0.01),
    )

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    offspring = orchestrator(genome, [genome])

    assert offspring.fitness is None


def test_orchestrator_with_weighted_ancestry():
    """Orchestrator works with weighted ancestry (multiple parents)."""

    class EqualAncestry(AbstractAncestryStrategy):
        def select_ancestry(self, my_genome, population):
            prob = 1.0 / len(population)
            return [(prob, g.uuid) for g in population]

    orchestrator = StrategyOrchestrator(
        EqualAncestry(), WeightedAverageCrossbreeding(), AdditiveMutation(delta=0.0)
    )

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    offspring = orchestrator(genome1, population)

    # Crossbreeding: equal average (0.5 * 0.01 + 0.5 * 0.02 = 0.015)
    # Mutation: no change (delta=0.0)
    assert offspring.alleles["lr"].value == pytest.approx(0.015)


def test_orchestrator_sequencing():
    """Orchestrator executes strategies in correct order."""

    class TrackingAncestry(AbstractAncestryStrategy):
        def __init__(self):
            self.call_order = []

        def select_ancestry(self, my_genome, population):
            self.call_order.append("ancestry")
            return [(1.0, my_genome.uuid)] + [(0.0, g.uuid) for g in population if g != my_genome]

    class TrackingCrossbreeding(AbstractCrossbreedingStrategy):
        def __init__(self, ancestry_tracker):
            self.ancestry_tracker = ancestry_tracker

        def handle_crossbreeding(self, template, allele_population, ancestry):
            self.ancestry_tracker.call_order.append("crossbreeding")
            return template

    class TrackingMutation(AbstractMutationStrategy):
        def __init__(self, ancestry_tracker):
            self.ancestry_tracker = ancestry_tracker

        def handle_mutating(self, allele, population, ancestry):
            self.ancestry_tracker.call_order.append("mutation")
            return allele

    ancestry = TrackingAncestry()
    crossbreeding = TrackingCrossbreeding(ancestry)
    mutation = TrackingMutation(ancestry)
    orchestrator = StrategyOrchestrator(ancestry, crossbreeding, mutation)

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    genome = genome.with_overrides(fitness=0.5)

    orchestrator(genome, [genome])

    # Verify order: ancestry → crossbreeding → mutation
    assert ancestry.call_order[0] == "ancestry"
    assert ancestry.call_order[1] == "crossbreeding"
    assert ancestry.call_order[2] == "mutation"


def test_setup_genome_chains_all_strategies():
    """setup_genome calls all three strategies in sequence."""

    class CountingAncestry(AbstractAncestryStrategy):
        def __init__(self):
            self.setup_calls = 0

        def handle_setup(self, allele):
            self.setup_calls += 1
            return allele.with_metadata(ancestry_setup=True)

        def select_ancestry(self, my_genome, population):
            return [(1.0, my_genome.uuid)] + [(0.0, g.uuid) for g in population if g != my_genome]

    class CountingCrossbreeding(AbstractCrossbreedingStrategy):
        def __init__(self):
            self.setup_calls = 0

        def handle_setup(self, allele):
            self.setup_calls += 1
            return allele.with_metadata(crossbreeding_setup=True)

        def handle_crossbreeding(self, template, allele_population, ancestry):
            return template

    class CountingMutation(AbstractMutationStrategy):
        def __init__(self):
            self.setup_calls = 0

        def handle_setup(self, allele):
            self.setup_calls += 1
            return allele.with_metadata(mutation_setup=True)

        def handle_mutating(self, allele, population, ancestry):
            return allele

    ancestry = CountingAncestry()
    crossbreeding = CountingCrossbreeding()
    mutation = CountingMutation()
    orchestrator = StrategyOrchestrator(ancestry, crossbreeding, mutation)

    genome = Genome(alleles={"lr": FloatAllele(0.01), "wd": FloatAllele(0.001)})

    result = orchestrator.setup_genome(genome)

    # Each strategy's handle_setup called for each allele
    assert ancestry.setup_calls == 2
    assert crossbreeding.setup_calls == 2
    assert mutation.setup_calls == 2

    # All metadata injected
    assert result.alleles["lr"].metadata.get("ancestry_setup") is True
    assert result.alleles["lr"].metadata.get("crossbreeding_setup") is True
    assert result.alleles["lr"].metadata.get("mutation_setup") is True


def test_setup_genome_independent_metadata_injection():
    """Strategies inject metadata independently without coordination."""

    class StrategyA(AbstractAncestryStrategy):
        def handle_setup(self, allele):
            return allele.with_metadata(param_a=1.0)

        def select_ancestry(self, my_genome, population):
            return [(1.0, my_genome.uuid)] + [(0.0, g.uuid) for g in population if g != my_genome]

    class StrategyB(AbstractCrossbreedingStrategy):
        def handle_setup(self, allele):
            return allele.with_metadata(param_b=2.0)

        def handle_crossbreeding(self, template, allele_population, ancestry):
            return template

    class StrategyC(AbstractMutationStrategy):
        def handle_setup(self, allele):
            return allele.with_metadata(param_c=3.0)

        def handle_mutating(self, allele, population, ancestry):
            return allele

    orchestrator = StrategyOrchestrator(StrategyA(), StrategyB(), StrategyC())

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    result = orchestrator.setup_genome(genome)

    # All three strategies injected their metadata
    assert result.alleles["lr"].metadata.get("param_a") == 1.0
    assert result.alleles["lr"].metadata.get("param_b") == 2.0
    assert result.alleles["lr"].metadata.get("param_c") == 3.0


def test_orchestrator_with_multiple_hyperparameters():
    """Orchestrator processes multiple hyperparameters correctly."""
    orchestrator = StrategyOrchestrator(
        SelfReproduceAncestry(),
        WeightedAverageCrossbreeding(),
        AdditiveMutation(delta=0.1),
    )

    genome = Genome(
        alleles={
            "lr": FloatAllele(0.01),
            "wd": FloatAllele(0.001),
            "momentum": FloatAllele(0.9),
        }
    )
    genome = genome.with_overrides(fitness=0.5)

    offspring = orchestrator(genome, [genome])

    # All hyperparameters processed
    assert offspring.alleles["lr"].value == pytest.approx(0.11)
    assert offspring.alleles["wd"].value == pytest.approx(0.101)
    assert offspring.alleles["momentum"].value == pytest.approx(1.0)


def test_orchestrator_preserves_can_mutate_can_crossbreed_flags():
    """Orchestrator respects can_mutate and can_crossbreed flags."""
    orchestrator = StrategyOrchestrator(
        SelfReproduceAncestry(),
        WeightedAverageCrossbreeding(),
        AdditiveMutation(delta=0.1),
    )

    genome = Genome(
        alleles={
            "lr": FloatAllele(0.01, can_mutate=True, can_crossbreed=True),
            "wd": FloatAllele(0.001, can_mutate=False, can_crossbreed=False),
        }
    )
    genome = genome.with_overrides(fitness=0.5)

    offspring = orchestrator(genome, [genome])

    # lr was crossbred and mutated
    assert offspring.alleles["lr"].value == pytest.approx(0.11)
    # wd was neither crossbred nor mutated
    assert offspring.alleles["wd"].value == 0.001


def test_orchestrator_validates_fitness_via_ancestry_strategy():
    """Orchestrator validates fitness through ancestry strategy."""
    orchestrator = StrategyOrchestrator(
        SelfReproduceAncestry(),
        WeightedAverageCrossbreeding(),
        AdditiveMutation(delta=0.01),
    )

    genome = Genome(alleles={"lr": FloatAllele(0.01)})
    # No fitness set

    with pytest.raises(ValueError, match="All genomes must have fitness set"):
        orchestrator(genome, [genome])
