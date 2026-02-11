"""
Concrete crossbreeding strategies implementing allele synthesis algorithms.

Each strategy fulfills AbstractCrossbreedingStrategy's handle_crossbreeding contract,
synthesizing offspring allele values from parent alleles based on ancestry probabilities.
"""

import random
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from .abstract_strategies import AbstractCrossbreedingStrategy
from .alleles import AbstractAllele, FloatAllele


class SBXEta(FloatAllele):
    """
    Evolvable distribution index for SimulatedBinaryCrossover metalearning.

    Extends FloatAllele with fixed domain [2.0, 30.0]. Injected into allele
    metadata["eta"] during setup when use_metalearning=True, enabling eta to
    evolve alongside primary hyperparameters.
    """

    def __init__(
        self,
        base_eta: float,
        can_change: bool = True,
    ):
        """
        Args:
            base_eta: Initial distribution index. Clamped to [2.0, 30.0].
            can_change: Whether this allele participates in mutation and crossbreeding.
        """
        super().__init__(
            base_eta,
            domain={"min": 2.0, "max": 30.0},
            can_mutate=can_change,
            can_crossbreed=can_change,
        )

    def with_overrides(
        self,
        **constructor_overrides: Any
    ) -> "SBXEta":
        """Construct new SBXEta preserving type through evolution operations."""
        return SBXEta(
            base_eta=constructor_overrides.get("value", self.value),
            can_change=constructor_overrides.get("can_mutate", self.can_mutate),
        )


class WeightedAverage(AbstractCrossbreedingStrategy):
    """
    Linear combination of parent values weighted by ancestry probabilities.

    Offspring value is the weighted average of source values. Simple, smooth,
    preserves characteristics proportionally. Baseline crossbreeding strategy.

    Type support: FloatAllele, IntAllele, LogFloatAllele (continuous types only).
    """

    def handle_crossbreeding(
        self,
        template: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        new_value = 0.0
        for i in range(len(allele_population)):
            new_value += ancestry[i][0] * allele_population[i].value
        return template.with_value(new_value)


class DominantParent(AbstractCrossbreedingStrategy):
    """
    Dominant parent selection: offspring inherits value from highest-probability parent.

    No blending, exact value preservation. Tie-breaking by first occurrence (lowest index).
    Pairs naturally with EliteBreeds (1.0 self-probability → exact self-copy).

    Type support: all types.
    """

    def handle_crossbreeding(
        self,
        template: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        dominant_idx = max(range(len(ancestry)), key=lambda i: ancestry[i][0])
        return template.with_value(allele_population[dominant_idx].value)


class SimulatedBinaryCrossover(AbstractCrossbreedingStrategy):
    """
    Simulated binary crossover: offspring near parents with controlled spread.

    Uses two parents and distribution index eta to generate offspring. High eta
    (20+) keeps offspring close (exploitation), low eta (2-5) spreads wider
    (exploration). Supports metalearning via evolvable SBXEta allele.

    Type support: FloatAllele, IntAllele, LogFloatAllele (continuous types only).
    """

    def __init__(
        self,
        default_eta: float = 15,
        use_metalearning: bool = False,
    ):
        """
        Args:
            default_eta: Distribution index when metalearning disabled. Typical range [2, 30].
            use_metalearning: When True, injects evolvable SBXEta into allele metadata.
        """
        if default_eta <= 0:
            raise ValueError("eta must be positive")
        self.default_eta = default_eta
        self.use_metalearning = use_metalearning

    @staticmethod
    def _random() -> float:
        """Return a random float in [0, 1). Override in tests for determinism."""
        return random.random()

    def handle_setup(
        self,
        allele: AbstractAllele,
    ) -> AbstractAllele:
        if not self.use_metalearning:
            return allele
        return allele.with_metadata(eta=SBXEta(self.default_eta))

    def handle_crossbreeding(
        self,
        template: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        eta = template.metadata.get("eta", self.default_eta)

        live_indices = [i for i in range(len(ancestry)) if ancestry[i][0] > 0.0]
        if len(live_indices) != 2:
            raise ValueError("SBX requires exactly 2 non-zero parents; pair with TopN(n=2, ...)")
        parent1_idx, parent2_idx = live_indices[0], live_indices[1]

        p1 = allele_population[parent1_idx].value
        p2 = allele_population[parent2_idx].value

        u = self._random()
        if u <= 0.5:
            beta = (2 * u) ** (1 / (eta + 1))
        else:
            beta = (1 / (2 * (1 - u))) ** (1 / (eta + 1))

        if self._random() < 0.5:
            new_value = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)
        else:
            new_value = 0.5 * ((1 - beta) * p1 + (1 + beta) * p2)
        return template.with_value(new_value)


class StochasticCrossover(AbstractCrossbreedingStrategy):
    """
    Per-allele weighted random parent selection.

    Each allele independently samples a parent using ancestry probabilities as
    weights, then uses that parent's value. Enables exploration via discontinuous
    mix-and-match inheritance.

    Type support: all types.
    """

    @staticmethod
    def _choose(
        allele_population: List[AbstractAllele],
        weights: List[float],
    ) -> AbstractAllele:
        """Sample one allele weighted by weights. Override in tests for determinism."""
        return random.choices(allele_population, weights=weights, k=1)[0]

    def handle_crossbreeding(
        self,
        template: AbstractAllele,
        allele_population: List[AbstractAllele],
        ancestry: List[Tuple[float, UUID]],
    ) -> AbstractAllele:
        probs = [ancestry[i][0] for i in range(len(ancestry))]
        sampled = self._choose(allele_population, probs)
        return template.with_value(sampled.value)
