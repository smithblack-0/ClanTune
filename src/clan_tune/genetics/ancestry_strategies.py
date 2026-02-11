"""
Concrete ancestry strategies implementing parent selection algorithms.

Each strategy fulfills AbstractAncestryStrategy's select_ancestry contract,
producing ancestry declarations consumed by crossbreeding strategies and orchestrators.
"""

import math
import random
from typing import List, Tuple
from uuid import UUID

from .abstract_strategies import AbstractAncestryStrategy
from .genome import Genome


class TournamentSelection(AbstractAncestryStrategy):
    """
    Repeated tournament selection: run num_tournaments tournaments, build ancestry from win frequencies.

    Selection pressure controlled by tournament_size — larger tournaments favor fitter
    genomes (exploitation), smaller tournaments preserve diversity (exploration).
    Sampling is with replacement so the same genome can win multiple tournaments.
    """

    def __init__(
        self,
        tournament_size: int = 3,
        num_tournaments: int = 7,
    ):
        """
        Args:
            tournament_size: Number of genomes sampled per tournament. Must be >= 2.
            num_tournaments: Number of tournaments to run; determines probability denominators.
        """
        if tournament_size < 2:
            raise ValueError("Tournament size must be at least 2")
        self.tournament_size = tournament_size
        self.num_tournaments = num_tournaments

    @staticmethod
    def _choose(
        population: List[Genome],
    ) -> Genome:
        """Select one genome from population uniformly at random. Override in tests for determinism."""
        return random.choice(population)

    def select_ancestry(
        self,
        my_genome: Genome,
        population: List[Genome],
    ) -> List[Tuple[float, UUID]]:
        win_counts = {genome.uuid: 0 for genome in population}

        for _ in range(self.num_tournaments):
            tournament = [self._choose(population) for _ in range(self.tournament_size)]
            winner = min(tournament, key=lambda g: g.fitness)
            win_counts[winner.uuid] += 1

        return [
            (win_counts[genome.uuid] / self.num_tournaments, genome.uuid)
            for genome in population
        ]


class EliteBreeds(AbstractAncestryStrategy):
    """
    Three-tier deterministic selection: thrive (self-reproduce), survive (self-reproduce),
    die (replaced by thrive offspring).

    Tier constraint: thrive_count + die_count < population_size ensures a survive tier exists.
    Validated at runtime when population size is known.
    """

    def __init__(
        self,
        thrive_count: int = 2,
        die_count: int = 2,
    ):
        """
        Args:
            thrive_count: Top-fitness genomes that self-reproduce and parent die tier.
            die_count: Bottom-fitness genomes replaced by thrive offspring.
        """
        self.thrive_count = thrive_count
        self.die_count = die_count

    def select_ancestry(
        self,
        my_genome: Genome,
        population: List[Genome],
    ) -> List[Tuple[float, UUID]]:
        if self.thrive_count + self.die_count >= len(population):
            raise ValueError("thrive_count + die_count must be less than population_size")

        sorted_pop = sorted(population, key=lambda g: g.fitness)
        thrive_set = set(sorted_pop[: self.thrive_count])
        die_set = set(sorted_pop[-self.die_count :]) if self.die_count > 0 else set()

        my_genome_survives = my_genome not in die_set

        ancestry = []
        for genome in population:
            if my_genome_survives:
                prob = 1.0 if genome is my_genome else 0.0
            else:
                prob = 1.0 / self.thrive_count if genome in thrive_set else 0.0
            ancestry.append((prob, genome.uuid))

        return ancestry


class RankSelection(AbstractAncestryStrategy):
    """
    Rank-based selection: probabilities depend on fitness rank, not raw fitness values.

    Invariant to fitness scale — probabilities reflect rank order only. Power curve on
    rank position enables adjustable selection pressure via selection_pressure exponent.
    All genomes receive non-zero probability; pair with TopN to restrict participation.
    """

    def __init__(
        self,
        selection_pressure: float = 1.0,
    ):
        """
        Args:
            selection_pressure: Exponent on rank weight curve. 1.0 is linear, >1.0
                                favors top ranks more strongly, <1.0 gentler gradient.
        """
        if selection_pressure <= 0:
            raise ValueError("Selection pressure must be positive")
        self.selection_pressure = selection_pressure

    def select_ancestry(
        self,
        my_genome: Genome,
        population: List[Genome],
    ) -> List[Tuple[float, UUID]]:
        n = len(population)
        sorted_pop = sorted(population, key=lambda g: g.fitness)

        weights = {
            sorted_pop[i].uuid: (n - i) ** self.selection_pressure
            for i in range(n)
        }

        total = sum(weights.values())
        probs = {uuid: w / total for uuid, w in weights.items()}

        return [(probs[genome.uuid], genome.uuid) for genome in population]


class BoltzmannSelection(AbstractAncestryStrategy):
    """
    Boltzmann-weighted selection: probabilities proportional to exp(-fitness/temperature).

    Temperature controls selection pressure — high temperature gives low pressure
    (nearly uniform), low temperature concentrates probability on best genomes.
    All genomes receive non-zero probability; pair with TopN to restrict participation.
    Supports external annealing schedules.
    """

    def __init__(
        self,
        temperature: float = 1.0,
    ):
        """
        Args:
            temperature: Controls selection pressure. High T = low pressure,
                         low T = high pressure (concentrates on best genomes).
        """
        if temperature <= 0:
            raise ValueError("Temperature must be positive")
        self.temperature = temperature

    def select_ancestry(
        self,
        my_genome: Genome,
        population: List[Genome],
    ) -> List[Tuple[float, UUID]]:
        weights = {
            genome.uuid: math.exp(-genome.fitness / self.temperature)
            for genome in population
        }

        total = sum(weights.values())
        probs = {uuid: w / total for uuid, w in weights.items()}

        return [(probs[genome.uuid], genome.uuid) for genome in population]


class TopN(AbstractAncestryStrategy):
    """
    Wrapper strategy clipping ancestry to top N contributors.

    Delegates to wrapped strategy, then retains only the N highest-probability
    parents, zeroing all others and renormalizing. Required pairing for
    crossbreeding strategies with strict parent count contracts — SBX requires
    exactly 2 non-zero parents: TopN(n=2, strategy=...).
    """

    def __init__(
        self,
        n: int,
        strategy: AbstractAncestryStrategy,
    ):
        """
        Args:
            n: Number of parents to retain with non-zero probability.
            strategy: Wrapped ancestry strategy whose output is clipped to top N.
        """
        if n < 1:
            raise ValueError("n must be at least 1")
        self.n = n
        self.strategy = strategy

    def select_ancestry(
        self,
        my_genome: Genome,
        population: List[Genome],
    ) -> List[Tuple[float, UUID]]:
        ancestry = self.strategy.select_ancestry(my_genome, population)

        # Find top N indices by probability descending; tie-break by lower index
        top_n_indices = set(
            sorted(
                range(len(ancestry)),
                key=lambda i: (-ancestry[i][0], i),
            )[: self.n]
        )

        clipped = [
            (prob if i in top_n_indices else 0.0, uuid)
            for i, (prob, uuid) in enumerate(ancestry)
        ]

        total = sum(p for p, _ in clipped)
        if total == 0.0:
            return clipped
        return [(p / total, uuid) for p, uuid in clipped]
