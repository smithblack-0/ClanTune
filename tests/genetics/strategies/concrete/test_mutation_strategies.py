"""
Black-box tests for concrete mutation strategies.

Tests allele type contracts, strategy construction, handle_setup metalearning
injection, and handle_mutating algorithm correctness for all four strategies.
"""

import math
from typing import List, Tuple
from uuid import UUID, uuid4

import pytest

from src.clan_tune.genetics.alleles import BoolAllele, FloatAllele, IntAllele, LogFloatAllele, StringAllele
from src.clan_tune.genetics.mutation_strategies import (
    CauchyMutation,
    CauchyMutationChance,
    CauchyScale,
    DifferentialEvolution,
    DifferentialEvolutionF,
    GaussianMutation,
    GaussianMutationChance,
    GaussianStd,
    UniformMutation,
    UniformMutationChance,
)


# ─── Deterministic Test Subclasses ────────────────────────────────────────────


class _DeterministicGaussian(GaussianMutation):
    """Overrides _gauss to yield from a fixed noise sequence."""

    def __init__(self, noise_sequence, **kwargs):
        super().__init__(**kwargs)
        self._it = iter(noise_sequence)

    def _gauss(self, std):
        return next(self._it)


class _DeterministicCauchy(CauchyMutation):
    """Overrides _cauchy to yield from a fixed noise sequence."""

    def __init__(self, noise_sequence, **kwargs):
        super().__init__(**kwargs)
        self._it = iter(noise_sequence)

    def _cauchy(self, scale):
        return next(self._it)


class _DeterministicDE(DifferentialEvolution):
    """Overrides _choose_two and _weighted_choose_two to dereference items by injected index pairs."""

    def __init__(self, index_sequence, **kwargs):
        super().__init__(**kwargs)
        self._it = iter(index_sequence)

    def _choose_two(self, items):
        i, j = next(self._it)
        return [items[i], items[j]]

    def _weighted_choose_two(self, items, weights):
        i, j = next(self._it)
        return [items[i], items[j]]


class _DeterministicUniform(UniformMutation):
    """Overrides _random and _choose for deterministic domain sampling."""

    def __init__(self, random_sequence=None, choice_sequence=None, **kwargs):
        super().__init__(**kwargs)
        self._random_it = iter(random_sequence) if random_sequence is not None else None
        self._choice_it = iter(choice_sequence) if choice_sequence is not None else None

    def _random(self):
        return next(self._random_it)

    def _choose(self, items):
        return next(self._choice_it)


# ─── Fixtures ─────────────────────────────────────────────────────────────────


def make_ancestry(*probs: float) -> List[Tuple[float, UUID]]:
    return [(p, uuid4()) for p in probs]



# ─── GaussianMutation Tests ───────────────────────────────────────────────────


class TestGaussianMutation:
    def test_constructor_stores_defaults(self):
        s = GaussianMutation(default_std=0.2, default_mutation_chance=0.3)
        assert s.default_std == pytest.approx(0.2)
        assert s.default_mutation_chance == pytest.approx(0.3)

    def test_constructor_std_zero_raises(self):
        with pytest.raises(ValueError, match="std must be positive"):
            GaussianMutation(default_std=0)

    def test_constructor_std_negative_raises(self):
        with pytest.raises(ValueError, match="std must be positive"):
            GaussianMutation(default_std=-0.1)

    def test_constructor_chance_below_zero_raises(self):
        with pytest.raises(ValueError, match="mutation_chance must be in"):
            GaussianMutation(default_mutation_chance=-0.1)

    def test_constructor_chance_above_one_raises(self):
        with pytest.raises(ValueError, match="mutation_chance must be in"):
            GaussianMutation(default_mutation_chance=1.1)

    def test_handle_setup_no_metalearning_returns_unchanged(self):
        s = GaussianMutation(use_metalearning=False)
        allele = FloatAllele(0.5)
        assert s.handle_setup(allele) is allele

    def test_handle_setup_metalearning_injects_std_allele(self):
        s = GaussianMutation(default_std=0.2, use_metalearning=True)
        result = s.handle_setup(FloatAllele(0.5))
        assert "std" in result.metadata
        assert isinstance(result.metadata["std"], GaussianStd)
        assert result.metadata["std"].value == pytest.approx(0.2)

    def test_handle_setup_metalearning_injects_mutation_chance_allele(self):
        s = GaussianMutation(default_mutation_chance=0.3, use_metalearning=True)
        result = s.handle_setup(FloatAllele(0.5))
        assert "mutation_chance" in result.metadata
        assert isinstance(result.metadata["mutation_chance"], GaussianMutationChance)

    def test_mutation_chance_zero_returns_allele_unchanged(self):
        s = GaussianMutation(default_mutation_chance=0.0)
        allele = FloatAllele(0.5)
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.5)

    def test_float_allele_additive_noise(self):
        s = _DeterministicGaussian([0.05], default_mutation_chance=1.0)
        result = s.handle_mutating(FloatAllele(0.1), [], [])
        assert result.value == pytest.approx(0.15)

    def test_int_allele_mutates_raw_value(self):
        s = _DeterministicGaussian([0.6], default_mutation_chance=1.0)
        allele = IntAllele(3, domain={"min": 0, "max": 10})
        result = s.handle_mutating(allele, [], [])
        # raw_value 3.0 + 0.6 = 3.6, rounds to 4
        assert result.value == 4

    def test_log_float_allele_multiplicative_noise(self):
        s = _DeterministicGaussian([0.1], default_mutation_chance=1.0)
        allele = LogFloatAllele(0.01, domain={"min": 1e-5, "max": 1.0})
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.01 * math.exp(0.1))

    def test_bool_allele_skipped_silently(self):
        s = GaussianMutation(default_mutation_chance=1.0)
        allele = BoolAllele(True)
        result = s.handle_mutating(allele, [], [])
        assert result.value is True

    def test_reads_std_from_flattened_metadata(self):
        s = _DeterministicGaussian([0.05], default_std=99.0, default_mutation_chance=1.0)
        allele = FloatAllele(0.1, metadata={"std": 0.05})
        # default_std=99 would give huge noise; metadata std=0.05 means noise=_gauss(0.05)=0.05
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.15)

    def test_falls_back_to_default_std_when_no_metadata(self):
        s = _DeterministicGaussian([0.1], default_std=0.2, default_mutation_chance=1.0)
        # No metadata; std from default. _gauss receives 0.2 (ignored by deterministic),
        # returns 0.1. Result: 0.5 + 0.1 = 0.6
        result = s.handle_mutating(FloatAllele(0.5), [], [])
        assert result.value == pytest.approx(0.6)



# ─── CauchyMutation Tests ─────────────────────────────────────────────────────


class TestCauchyMutation:
    def test_constructor_scale_zero_raises(self):
        with pytest.raises(ValueError, match="scale must be positive"):
            CauchyMutation(default_scale=0)

    def test_constructor_chance_out_of_range_raises(self):
        with pytest.raises(ValueError, match="mutation_chance must be in"):
            CauchyMutation(default_mutation_chance=1.5)

    def test_handle_setup_no_metalearning_returns_unchanged(self):
        s = CauchyMutation(use_metalearning=False)
        allele = FloatAllele(0.5)
        assert s.handle_setup(allele) is allele

    def test_handle_setup_metalearning_injects_scale_allele(self):
        s = CauchyMutation(default_scale=0.2, use_metalearning=True)
        result = s.handle_setup(FloatAllele(0.5))
        assert isinstance(result.metadata["scale"], CauchyScale)
        assert result.metadata["scale"].value == pytest.approx(0.2)

    def test_mutation_chance_zero_returns_allele_unchanged(self):
        s = CauchyMutation(default_mutation_chance=0.0)
        result = s.handle_mutating(FloatAllele(0.5), [], [])
        assert result.value == pytest.approx(0.5)

    def test_float_allele_additive_noise(self):
        s = _DeterministicCauchy([0.05], default_mutation_chance=1.0)
        result = s.handle_mutating(FloatAllele(0.1), [], [])
        assert result.value == pytest.approx(0.15)

    def test_int_allele_mutates_raw_value(self):
        s = _DeterministicCauchy([0.7], default_mutation_chance=1.0)
        allele = IntAllele(3, domain={"min": 0, "max": 10})
        result = s.handle_mutating(allele, [], [])
        # raw_value 3.0 + 0.7 = 3.7, rounds to 4
        assert result.value == 4

    def test_log_float_allele_multiplicative_noise(self):
        s = _DeterministicCauchy([0.1], default_mutation_chance=1.0)
        allele = LogFloatAllele(0.01, domain={"min": 1e-5, "max": 1.0})
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.01 * math.exp(0.1))

    def test_bool_allele_skipped_silently(self):
        s = CauchyMutation(default_mutation_chance=1.0)
        result = s.handle_mutating(BoolAllele(False), [], [])
        assert result.value is False

    def test_reads_scale_from_flattened_metadata(self):
        s = _DeterministicCauchy([0.05], default_scale=99.0, default_mutation_chance=1.0)
        allele = FloatAllele(0.1, metadata={"scale": 0.05})
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.15)



# ─── DifferentialEvolution Tests ──────────────────────────────────────────────


class TestDifferentialEvolution:
    def test_constructor_f_zero_raises(self):
        with pytest.raises(ValueError, match="F must be positive"):
            DifferentialEvolution(default_F=0)

    def test_constructor_invalid_sampling_mode_raises(self):
        with pytest.raises(ValueError, match="sampling_mode must be"):
            DifferentialEvolution(default_sampling_mode="invalid")

    def test_constructor_stores_defaults(self):
        s = DifferentialEvolution(default_F=0.5, default_sampling_mode="weighted")
        assert s.default_F == pytest.approx(0.5)
        assert s.default_sampling_mode == "weighted"

    def test_handle_setup_no_metalearning_returns_unchanged(self):
        s = DifferentialEvolution(use_metalearning=False)
        allele = FloatAllele(0.5)
        assert s.handle_setup(allele) is allele

    def test_handle_setup_metalearning_injects_f_allele(self):
        s = DifferentialEvolution(default_F=0.6, use_metalearning=True)
        result = s.handle_setup(FloatAllele(0.5))
        assert isinstance(result.metadata["F"], DifferentialEvolutionF)
        assert result.metadata["F"].value == pytest.approx(0.6)

    def test_fewer_than_three_live_members_raises(self):
        s = DifferentialEvolution()
        allele = FloatAllele(0.5)
        ancestry = make_ancestry(1.0, 0.0, 0.0, 0.0)
        population = [FloatAllele(v) for v in [0.1, 0.2, 0.3, 0.4]]
        with pytest.raises(ValueError, match="at least 3 live population members"):
            s.handle_mutating(allele, population, ancestry)

    def test_unsupported_type_raises(self):
        s = DifferentialEvolution()
        ancestry = make_ancestry(1.0, 1.0, 1.0)
        population = [BoolAllele(True), BoolAllele(False), BoolAllele(True)]
        with pytest.raises(TypeError):
            s.handle_mutating(BoolAllele(False), population, ancestry)

    def test_float_allele_de_formula(self):
        # live_values=[0.1, 0.2, 0.3]; pick indices (0,2) → val1=0.1, val2=0.3
        # new_value = allele(0.5) + 1.0*(0.1 - 0.3) = 0.3
        s = _DeterministicDE([(0, 2)], default_F=1.0)
        allele = FloatAllele(0.5, domain={"min": 0.0, "max": 1.0})
        population = [FloatAllele(0.1), FloatAllele(0.2), FloatAllele(0.3)]
        ancestry = make_ancestry(1.0, 1.0, 1.0)
        result = s.handle_mutating(allele, population, ancestry)
        assert result.value == pytest.approx(0.3)

    def test_int_allele_de_uses_raw_values(self):
        # live_values=[3.0, 5.0, 7.0] (raw); pick indices (2,0) → val1=7.0, val2=3.0
        # new_raw = allele.raw_value(5.0) + 0.5*(7.0-3.0) = 7.0 → rounds to 7
        s = _DeterministicDE([(2, 0)], default_F=0.5)
        allele = IntAllele(5, domain={"min": 0, "max": 20})
        population = [IntAllele(3, domain={"min": 0, "max": 20}),
                      IntAllele(5, domain={"min": 0, "max": 20}),
                      IntAllele(7, domain={"min": 0, "max": 20})]
        ancestry = make_ancestry(1.0, 1.0, 1.0)
        result = s.handle_mutating(allele, population, ancestry)
        assert result.value == 7

    def test_log_float_allele_de_multiplicative_formula(self):
        # live_values=[0.01, 0.1, 0.001]; pick indices (1,0) → val1=0.1, val2=0.01
        # new_value = allele(0.01) * (0.1/0.01)^1.0 = 0.1
        s = _DeterministicDE([(1, 0)], default_F=1.0)
        allele = LogFloatAllele(0.01, domain={"min": 1e-5, "max": 1.0})
        population = [LogFloatAllele(0.01, domain={"min": 1e-5, "max": 1.0}),
                      LogFloatAllele(0.1,  domain={"min": 1e-5, "max": 1.0}),
                      LogFloatAllele(0.001, domain={"min": 1e-5, "max": 1.0})]
        ancestry = make_ancestry(1.0, 1.0, 1.0)
        result = s.handle_mutating(allele, population, ancestry)
        assert result.value == pytest.approx(0.1)

    def test_uses_only_live_members(self):
        # live_indices=[0,2,3]; dead member at index 1 (value 999.0) excluded.
        # live_values=[0.1, 0.3, 0.2]; pick indices (0,1) → val1=0.1, val2=0.3
        # new_value = allele(0.5) + 1.0*(0.1-0.3) = 0.3
        s = _DeterministicDE([(0, 1)], default_F=1.0)
        allele = FloatAllele(0.5, domain={"min": 0.0, "max": 2.0})
        population = [FloatAllele(0.1), FloatAllele(999.0), FloatAllele(0.3), FloatAllele(0.2)]
        ancestry = make_ancestry(1.0, 0.0, 1.0, 1.0)
        result = s.handle_mutating(allele, population, ancestry)
        assert result.value == pytest.approx(0.3)

    def test_reads_f_from_flattened_metadata(self):
        # F from metadata=1.0 overrides default=99.0
        # live_values=[0.1, 0.3, 0.2]; pick (0,2) → val1=0.1, val2=0.2
        # new_value = allele(0.5) + 1.0*(0.1-0.2) = 0.4
        s = _DeterministicDE([(0, 2)], default_F=99.0)
        allele = FloatAllele(0.5, domain={"min": 0.0, "max": 1.0}, metadata={"F": 1.0})
        population = [FloatAllele(0.1), FloatAllele(0.3), FloatAllele(0.2)]
        ancestry = make_ancestry(1.0, 1.0, 1.0)
        result = s.handle_mutating(allele, population, ancestry)
        assert result.value == pytest.approx(0.4)

    def test_weighted_mode_uses_weighted_choose_two(self):
        # Weighted mode dispatches to _weighted_choose_two.
        # live_values=[0.1, 0.3, 0.2]; pick indices (1,2) → val1=0.3, val2=0.2
        # new_value = allele(0.5) + 1.0*(0.3-0.2) = 0.6
        s = _DeterministicDE([(1, 2)], default_sampling_mode="weighted", default_F=1.0)
        allele = FloatAllele(0.5, domain={"min": 0.0, "max": 2.0})
        population = [FloatAllele(0.1), FloatAllele(0.3), FloatAllele(0.2)]
        ancestry = make_ancestry(0.6, 0.3, 0.1)
        result = s.handle_mutating(allele, population, ancestry)
        assert result.value == pytest.approx(0.6)



# ─── UniformMutation Tests ────────────────────────────────────────────────────


class TestUniformMutation:
    def test_constructor_chance_out_of_range_raises(self):
        with pytest.raises(ValueError, match="mutation_chance must be in"):
            UniformMutation(default_mutation_chance=1.5)

    def test_handle_setup_no_metalearning_returns_unchanged(self):
        s = UniformMutation(use_metalearning=False)
        allele = FloatAllele(0.5)
        assert s.handle_setup(allele) is allele

    def test_handle_setup_metalearning_injects_mutation_chance_allele(self):
        s = UniformMutation(default_mutation_chance=0.15, use_metalearning=True)
        result = s.handle_setup(FloatAllele(0.5))
        assert isinstance(result.metadata["mutation_chance"], UniformMutationChance)

    def test_mutation_chance_zero_returns_allele_unchanged(self):
        s = UniformMutation(default_mutation_chance=0.0)
        result = s.handle_mutating(FloatAllele(0.5, domain={"min": 0.0, "max": 1.0}), [], [])
        assert result.value == pytest.approx(0.5)

    def test_float_allele_samples_from_domain(self):
        # first _random() = chance check (0.0 <= 1.0 → mutate); second = domain sample 0.5
        # new_value = min + 0.5*(max-min) = 0.0 + 0.5*1.0 = 0.5
        s = _DeterministicUniform(random_sequence=[0.0, 0.5], default_mutation_chance=1.0)
        allele = FloatAllele(0.0, domain={"min": 0.0, "max": 1.0})
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.5)

    def test_float_allele_zero_random_gives_domain_min(self):
        s = _DeterministicUniform(random_sequence=[0.0, 0.0], default_mutation_chance=1.0)
        allele = FloatAllele(0.0, domain={"min": 0.2, "max": 0.8})
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.2)

    def test_int_allele_samples_from_domain(self):
        # first _random() = chance check; second = domain sample 0.5 → rounds to 5
        s = _DeterministicUniform(random_sequence=[0.0, 0.5], default_mutation_chance=1.0)
        allele = IntAllele(0, domain={"min": 0, "max": 10})
        result = s.handle_mutating(allele, [], [])
        assert result.value == 5

    def test_log_float_allele_samples_in_log_space(self):
        # domain [0.01, 1.0]; first _random() = chance check; second = 0.5
        # new_value = exp(log(0.01) + 0.5*(log(1.0)-log(0.01))) = exp(-2.3026) ≈ 0.1
        s = _DeterministicUniform(random_sequence=[0.0, 0.5], default_mutation_chance=1.0)
        allele = LogFloatAllele(0.5, domain={"min": 0.01, "max": 1.0})
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.1, rel=1e-4)

    def test_bool_allele_samples_from_domain(self):
        # random_sequence=[0.0] for chance check; choice provides domain sample
        s = _DeterministicUniform(random_sequence=[0.0], choice_sequence=[True], default_mutation_chance=1.0)
        result = s.handle_mutating(BoolAllele(False), [], [])
        assert result.value is True

    def test_string_allele_samples_from_domain(self):
        s = _DeterministicUniform(random_sequence=[0.0], choice_sequence=["b"], default_mutation_chance=1.0)
        allele = StringAllele("a", domain={"a", "b", "c"})
        result = s.handle_mutating(allele, [], [])
        assert result.value == "b"

    def test_reads_mutation_chance_from_metadata(self):
        # metadata mutation_chance=0.0 overrides default of 1.0 → no mutation
        s = UniformMutation(default_mutation_chance=1.0)
        allele = FloatAllele(0.5, domain={"min": 0.0, "max": 1.0}, metadata={"mutation_chance": 0.0})
        result = s.handle_mutating(allele, [], [])
        assert result.value == pytest.approx(0.5)
