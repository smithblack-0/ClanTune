"""
Concrete ancestry strategies implementing parent selection algorithms.

Each strategy fulfills AbstractAncestryStrategy's select_ancestry contract,
producing ancestry declarations consumed by crossbreeding strategies and orchestrators.
"""

import math
import random
from typing import Any, Callable, List, Optional, Tuple
from uuid import UUID

from .abstract_strategies import AbstractAncestryStrategy
from .genome import Genome


class TournamentSelection(AbstractAncestryStrategy):
    """
    Repeated tournament selection: run num_parents tournaments, build ancestry from win frequencies.

    Selection pressure controlled by tournament_size — larger tournaments favor fitter
    genomes (exploitation), smaller tournaments preserve diversity (exploration).
    Sampling is with replacement so the same genome can win multiple tournaments.
    """

    def __init__(
        self,
        tournament_size: int = 3,
        num_parents: int = 7,
        _choose: Optional[Callable[[List], Any]] = None,
    ):
        """
        Args:
            tournament_size: Number of genomes sampled per tournament. Must be >= 2.
            num_parents: Number of tournaments to run; determines probability denominators.
            _choose: Sampling hook — replaces random.choice in tests. Receives a list
                     and returns one element. Called tournament_size times per tournament.
        """
        if tournament_size < 2:
            raise ValueError("Tournament size must be at least 2")
        self.tournament_size = tournament_size
        self.num_parents = num_parents
        self._choose = _choose if _choose is not None else (lambda lst: random.choice(lst))

    def select_ancestry(
        self, my_genome: Genome, population: List[Genome]
    ) -> List[Tuple[float, UUID]]:
        win_counts = {genome.uuid: 0 for genome in population}

        for _ in range(self.num_parents):
            tournament = [self._choose(population) for _ in range(self.tournament_size)]
            winner = min(tournament, key=lambda g: g.fitness)
            win_counts[winner.uuid] += 1

        return [
            (win_counts[genome.uuid] / self.num_parents, genome.uuid)
            for genome in population
        ]


class EliteBreeds(AbstractAncestryStrategy):
    """
    Three-tier deterministic selection: thrive (self-reproduce), survive (self-reproduce),
    die (replaced by thrive offspring).

    Tier constraint: thrive_count + die_count < population_size ensures a survive tier exists.
    Validated at runtime when population size is known.
    """

    def __init__(self, thrive_count: int = 2, die_count: int = 2):
        """
        Args:
            thrive_count: Top-fitness genomes that self-reproduce and parent die tier.
            die_count: Bottom-fitness genomes replaced by thrive offspring.
        """
        self.thrive_count = thrive_count
        self.die_count = die_count

    def select_ancestry(
        self, my_genome: Genome, population: List[Genome]
    ) -> List[Tuple[float, UUID]]:
        if self.thrive_count + self.die_count >= len(population):
            raise ValueError("thrive_count + die_count must be less than population_size")

        sorted_pop = sorted(population, key=lambda g: g.fitness)
        thrive_set = set(sorted_pop[: self.thrive_count])
        die_set = set(sorted_pop[-self.die_count :]) if self.die_count > 0 else set()

        ancestry = []
        for genome in population:
            if my_genome not in die_set:
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
    """

    def __init__(self, selection_pressure: float = 1.0, num_parents: int = 2):
        """
        Args:
            selection_pressure: Exponent on rank weight curve. 1.0 is linear, >1.0
                                favors top ranks more strongly, <1.0 gentler gradient.
            num_parents: Number of top-ranked genomes receiving non-zero probability.
        """
        if selection_pressure <= 0:
            raise ValueError("Selection pressure must be positive")
        if num_parents < 1:
            raise ValueError("num_parents must be at least 1")
        self.selection_pressure = selection_pressure
        self.num_parents = num_parents

    def select_ancestry(
        self, my_genome: Genome, population: List[Genome]
    ) -> List[Tuple[float, UUID]]:
        n = len(population)
        sorted_pop = sorted(population, key=lambda g: g.fitness)

        raw_weights = {
            genome.uuid: (n - i) ** self.selection_pressure if i < self.num_parents else 0.0
            for i, genome in enumerate(sorted_pop)
        }

        total = sum(w for w in raw_weights.values() if w > 0)
        probs = {uuid: w / total if w > 0 else 0.0 for uuid, w in raw_weights.items()}

        return [(probs[genome.uuid], genome.uuid) for genome in population]


class BoltzmannSelection(AbstractAncestryStrategy):
    """
    Boltzmann-weighted selection: probabilities proportional to exp(-fitness/temperature).

    Temperature controls selection pressure — high temperature gives low pressure
    (nearly uniform), low temperature concentrates probability on best genomes.
    Supports external annealing schedules.
    """

    def __init__(self, temperature: float = 1.0, num_parents: int = 2):
        """
        Args:
            temperature: Controls selection pressure. High T = low pressure,
                         low T = high pressure (concentrates on best genomes).
            num_parents: Number of top-weighted genomes receiving non-zero probability.
        """
        if temperature <= 0:
            raise ValueError("Temperature must be positive")
        if num_parents < 1:
            raise ValueError("num_parents must be at least 1")
        self.temperature = temperature
        self.num_parents = num_parents

    def select_ancestry(
        self, my_genome: Genome, population: List[Genome]
    ) -> List[Tuple[float, UUID]]:
        boltzmann_weights = {
            genome.uuid: math.exp(-genome.fitness / self.temperature)
            for genome in population
        }

        sorted_by_weight = sorted(
            population, key=lambda g: boltzmann_weights[g.uuid], reverse=True
        )
        selected_set = set(sorted_by_weight[: self.num_parents])

        total = sum(boltzmann_weights[g.uuid] for g in selected_set)
        probs = {
            genome.uuid: boltzmann_weights[genome.uuid] / total
            if genome in selected_set
            else 0.0
            for genome in population
        }

        return [(probs[genome.uuid], genome.uuid) for genome in population]
