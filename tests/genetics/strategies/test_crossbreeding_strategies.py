import math
from typing import List, Tuple
from uuid import UUID, uuid4

import pytest

from src.clan_tune.genetics.alleles import BoolAllele, FloatAllele, StringAllele
from src.clan_tune.genetics.crossbreeding_strategies import (
    DominantParent,
    SimulatedBinaryCrossover,
    SBXEta,
    StochasticCrossover,
    WeightedAverage,
)


# ─── Test Subclasses ──────────────────────────────────────────────────────────


class _DeterministicSBX(SimulatedBinaryCrossover):
    """Test subclass overriding _random for deterministic algorithm verification."""

    def __init__(
        self,
        random_sequence,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._it = iter(random_sequence)

    def _random(self):
        return next(self._it)


class _DeterministicStochastic(StochasticCrossover):
    """Test subclass overriding _choose for deterministic sampling verification."""

    def __init__(
        self,
        index_sequence,
    ):
        self._it = iter(index_sequence)

    def _choose(
        self,
        allele_population,
        weights,
    ):
        return allele_population[next(self._it)]


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def make_ancestry(*probs: float) -> List[Tuple[float, UUID]]:
    return [(p, uuid4()) for p in probs]


# ─── SBXEta Tests ─────────────────────────────────────────────────────────────


class TestSBXEta:
    def test_valid_construction_stores_value(self):
        eta = SBXEta(15.0)
        assert eta.value == pytest.approx(15.0)

    def test_clamped_below_min(self):
        eta = SBXEta(1.0)
        assert eta.value == pytest.approx(2.0)

    def test_clamped_above_max(self):
        eta = SBXEta(50.0)
        assert eta.value == pytest.approx(30.0)

    def test_can_change_true_sets_both_evolution_flags(self):
        eta = SBXEta(15.0, can_change=True)
        assert eta.can_mutate is True
        assert eta.can_crossbreed is True

    def test_can_change_false_clears_both_evolution_flags(self):
        eta = SBXEta(15.0, can_change=False)
        assert eta.can_mutate is False
        assert eta.can_crossbreed is False

    def test_with_value_stores_valid_unclamped_value(self):
        eta = SBXEta(15.0)
        assert eta.with_value(20.0).value == pytest.approx(20.0)

    def test_with_value_returns_sbxeta_instance(self):
        eta = SBXEta(15.0)
        updated = eta.with_value(20.0)
        assert isinstance(updated, SBXEta)

    def test_with_value_preserves_domain_clamping(self):
        eta = SBXEta(15.0)
        assert eta.with_value(50.0).value == pytest.approx(30.0)
        assert eta.with_value(1.0).value == pytest.approx(2.0)

    def test_with_value_preserves_can_change(self):
        eta = SBXEta(15.0, can_change=False)
        updated = eta.with_value(20.0)
        assert updated.can_mutate is False
        assert updated.can_crossbreed is False


# ─── WeightedAverage Tests ─────────────────────────────────────────────────────


class TestWeightedAverage:
    def test_weighted_sum_two_parents(self):
        strategy = WeightedAverage()
        template = FloatAllele(0.0)
        sources = [FloatAllele(2.0), FloatAllele(8.0)]
        ancestry = make_ancestry(0.6, 0.4)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(0.6 * 2.0 + 0.4 * 8.0)

    def test_zero_probability_parent_does_not_contribute(self):
        strategy = WeightedAverage()
        template = FloatAllele(0.0)
        sources = [FloatAllele(5.0), FloatAllele(100.0)]
        ancestry = make_ancestry(1.0, 0.0)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(5.0)

    def test_single_parent_probability_one_returns_exact_value(self):
        strategy = WeightedAverage()
        template = FloatAllele(0.0)
        sources = [FloatAllele(7.5)]
        ancestry = make_ancestry(1.0)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(7.5)

    def test_three_way_weighted_average(self):
        strategy = WeightedAverage()
        template = FloatAllele(0.0)
        sources = [FloatAllele(0.0), FloatAllele(10.0), FloatAllele(20.0)]
        ancestry = make_ancestry(0.5, 0.3, 0.2)

        expected = 0.5 * 0.0 + 0.3 * 10.0 + 0.2 * 20.0
        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(expected)

    def test_result_respects_template_domain(self):
        strategy = WeightedAverage()
        template = FloatAllele(0.0, domain={"min": 0.0, "max": 5.0})
        sources = [FloatAllele(8.0), FloatAllele(6.0)]
        ancestry = make_ancestry(0.5, 0.5)

        # Weighted average 7.0 exceeds template max of 5.0 — clamped via with_value
        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(5.0)


# ─── DominantParent Tests ──────────────────────────────────────────────────────


class TestDominantParent:
    def test_selects_highest_probability_parent(self):
        strategy = DominantParent()
        template = FloatAllele(0.0)
        sources = [FloatAllele(2.0), FloatAllele(8.0)]
        ancestry = make_ancestry(0.3, 0.7)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(8.0)

    def test_tie_breaking_selects_first_index(self):
        strategy = DominantParent()
        template = FloatAllele(0.0)
        sources = [FloatAllele(2.0), FloatAllele(5.0)]
        ancestry = make_ancestry(0.5, 0.5)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(2.0)

    def test_three_parents_picks_dominant(self):
        strategy = DominantParent()
        template = FloatAllele(0.0)
        sources = [FloatAllele(1.0), FloatAllele(9.0), FloatAllele(4.0)]
        ancestry = make_ancestry(0.1, 0.5, 0.4)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(9.0)

    def test_works_with_bool_allele(self):
        strategy = DominantParent()
        template = BoolAllele(False)
        sources = [BoolAllele(False), BoolAllele(True)]
        ancestry = make_ancestry(0.1, 0.9)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value is True

    def test_works_with_string_allele(self):
        strategy = DominantParent()
        template = StringAllele("a", domain={"a", "b", "c"})
        sources = [
            StringAllele("a", domain={"a", "b", "c"}),
            StringAllele("b", domain={"a", "b", "c"}),
            StringAllele("c", domain={"a", "b", "c"}),
        ]
        ancestry = make_ancestry(0.1, 0.7, 0.2)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == "b"


# ─── SimulatedBinaryCrossover Tests ───────────────────────────────────────────


class TestSimulatedBinaryCrossover:
    def test_constructor_defaults(self):
        strategy = SimulatedBinaryCrossover()
        assert strategy.default_eta == 15
        assert strategy.use_metalearning is False

    def test_constructor_eta_zero_raises(self):
        with pytest.raises(ValueError, match="eta must be positive"):
            SimulatedBinaryCrossover(default_eta=0)

    def test_constructor_eta_negative_raises(self):
        with pytest.raises(ValueError, match="eta must be positive"):
            SimulatedBinaryCrossover(default_eta=-5.0)

    def test_handle_setup_no_metalearning_returns_allele_unchanged(self):
        strategy = SimulatedBinaryCrossover(use_metalearning=False)
        allele = FloatAllele(0.5)
        result = strategy.handle_setup(allele)
        assert result is allele

    def test_handle_setup_metalearning_injects_sbxeta_into_metadata(self):
        strategy = SimulatedBinaryCrossover(default_eta=10, use_metalearning=True)
        allele = FloatAllele(0.5)
        result = strategy.handle_setup(allele)
        assert "eta" in result.metadata
        assert isinstance(result.metadata["eta"], SBXEta)

    def test_handle_setup_metalearning_uses_default_eta_as_initial_value(self):
        strategy = SimulatedBinaryCrossover(default_eta=20, use_metalearning=True)
        allele = FloatAllele(0.5)
        result = strategy.handle_setup(allele)
        assert result.metadata["eta"].value == pytest.approx(20.0)

    def test_algorithm_u_below_half_computes_correct_beta(self):
        u, p1, p2, eta = 0.25, 2.0, 8.0, 2
        strategy = _DeterministicSBX([u, 0.3], default_eta=eta)
        template = FloatAllele(0.0)
        sources = [FloatAllele(p1), FloatAllele(p2)]
        ancestry = make_ancestry(0.6, 0.4)

        beta = (2 * u) ** (1 / (eta + 1))
        expected_c1 = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(expected_c1, rel=1e-6)

    def test_algorithm_u_above_half_computes_correct_beta(self):
        u, p1, p2, eta = 0.75, 2.0, 8.0, 2
        strategy = _DeterministicSBX([u, 0.3], default_eta=eta)
        template = FloatAllele(0.0)
        sources = [FloatAllele(p1), FloatAllele(p2)]
        ancestry = make_ancestry(0.6, 0.4)

        beta = (1 / (2 * (1 - u))) ** (1 / (eta + 1))
        expected_c1 = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(expected_c1, rel=1e-6)

    def test_second_random_below_half_selects_c1(self):
        u, p1, p2, eta = 0.25, 2.0, 8.0, 2
        strategy = _DeterministicSBX([u, 0.3], default_eta=eta)
        template = FloatAllele(0.0)
        sources = [FloatAllele(p1), FloatAllele(p2)]
        ancestry = make_ancestry(0.6, 0.4)

        beta = (2 * u) ** (1 / (eta + 1))
        expected = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(expected, rel=1e-6)

    def test_second_random_above_half_selects_c2(self):
        u, p1, p2, eta = 0.25, 2.0, 8.0, 2
        strategy = _DeterministicSBX([u, 0.7], default_eta=eta)
        template = FloatAllele(0.0)
        sources = [FloatAllele(p1), FloatAllele(p2)]
        ancestry = make_ancestry(0.6, 0.4)

        beta = (2 * u) ** (1 / (eta + 1))
        expected = 0.5 * ((1 - beta) * p1 + (1 + beta) * p2)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(expected, rel=1e-6)

    def test_fewer_than_two_nonzero_parents_raises(self):
        strategy = SimulatedBinaryCrossover()
        template = FloatAllele(0.0)
        sources = [FloatAllele(1.0), FloatAllele(2.0)]
        ancestry = make_ancestry(1.0, 0.0)

        with pytest.raises(ValueError, match="at least two parents"):
            strategy.handle_crossbreeding(template, sources, ancestry)

    def test_reads_eta_from_flattened_template_metadata(self):
        """Flattened metadata contains eta as float; algorithm uses it instead of default."""
        u, p1, p2, eta = 0.25, 2.0, 8.0, 5.0
        # Simulate post-flatten state: metadata["eta"] is a float
        template = FloatAllele(0.0, metadata={"eta": eta})
        sources = [FloatAllele(p1), FloatAllele(p2)]
        ancestry = make_ancestry(0.6, 0.4)
        # default_eta=15 should be ignored when metadata has "eta"
        strategy = _DeterministicSBX([u, 0.3], default_eta=15)

        beta = (2 * u) ** (1 / (eta + 1))
        expected_c1 = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(expected_c1, rel=1e-6)

    def test_uses_top_two_parents_by_probability(self):
        """Third parent has lowest probability and is excluded from SBX computation."""
        p1, p2, p_excluded = 2.0, 8.0, 100.0
        u, eta = 0.25, 2
        strategy = _DeterministicSBX([u, 0.3], default_eta=eta)
        template = FloatAllele(0.0)
        sources = [FloatAllele(p1), FloatAllele(p2), FloatAllele(p_excluded)]
        ancestry = make_ancestry(0.6, 0.35, 0.05)  # top 2: indices 0 and 1

        beta = (2 * u) ** (1 / (eta + 1))
        expected_c1 = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(expected_c1, rel=1e-6)


# ─── StochasticCrossover Tests ─────────────────────────────────────────────────


class TestStochasticCrossover:
    def test_samples_second_parent(self):
        strategy = _DeterministicStochastic([1])
        template = FloatAllele(0.0)
        sources = [FloatAllele(2.0), FloatAllele(7.0)]
        ancestry = make_ancestry(0.4, 0.6)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(7.0)

    def test_samples_first_parent(self):
        strategy = _DeterministicStochastic([0])
        template = FloatAllele(0.0)
        sources = [FloatAllele(3.0), FloatAllele(9.0)]
        ancestry = make_ancestry(0.7, 0.3)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == pytest.approx(3.0)

    def test_sequential_calls_can_produce_different_parents(self):
        strategy = _DeterministicStochastic([0, 1, 0, 2])
        template = FloatAllele(0.0)
        sources = [FloatAllele(1.0), FloatAllele(2.0), FloatAllele(3.0)]
        ancestry = make_ancestry(0.4, 0.4, 0.2)

        results = [strategy.handle_crossbreeding(template, sources, ancestry).value for _ in range(4)]
        assert results == pytest.approx([1.0, 2.0, 1.0, 3.0])

    def test_works_with_bool_allele(self):
        strategy = _DeterministicStochastic([1])
        template = BoolAllele(False)
        sources = [BoolAllele(False), BoolAllele(True)]
        ancestry = make_ancestry(0.4, 0.6)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value is True

    def test_works_with_string_allele(self):
        strategy = _DeterministicStochastic([2])
        template = StringAllele("a", domain={"a", "b", "c"})
        sources = [
            StringAllele("a", domain={"a", "b", "c"}),
            StringAllele("b", domain={"a", "b", "c"}),
            StringAllele("c", domain={"a", "b", "c"}),
        ]
        ancestry = make_ancestry(0.3, 0.3, 0.4)

        result = strategy.handle_crossbreeding(template, sources, ancestry)
        assert result.value == "c"
