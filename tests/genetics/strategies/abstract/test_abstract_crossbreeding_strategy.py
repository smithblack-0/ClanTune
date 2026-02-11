"""
Black-box tests for AbstractCrossbreedingStrategy.

Tests allele synthesis orchestration, delegation to handle_crossbreeding hook,
and ancestry recording. Uses minimal concrete subclass for testing.
"""

import pytest
from src.clan_tune.genetics.abstract_strategies import AbstractCrossbreedingStrategy
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele


class WeightedAverageCrossbreeding(AbstractCrossbreedingStrategy):
    """Test double implementing weighted average crossbreeding."""

    def handle_crossbreeding(self, template, allele_population, ancestry):
        """Compute weighted average using ancestry probabilities."""
        new_value = sum(prob * source.value for (prob, _), source in zip(ancestry, allele_population))
        return template.with_value(new_value)


class DominantParentCrossbreeding(AbstractCrossbreedingStrategy):
    """Test double selecting dominant parent (highest probability)."""

    def handle_crossbreeding(self, template, allele_population, ancestry):
        """Select value from parent with highest probability."""
        max_idx = max(range(len(ancestry)), key=lambda i: ancestry[i][0])
        return template.with_value(allele_population[max_idx].value)


# AbstractCrossbreedingStrategy Tests


def test_crossbreeding_strategy_cannot_instantiate_directly():
    """AbstractCrossbreedingStrategy cannot be instantiated without implementing handle_crossbreeding."""
    with pytest.raises(TypeError):
        AbstractCrossbreedingStrategy()


def test_apply_strategy_delegates_to_handle_crossbreeding():
    """apply_strategy orchestrates by calling handle_crossbreeding hook."""
    strategy = WeightedAverageCrossbreeding()

    genome1 = Genome(alleles={"lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0})})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02, domain={"min": 0.0, "max": 1.0})})
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    ancestry = [(0.7, genome1.uuid), (0.3, genome2.uuid)]

    offspring = strategy.apply_strategy(genome1, population, ancestry)

    # Weighted average: 0.7 * 0.01 + 0.3 * 0.02 = 0.013
    assert offspring.alleles["lr"].value == pytest.approx(0.013)



def test_apply_strategy_processes_can_crossbreed_alleles_only():
    """apply_strategy only processes alleles with can_crossbreed=True."""
    strategy = WeightedAverageCrossbreeding()

    genome1 = Genome(
        alleles={
            "lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0}, can_crossbreed=True),
            "wd": FloatAllele(0.001, domain={"min": 0.0, "max": 0.1}, can_crossbreed=False),
        }
    )
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(
        alleles={
            "lr": FloatAllele(0.02, domain={"min": 0.0, "max": 1.0}, can_crossbreed=True),
            "wd": FloatAllele(0.002, domain={"min": 0.0, "max": 0.1}, can_crossbreed=False),
        }
    )
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    ancestry = [(0.5, genome1.uuid), (0.5, genome2.uuid)]

    offspring = strategy.apply_strategy(genome1, population, ancestry)

    # lr was crossbred (weighted average: 0.5 * 0.01 + 0.5 * 0.02 = 0.015)
    assert offspring.alleles["lr"].value == pytest.approx(0.015)
    # wd was NOT crossbred (preserves template value)
    assert offspring.alleles["wd"].value == 0.001


def test_handle_crossbreeding_receives_flattened_alleles():
    """handle_crossbreeding receives template and allele_population as flattened alleles."""

    class InspectingStrategy(AbstractCrossbreedingStrategy):
        def __init__(self):
            self.received_template = None
            self.received_allele_population = None
            self.received_ancestry = None

        def handle_crossbreeding(self, template, allele_population, ancestry):
            self.received_template = template
            self.received_allele_population = allele_population
            self.received_ancestry = ancestry
            return template

    strategy = InspectingStrategy()

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    ancestry = [(0.6, genome1.uuid), (0.4, genome2.uuid)]

    strategy.apply_strategy(genome1, population, ancestry)

    # Verify hook received parameters
    assert strategy.received_template.value == 0.01
    assert len(strategy.received_allele_population) == 2
    assert strategy.received_allele_population[0].value == 0.01
    assert strategy.received_allele_population[1].value == 0.02
    assert strategy.received_ancestry == ancestry


def test_handle_crossbreeding_ancestry_parameter_injected_via_closure():
    """apply_strategy injects ancestry into handler via closure."""

    class CountingStrategy(AbstractCrossbreedingStrategy):
        def __init__(self):
            self.call_count = 0

        def handle_crossbreeding(self, template, allele_population, ancestry):
            self.call_count += 1
            # Verify ancestry is available
            assert len(ancestry) == len(allele_population)
            return template

    strategy = CountingStrategy()

    genome = Genome(
        alleles={
            "lr": FloatAllele(0.01),
            "wd": FloatAllele(0.001),
        }
    )
    genome = genome.with_overrides(fitness=0.5)
    ancestry = [(1.0, genome.uuid)]

    strategy.apply_strategy(genome, [genome], ancestry)

    # Handler called for each allele
    assert strategy.call_count == 2


def test_crossbreeding_with_multiple_hyperparameters():
    """Crossbreeding processes multiple hyperparameters independently."""
    strategy = WeightedAverageCrossbreeding()

    genome1 = Genome(
        alleles={
            "lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0}),
            "wd": FloatAllele(0.001, domain={"min": 0.0, "max": 0.1}),
        }
    )
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(
        alleles={
            "lr": FloatAllele(0.02, domain={"min": 0.0, "max": 1.0}),
            "wd": FloatAllele(0.002, domain={"min": 0.0, "max": 0.1}),
        }
    )
    genome2 = genome2.with_overrides(fitness=0.5)

    population = [genome1, genome2]
    ancestry = [(0.7, genome1.uuid), (0.3, genome2.uuid)]

    offspring = strategy.apply_strategy(genome1, population, ancestry)

    # Both hyperparameters crossbred independently
    assert offspring.alleles["lr"].value == pytest.approx(0.7 * 0.01 + 0.3 * 0.02)
    assert offspring.alleles["wd"].value == pytest.approx(0.7 * 0.001 + 0.3 * 0.002)


def test_dominant_parent_crossbreeding():
    """Dominant parent strategy selects value from highest probability parent."""
    strategy = DominantParentCrossbreeding()

    genome1 = Genome(alleles={"lr": FloatAllele(0.01)})
    genome1 = genome1.with_overrides(fitness=0.3)
    genome2 = Genome(alleles={"lr": FloatAllele(0.02)})
    genome2 = genome2.with_overrides(fitness=0.5)
    genome3 = Genome(alleles={"lr": FloatAllele(0.03)})
    genome3 = genome3.with_overrides(fitness=0.7)

    population = [genome1, genome2, genome3]
    ancestry = [(0.2, genome1.uuid), (0.7, genome2.uuid), (0.1, genome3.uuid)]

    offspring = strategy.apply_strategy(genome1, population, ancestry)

    # Dominant parent is genome2 (0.7 probability)
    assert offspring.alleles["lr"].value == 0.02
