"""
Concrete mutation strategies implementing allele perturbation algorithms.

Each strategy fulfills AbstractMutationStrategy's handle_mutating contract,
modifying allele values to introduce variation in the hyperparameter space.
"""

import math
import random
from typing import Any, List, Tuple
from uuid import UUID

import numpy

from .abstract_strategies import AbstractMutationStrategy
from .alleles import AbstractAllele, BoolAllele, FloatAllele, IntAllele, LogFloatAllele, StringAllele


# ─── Metalearning Allele Types ─────────────────────────────────────────────────


class GaussianStd(FloatAllele):
    """
    Evolvable standard deviation for GaussianMutation metalearning.

    Domain fixed at init from base_std: [0.01 * base_std, 10.0 * base_std].
    Preserved through with_overrides — value changes but domain stays static.
    Injected into allele metadata["std"] during setup when use_metalearning=True.
    """

    def __init__(self, base_std: float, *, _domain=None):
        super().__init__(
            base_std,
            domain=_domain if _domain is not None else {"min": 0.01 * base_std, "max": 10.0 * base_std},
            can_mutate=True,
            can_crossbreed=True,
        )

    def with_overrides(self, **constructor_overrides: Any) -> "GaussianStd":
        """Construct new GaussianStd preserving original domain bounds."""
        return GaussianStd(
            base_std=constructor_overrides.get("value", self.value),
            _domain=constructor_overrides.get("domain", self._domain),
        )


class GaussianMutationChance(FloatAllele):
    """
    Evolvable mutation frequency for GaussianMutation metalearning.

    Fixed domain [0.1, 0.5]. Injected into allele metadata["mutation_chance"]
    during setup when use_metalearning=True.
    """

    def __init__(self, value: float):
        super().__init__(value, domain={"min": 0.1, "max": 0.5}, can_mutate=True, can_crossbreed=True)

    def with_overrides(self, **constructor_overrides: Any) -> "GaussianMutationChance":
        return GaussianMutationChance(value=constructor_overrides.get("value", self.value))


class CauchyScale(FloatAllele):
    """
    Evolvable scale parameter for CauchyMutation metalearning.

    Domain fixed at init from base_scale: [0.01 * base_scale, 10.0 * base_scale].
    Preserved through with_overrides — value changes but domain stays static.
    Injected into allele metadata["scale"] during setup when use_metalearning=True.
    """

    def __init__(self, base_scale: float, *, _domain=None):
        super().__init__(
            base_scale,
            domain=_domain if _domain is not None else {"min": 0.01 * base_scale, "max": 10.0 * base_scale},
            can_mutate=True,
            can_crossbreed=True,
        )

    def with_overrides(self, **constructor_overrides: Any) -> "CauchyScale":
        """Construct new CauchyScale preserving original domain bounds."""
        return CauchyScale(
            base_scale=constructor_overrides.get("value", self.value),
            _domain=constructor_overrides.get("domain", self._domain),
        )


class CauchyMutationChance(FloatAllele):
    """
    Evolvable mutation frequency for CauchyMutation metalearning.

    Fixed domain [0.1, 0.5]. Injected into allele metadata["mutation_chance"]
    during setup when use_metalearning=True.
    """

    def __init__(self, value: float):
        super().__init__(value, domain={"min": 0.1, "max": 0.5}, can_mutate=True, can_crossbreed=True)

    def with_overrides(self, **constructor_overrides: Any) -> "CauchyMutationChance":
        return CauchyMutationChance(value=constructor_overrides.get("value", self.value))


class DifferentialEvolutionF(FloatAllele):
    """
    Evolvable scale factor for DifferentialEvolution metalearning.

    Fixed domain [0.5, 2.0]. Injected into allele metadata["F"] during setup
    when use_metalearning=True.
    """

    def __init__(self, base_F: float):
        super().__init__(
            base_F,
            domain={"min": 0.5, "max": 2.0},
            can_mutate=True,
            can_crossbreed=True,
        )

    def with_overrides(self, **constructor_overrides: Any) -> "DifferentialEvolutionF":
        return DifferentialEvolutionF(base_F=constructor_overrides.get("value", self.value))


class UniformMutationChance(FloatAllele):
    """
    Evolvable mutation frequency for UniformMutation metalearning.

    Fixed domain [0.01, 0.3]. Injected into allele metadata["mutation_chance"]
    during setup when use_metalearning=True.
    """

    def __init__(self, value: float):
        super().__init__(value, domain={"min": 0.01, "max": 0.3}, can_mutate=True, can_crossbreed=True)

    def with_overrides(self, **constructor_overrides: Any) -> "UniformMutationChance":
        return UniformMutationChance(value=constructor_overrides.get("value", self.value))


# ─── Mutation Strategies ───────────────────────────────────────────────────────


class GaussianMutation(AbstractMutationStrategy):
    """
    Gaussian noise-based mutation adding normally distributed perturbations.

    Noise follows N(0, std). Simple local search; ignores population and ancestry.
    Supports metalearning for std and mutation_chance via GaussianStd and
    GaussianMutationChance allele types.
    """

    def __init__(
        self,
        default_std: float = 0.1,
        default_mutation_chance: float = 0.15,
        use_metalearning: bool = False,
    ):
        """
        Args:
            default_std: Standard deviation for Gaussian noise when metalearning disabled.
            default_mutation_chance: Per-allele mutation probability.
            use_metalearning: When True, injects evolvable GaussianStd and
                GaussianMutationChance into allele metadata during setup.
        """
        if default_std <= 0:
            raise ValueError("std must be positive")
        if not 0 <= default_mutation_chance <= 1:
            raise ValueError("mutation_chance must be in [0, 1]")
        self.default_std = default_std
        self.default_mutation_chance = default_mutation_chance
        self.use_metalearning = use_metalearning

    @staticmethod
    def _gauss(std: float) -> float:
        """Generate Gaussian noise N(0, std). Override in tests for determinism."""
        return random.gauss(0, std)

    @staticmethod
    def _random() -> float:
        """Return uniform random in [0, 1). Override in tests for determinism."""
        return random.random()

    def handle_setup(self, allele: AbstractAllele) -> AbstractAllele:
        if not self.use_metalearning:
            return allele
        return allele.with_metadata(
            std=GaussianStd(self.default_std),
            mutation_chance=GaussianMutationChance(self.default_mutation_chance),
        )

    def handle_mutating(
        self,
        allele: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        std = allele.metadata.get("std", self.default_std)
        mutation_chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)

        if self._random() > mutation_chance:
            return allele

        noise = self._gauss(std)

        if isinstance(allele, IntAllele):
            return allele.with_value(allele.raw_value + noise)
        elif isinstance(allele, LogFloatAllele):
            return allele.with_value(allele.value * math.exp(noise))
        elif isinstance(allele, FloatAllele):
            return allele.with_value(allele.value + noise)

        raise TypeError(f"GaussianMutation does not support {type(allele).__name__}")


class CauchyMutation(AbstractMutationStrategy):
    """
    Heavy-tailed Cauchy noise-based mutation enabling occasional large jumps.

    Most perturbations are small; rare large jumps escape local optima. Ignores
    population and ancestry. Supports metalearning for scale and mutation_chance
    via CauchyScale and CauchyMutationChance allele types.
    """

    def __init__(
        self,
        default_scale: float = 0.1,
        default_mutation_chance: float = 0.15,
        use_metalearning: bool = False,
    ):
        """
        Args:
            default_scale: Cauchy scale parameter when metalearning disabled.
            default_mutation_chance: Per-allele mutation probability.
            use_metalearning: When True, injects evolvable CauchyScale and
                CauchyMutationChance into allele metadata during setup.
        """
        if default_scale <= 0:
            raise ValueError("scale must be positive")
        if not 0 <= default_mutation_chance <= 1:
            raise ValueError("mutation_chance must be in [0, 1]")
        self.default_scale = default_scale
        self.default_mutation_chance = default_mutation_chance
        self.use_metalearning = use_metalearning

    @staticmethod
    def _cauchy(scale: float) -> float:
        """Generate Cauchy(0, scale) noise. Override in tests for determinism."""
        return scale * math.tan(math.pi * (random.random() - 0.5))

    @staticmethod
    def _random() -> float:
        """Return uniform random in [0, 1). Override in tests for determinism."""
        return random.random()

    def handle_setup(self, allele: AbstractAllele) -> AbstractAllele:
        if not self.use_metalearning:
            return allele
        return allele.with_metadata(
            scale=CauchyScale(self.default_scale),
            mutation_chance=CauchyMutationChance(self.default_mutation_chance),
        )

    def handle_mutating(
        self,
        allele: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        scale = allele.metadata.get("scale", self.default_scale)
        mutation_chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)

        if self._random() > mutation_chance:
            return allele

        noise = self._cauchy(scale)

        if isinstance(allele, IntAllele):
            return allele.with_value(allele.raw_value + noise)
        elif isinstance(allele, LogFloatAllele):
            return allele.with_value(allele.value * math.exp(noise))
        elif isinstance(allele, FloatAllele):
            return allele.with_value(allele.value + noise)

        raise TypeError(f"CauchyMutation does not support {type(allele).__name__}")


class DifferentialEvolution(AbstractMutationStrategy):
    """
    Population-aware mutation using scaled differences between population alleles.

    Computes v = allele + F * (diff1 - diff2) where allele is the base and diff1,
    diff2 are sampled from live population members (ancestry probability > 0).
    Requires at least 3 live members; raises ValueError otherwise.
    """

    def __init__(
        self,
        default_F: float = 0.8,
        default_sampling_mode: str = "random",
        use_metalearning: bool = False,
    ):
        """
        Args:
            default_F: Scale factor for difference vectors. Typical range [0.5, 1.0].
            default_sampling_mode: "random" for uniform sampling from live members,
                "weighted" for ancestry-probability-weighted sampling.
            use_metalearning: When True, injects evolvable DifferentialEvolutionF allele.
        """
        if default_F <= 0:
            raise ValueError("F must be positive")
        if default_sampling_mode not in ("random", "weighted"):
            raise ValueError("sampling_mode must be 'random' or 'weighted'")
        self.default_F = default_F
        self.default_sampling_mode = default_sampling_mode
        self.use_metalearning = use_metalearning

    @staticmethod
    def _choose_two(items: List[float]) -> List[float]:
        """Sample two distinct values uniformly without replacement. Override in tests for determinism."""
        return random.sample(items, 2)

    @staticmethod
    def _weighted_choose_two(items: List[float], weights: List[float]) -> List[float]:
        """Sample two distinct values without replacement using weights. Override in tests for determinism."""
        return list(numpy.random.choice(items, size=2, replace=False, p=weights))

    def handle_setup(self, allele: AbstractAllele) -> AbstractAllele:
        if not self.use_metalearning:
            return allele
        return allele.with_metadata(F=DifferentialEvolutionF(self.default_F))

    def handle_mutating(
        self,
        allele: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        if not isinstance(allele, (IntAllele, FloatAllele, LogFloatAllele)):
            raise TypeError(f"DifferentialEvolution does not support {type(allele).__name__}")

        F = allele.metadata.get("F", self.default_F)
        sampling_mode = allele.metadata.get("sampling_mode", self.default_sampling_mode)

        live_indices = [i for i, (prob, _) in enumerate(ancestry) if prob > 0.0]
        if len(live_indices) < 3:
            raise ValueError("DifferentialEvolution requires at least 3 live population members")

        live_alleles = [allele_population[i] for i in live_indices]

        if isinstance(allele, IntAllele):
            live_values = [a.raw_value for a in live_alleles]
        else:
            live_values = [a.value for a in live_alleles]

        if sampling_mode == "weighted":
            live_weights = [ancestry[i][0] for i in live_indices]
            val1, val2 = self._weighted_choose_two(live_values, live_weights)
        else:
            val1, val2 = self._choose_two(live_values)

        if isinstance(allele, IntAllele):
            new_value = allele.raw_value + F * (val1 - val2)
        elif isinstance(allele, LogFloatAllele):
            new_value = allele.value * (val1 / val2) ** F
        else:
            new_value = allele.value + F * (val1 - val2)

        return allele.with_value(new_value)


class UniformMutation(AbstractMutationStrategy):
    """
    Uniform sampling mutation replacing allele values with random domain samples.

    Maximum exploration: entire domain reachable with equal probability. Supports
    all allele types including discrete (BoolAllele, StringAllele). Ignores
    population and ancestry.
    """

    def __init__(
        self,
        default_mutation_chance: float = 0.1,
        use_metalearning: bool = False,
    ):
        """
        Args:
            default_mutation_chance: Per-allele mutation probability. Lower than
                Gaussian (0.15) since uniform perturbations are more disruptive.
            use_metalearning: When True, injects evolvable UniformMutationChance.
        """
        if not 0 <= default_mutation_chance <= 1:
            raise ValueError("mutation_chance must be in [0, 1]")
        self.default_mutation_chance = default_mutation_chance
        self.use_metalearning = use_metalearning

    @staticmethod
    def _random() -> float:
        """Return uniform random in [0, 1). Override in tests for determinism."""
        return random.random()

    @staticmethod
    def _choose(items: list) -> Any:
        """Choose uniformly from a list. Override in tests for determinism."""
        return random.choice(items)

    def handle_setup(self, allele: AbstractAllele) -> AbstractAllele:
        if not self.use_metalearning:
            return allele
        return allele.with_metadata(
            mutation_chance=UniformMutationChance(self.default_mutation_chance)
        )

    def handle_mutating(
        self,
        allele: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        mutation_chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)

        if self._random() > mutation_chance:
            return allele

        if isinstance(allele, LogFloatAllele):
            log_min = math.log(allele.domain["min"])
            log_max = math.log(allele.domain["max"])
            new_value = math.exp(log_min + self._random() * (log_max - log_min))
        elif isinstance(allele, (FloatAllele, IntAllele)):
            new_value = allele.domain["min"] + self._random() * (
                allele.domain["max"] - allele.domain["min"]
            )
        elif isinstance(allele, BoolAllele):
            new_value = self._choose([True, False])
        elif isinstance(allele, StringAllele):
            new_value = self._choose(list(allele.domain))
        else:
            return allele

        return allele.with_value(new_value)
