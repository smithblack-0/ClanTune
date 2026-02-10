"""
Tests for concrete ancestry strategies.

Tests verify algorithm correctness through public interfaces only. TournamentSelection
uses a _choose injection hook for deterministic verification of probability math.
All other strategies are deterministic and verified with exact computations.
"""

import math
from typing import List

import pytest

from src.clan_tune.genetics.ancestry_strategies import (
    BoltzmannSelection,
    EliteBreeds,
    RankSelection,
    TournamentSelection,
)
from src.clan_tune.genetics.genome import Genome


# --- Test fixtures ---


def make_genome(fitness: float) -> Genome:
    """Build a minimal genome with fitness set. Ancestry strategies only require uuid and fitness."""
    return Genome().set_fitness(fitness)


def make_population(*fitnesses: float) -> List[Genome]:
    """Build a population of genomes with the given fitness values, in order."""
    return [make_genome(f) for f in fitnesses]


def make_choose_sequence(*index_sequences):
    """
    Build a deterministic _choose hook for TournamentSelection testing.

    Returns a callable that serves the given index sequences in order on successive
    calls. Each sequence is one tournament's sampled indices. Allows exact verification
    of win_count / num_parents probability math without stochastic randomness.
    """
    it = iter(index_sequences)

    def choose(indices, k):
        return next(it)

    return choose


# --- TournamentSelection ---


class TestTournamentSelectionConstructorValidation:
    """Tests that the constructor enforces the tournament_size >= 2 contract."""

    def test_tournament_size_below_two_raises(self):
        with pytest.raises(ValueError, match="Tournament size must be at least 2"):
            TournamentSelection(tournament_size=1)

    def test_tournament_size_of_zero_raises(self):
        with pytest.raises(ValueError, match="Tournament size must be at least 2"):
            TournamentSelection(tournament_size=0)

    def test_minimum_valid_tournament_size_accepted(self):
        strategy = TournamentSelection(tournament_size=2)
        assert strategy.tournament_size == 2

    def test_default_parameters_accepted(self):
        strategy = TournamentSelection()
        assert strategy.tournament_size == 3
        assert strategy.num_parents == 2


class TestTournamentSelectionOutputStructure:
    """Tests that select_ancestry returns correctly structured ancestry declarations."""

    def test_output_length_equals_population_size(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = TournamentSelection(_choose=make_choose_sequence([0, 1], [0, 1]))
        ancestry = strategy.select_ancestry(population[0], population)
        assert len(ancestry) == len(population)

    def test_uuid_at_index_matches_population_genome(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = TournamentSelection(_choose=make_choose_sequence([0, 1], [0, 1]))
        ancestry = strategy.select_ancestry(population[0], population)
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid

    def test_probabilities_are_nonnegative(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = TournamentSelection(_choose=make_choose_sequence([0, 1], [1, 2]))
        ancestry = strategy.select_ancestry(population[0], population)
        assert all(prob >= 0.0 for prob, _ in ancestry)

    def test_probabilities_sum_to_one(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = TournamentSelection(_choose=make_choose_sequence([0, 1], [1, 2]))
        ancestry = strategy.select_ancestry(population[0], population)
        total = sum(prob for prob, _ in ancestry)
        assert abs(total - 1.0) < 1e-9


class TestTournamentSelectionProbabilityMath:
    """Tests that win counts translate correctly to probabilities via win_count / num_parents."""

    def test_single_winner_receives_probability_one(self):
        # Both tournaments: indices [0,1] → genome[0] wins (fitness 1.0 < 2.0)
        population = make_population(1.0, 2.0, 3.0)
        choose = make_choose_sequence([0, 1], [0, 2])
        strategy = TournamentSelection(tournament_size=2, num_parents=2, _choose=choose)
        ancestry = strategy.select_ancestry(population[0], population)

        probs = {uuid: prob for prob, uuid in ancestry}
        assert probs[population[0].uuid] == 1.0
        assert probs[population[1].uuid] == 0.0
        assert probs[population[2].uuid] == 0.0

    def test_split_wins_produce_equal_probabilities(self):
        # Tournament 1: [0,1] → genome[0] wins; Tournament 2: [1,2] → genome[1] wins
        population = make_population(1.0, 2.0, 3.0)
        choose = make_choose_sequence([0, 1], [1, 2])
        strategy = TournamentSelection(tournament_size=2, num_parents=2, _choose=choose)
        ancestry = strategy.select_ancestry(population[0], population)

        probs = {uuid: prob for prob, uuid in ancestry}
        assert probs[population[0].uuid] == 0.5
        assert probs[population[1].uuid] == 0.5
        assert probs[population[2].uuid] == 0.0

    def test_three_wins_out_of_four_gives_correct_fraction(self):
        # Tournaments: [0,1], [0,2], [0,1], [1,2]
        # Winners: genome[0], genome[0], genome[0], genome[1]
        # win_counts: {0: 3, 1: 1, 2: 0}
        population = make_population(1.0, 2.0, 3.0)
        choose = make_choose_sequence([0, 1], [0, 2], [0, 1], [1, 2])
        strategy = TournamentSelection(tournament_size=2, num_parents=4, _choose=choose)
        ancestry = strategy.select_ancestry(population[0], population)

        probs = {uuid: prob for prob, uuid in ancestry}
        assert abs(probs[population[0].uuid] - 0.75) < 1e-9
        assert abs(probs[population[1].uuid] - 0.25) < 1e-9
        assert probs[population[2].uuid] == 0.0

    def test_repeated_winner_accumulates_probability(self):
        # All four tournaments produce genome[0] → prob = 4/4 = 1.0
        population = make_population(1.0, 2.0, 3.0)
        choose = make_choose_sequence([0, 1], [0, 2], [0, 1], [0, 2])
        strategy = TournamentSelection(tournament_size=2, num_parents=4, _choose=choose)
        ancestry = strategy.select_ancestry(population[0], population)

        probs = {uuid: prob for prob, uuid in ancestry}
        assert probs[population[0].uuid] == 1.0

    def test_original_population_order_preserved_in_output(self):
        # Provide population in non-fitness order: [3.0, 1.0, 2.0]
        # Best genome is population[1]; output should still index by original order
        population = make_population(3.0, 1.0, 2.0)
        choose = make_choose_sequence([1, 2], [1, 0])
        strategy = TournamentSelection(tournament_size=2, num_parents=2, _choose=choose)
        ancestry = strategy.select_ancestry(population[0], population)

        # Check UUIDs are at original positions
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid

        # genome[1] wins both: prob = 1.0
        probs = {uuid: prob for prob, uuid in ancestry}
        assert probs[population[1].uuid] == 1.0

    def test_my_genome_does_not_affect_selection_outcome(self):
        # TournamentSelection doesn't use my_genome in its algorithm;
        # same _choose sequence from different my_genome values yields same probs
        population = make_population(1.0, 2.0, 3.0)

        strategy1 = TournamentSelection(
            tournament_size=2, num_parents=2, _choose=make_choose_sequence([0, 1], [0, 2])
        )
        ancestry1 = strategy1.select_ancestry(population[0], population)

        strategy2 = TournamentSelection(
            tournament_size=2, num_parents=2, _choose=make_choose_sequence([0, 1], [0, 2])
        )
        ancestry2 = strategy2.select_ancestry(population[2], population)

        probs1 = {uuid: prob for prob, uuid in ancestry1}
        probs2 = {uuid: prob for prob, uuid in ancestry2}
        assert probs1 == probs2


# --- EliteBreeds ---


class TestEliteBreedsValidation:
    """Tests that EliteBreeds enforces the tier constraint at runtime."""

    def test_thrive_plus_die_equals_population_size_raises(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = EliteBreeds(thrive_count=2, die_count=1)  # 2+1 == 3 = pop size
        with pytest.raises(ValueError, match="thrive_count.*die_count.*population"):
            strategy.select_ancestry(population[0], population)

    def test_thrive_plus_die_exceeds_population_size_raises(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = EliteBreeds(thrive_count=2, die_count=2)  # 2+2 > 3
        with pytest.raises(ValueError, match="thrive_count.*die_count.*population"):
            strategy.select_ancestry(population[0], population)

    def test_valid_tier_configuration_accepted(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = EliteBreeds(thrive_count=1, die_count=1)  # 1+1 < 4
        ancestry = strategy.select_ancestry(population[0], population)
        assert len(ancestry) == 4


class TestEliteBreedsOutputStructure:
    """Tests structural contracts of EliteBreeds ancestry output."""

    def test_output_length_equals_population_size(self):
        population = make_population(1.0, 2.0, 3.0, 4.0, 5.0)
        strategy = EliteBreeds(thrive_count=1, die_count=1)
        ancestry = strategy.select_ancestry(population[0], population)
        assert len(ancestry) == 5

    def test_uuid_at_index_matches_population_genome(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = EliteBreeds(thrive_count=1, die_count=1)
        ancestry = strategy.select_ancestry(population[0], population)
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid

    def test_probabilities_sum_to_one(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        for genome in population:
            strategy = EliteBreeds(thrive_count=1, die_count=1)
            ancestry = strategy.select_ancestry(genome, population)
            total = sum(prob for prob, _ in ancestry)
            assert abs(total - 1.0) < 1e-9


class TestEliteBreedsTierBehavior:
    """Tests that each tier receives the correct ancestry probabilities."""

    def test_thrive_genome_self_reproduces(self):
        # Population fitness: [1.0, 2.0, 3.0, 4.0]; thrive=[genome[0]], die=[genome[3]]
        population = make_population(1.0, 2.0, 3.0, 4.0)
        thrive_genome = population[0]
        strategy = EliteBreeds(thrive_count=1, die_count=1)

        ancestry = strategy.select_ancestry(thrive_genome, population)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert probs[thrive_genome.uuid] == 1.0
        assert all(probs[g.uuid] == 0.0 for g in population if g is not thrive_genome)

    def test_survive_genome_self_reproduces(self):
        # Population fitness: [1.0, 2.0, 3.0, 4.0]; survive=genome[1], genome[2]
        population = make_population(1.0, 2.0, 3.0, 4.0)
        survive_genome = population[1]
        strategy = EliteBreeds(thrive_count=1, die_count=1)

        ancestry = strategy.select_ancestry(survive_genome, population)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert probs[survive_genome.uuid] == 1.0
        assert all(probs[g.uuid] == 0.0 for g in population if g is not survive_genome)

    def test_die_genome_receives_equal_probability_from_thrive(self):
        # thrive_count=2: die genome gets 0.5 from each thrive member
        population = make_population(1.0, 2.0, 3.0, 4.0, 5.0)
        die_genome = population[4]  # worst fitness, in die tier
        thrive_genomes = [population[0], population[1]]  # best fitness
        strategy = EliteBreeds(thrive_count=2, die_count=1)

        ancestry = strategy.select_ancestry(die_genome, population)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert abs(probs[thrive_genomes[0].uuid] - 0.5) < 1e-9
        assert abs(probs[thrive_genomes[1].uuid] - 0.5) < 1e-9
        assert probs[die_genome.uuid] == 0.0

    def test_die_genome_with_three_thrive_gets_one_third_each(self):
        population = make_population(1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        die_genome = population[5]
        thrive_genomes = population[:3]
        strategy = EliteBreeds(thrive_count=3, die_count=1)

        ancestry = strategy.select_ancestry(die_genome, population)
        probs = {uuid: prob for prob, uuid in ancestry}

        for thrive_genome in thrive_genomes:
            assert abs(probs[thrive_genome.uuid] - 1.0 / 3.0) < 1e-9

    def test_tier_assignment_by_fitness_not_population_order(self):
        # Population provided in non-fitness order: fitness=[3.0, 1.0, 4.0, 2.0]
        # Sorted: [1.0, 2.0, 3.0, 4.0] → thrive=population[1], die=population[2]
        population = make_population(3.0, 1.0, 4.0, 2.0)
        thrive_genome = population[1]   # fitness 1.0 — best
        die_genome = population[2]       # fitness 4.0 — worst
        survive_genome = population[0]   # fitness 3.0 — survive

        strategy = EliteBreeds(thrive_count=1, die_count=1)

        thrive_ancestry = strategy.select_ancestry(thrive_genome, population)
        die_ancestry = strategy.select_ancestry(die_genome, population)
        survive_ancestry = strategy.select_ancestry(survive_genome, population)

        thrive_probs = {uuid: prob for prob, uuid in thrive_ancestry}
        die_probs = {uuid: prob for prob, uuid in die_ancestry}
        survive_probs = {uuid: prob for prob, uuid in survive_ancestry}

        assert thrive_probs[thrive_genome.uuid] == 1.0
        assert survive_probs[survive_genome.uuid] == 1.0
        assert die_probs[thrive_genome.uuid] == 1.0  # die gets from thrive

    def test_original_population_order_preserved_in_output(self):
        population = make_population(3.0, 1.0, 4.0, 2.0)
        strategy = EliteBreeds(thrive_count=1, die_count=1)
        ancestry = strategy.select_ancestry(population[0], population)
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid


# --- RankSelection ---


class TestRankSelectionConstructorValidation:
    """Tests that the constructor enforces parameter constraints."""

    def test_nonpositive_pressure_raises(self):
        with pytest.raises(ValueError, match="Selection pressure must be positive"):
            RankSelection(selection_pressure=0.0)

    def test_negative_pressure_raises(self):
        with pytest.raises(ValueError, match="Selection pressure must be positive"):
            RankSelection(selection_pressure=-1.0)

    def test_zero_num_parents_raises(self):
        with pytest.raises(ValueError, match="num_parents must be at least 1"):
            RankSelection(num_parents=0)

    def test_default_parameters_accepted(self):
        strategy = RankSelection()
        assert strategy.selection_pressure == 1.0
        assert strategy.num_parents == 2


class TestRankSelectionOutputStructure:
    """Tests structural contracts of RankSelection ancestry output."""

    def test_output_length_equals_population_size(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = RankSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        assert len(ancestry) == len(population)

    def test_uuid_at_index_matches_population_genome(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = RankSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid

    def test_probabilities_sum_to_one(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = RankSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        total = sum(prob for prob, _ in ancestry)
        assert abs(total - 1.0) < 1e-9

    def test_probabilities_are_nonnegative(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = RankSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        assert all(prob >= 0.0 for prob, _ in ancestry)


class TestRankSelectionProbabilityMath:
    """Tests that rank weights and normalization are computed correctly."""

    def test_top_num_parents_receive_nonzero_probability(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = RankSelection(num_parents=2)
        ancestry = strategy.select_ancestry(population[0], population)

        # Best two should be nonzero; worst two should be zero
        sorted_pop = sorted(population, key=lambda g: g.fitness)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert probs[sorted_pop[0].uuid] > 0.0
        assert probs[sorted_pop[1].uuid] > 0.0
        assert probs[sorted_pop[2].uuid] == 0.0
        assert probs[sorted_pop[3].uuid] == 0.0

    def test_linear_pressure_produces_correct_weights(self):
        # n=4, pressure=1.0, num_parents=2
        # sorted ranks: [0,1,2,3]; weights=[4,3,0,0]; total=7
        # probs: [4/7, 3/7, 0, 0]
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = RankSelection(selection_pressure=1.0, num_parents=2)
        ancestry = strategy.select_ancestry(population[0], population)

        sorted_pop = sorted(population, key=lambda g: g.fitness)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert abs(probs[sorted_pop[0].uuid] - 4 / 7) < 1e-9
        assert abs(probs[sorted_pop[1].uuid] - 3 / 7) < 1e-9

    def test_quadratic_pressure_produces_correct_weights(self):
        # n=4, pressure=2.0, num_parents=2
        # weights=[4^2, 3^2, 0, 0] = [16, 9, 0, 0]; total=25
        # probs: [16/25, 9/25, 0, 0]
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = RankSelection(selection_pressure=2.0, num_parents=2)
        ancestry = strategy.select_ancestry(population[0], population)

        sorted_pop = sorted(population, key=lambda g: g.fitness)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert abs(probs[sorted_pop[0].uuid] - 16 / 25) < 1e-9
        assert abs(probs[sorted_pop[1].uuid] - 9 / 25) < 1e-9

    def test_higher_pressure_increases_top_genome_share(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        sorted_pop = sorted(population, key=lambda g: g.fitness)
        best_uuid = sorted_pop[0].uuid

        low_pressure = RankSelection(selection_pressure=0.5, num_parents=2)
        high_pressure = RankSelection(selection_pressure=3.0, num_parents=2)

        low_ancestry = low_pressure.select_ancestry(population[0], population)
        high_ancestry = high_pressure.select_ancestry(population[0], population)

        low_probs = {uuid: prob for prob, uuid in low_ancestry}
        high_probs = {uuid: prob for prob, uuid in high_ancestry}

        assert high_probs[best_uuid] > low_probs[best_uuid]

    def test_num_parents_one_gives_winner_takes_all(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = RankSelection(num_parents=1)
        ancestry = strategy.select_ancestry(population[0], population)

        sorted_pop = sorted(population, key=lambda g: g.fitness)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert probs[sorted_pop[0].uuid] == 1.0
        assert probs[sorted_pop[1].uuid] == 0.0
        assert probs[sorted_pop[2].uuid] == 0.0

    def test_deterministic_output_independent_of_my_genome(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = RankSelection()

        ancestry_from_best = strategy.select_ancestry(population[0], population)
        ancestry_from_worst = strategy.select_ancestry(population[3], population)

        probs_best = {uuid: prob for prob, uuid in ancestry_from_best}
        probs_worst = {uuid: prob for prob, uuid in ancestry_from_worst}

        assert probs_best == probs_worst

    def test_original_population_order_preserved_in_output(self):
        # Unsorted population: fitness=[3.0, 1.0, 4.0, 2.0]
        population = make_population(3.0, 1.0, 4.0, 2.0)
        strategy = RankSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid

    def test_rank_order_not_population_order_determines_weights(self):
        # Population in non-fitness order; best by fitness should get highest weight
        population = make_population(4.0, 1.0, 3.0, 2.0)
        best_genome = population[1]  # fitness 1.0 — best
        strategy = RankSelection(selection_pressure=1.0, num_parents=2)
        ancestry = strategy.select_ancestry(population[0], population)

        probs = {uuid: prob for prob, uuid in ancestry}
        # best_genome should have highest probability among all
        assert all(
            probs[best_genome.uuid] >= probs[g.uuid]
            for g in population
        )


# --- BoltzmannSelection ---


class TestBoltzmannSelectionConstructorValidation:
    """Tests that the constructor enforces parameter constraints."""

    def test_nonpositive_temperature_raises(self):
        with pytest.raises(ValueError, match="Temperature must be positive"):
            BoltzmannSelection(temperature=0.0)

    def test_negative_temperature_raises(self):
        with pytest.raises(ValueError, match="Temperature must be positive"):
            BoltzmannSelection(temperature=-1.0)

    def test_zero_num_parents_raises(self):
        with pytest.raises(ValueError, match="num_parents must be at least 1"):
            BoltzmannSelection(num_parents=0)

    def test_default_parameters_accepted(self):
        strategy = BoltzmannSelection()
        assert strategy.temperature == 1.0
        assert strategy.num_parents == 2


class TestBoltzmannSelectionOutputStructure:
    """Tests structural contracts of BoltzmannSelection ancestry output."""

    def test_output_length_equals_population_size(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = BoltzmannSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        assert len(ancestry) == len(population)

    def test_uuid_at_index_matches_population_genome(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = BoltzmannSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid

    def test_probabilities_sum_to_one(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = BoltzmannSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        total = sum(prob for prob, _ in ancestry)
        assert abs(total - 1.0) < 1e-9

    def test_probabilities_are_nonnegative(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = BoltzmannSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        assert all(prob >= 0.0 for prob, _ in ancestry)


class TestBoltzmannSelectionProbabilityMath:
    """Tests that Boltzmann weights are computed and filtered correctly."""

    def test_top_num_parents_by_weight_receive_nonzero_probability(self):
        population = make_population(1.0, 2.0, 3.0, 4.0)
        strategy = BoltzmannSelection(temperature=1.0, num_parents=2)
        ancestry = strategy.select_ancestry(population[0], population)

        # Lower fitness → higher Boltzmann weight; top 2 should be nonzero
        sorted_pop = sorted(population, key=lambda g: g.fitness)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert probs[sorted_pop[0].uuid] > 0.0
        assert probs[sorted_pop[1].uuid] > 0.0
        assert probs[sorted_pop[2].uuid] == 0.0
        assert probs[sorted_pop[3].uuid] == 0.0

    def test_boltzmann_weight_math_is_correct(self):
        # exp(-fitness/T) for T=1.0: genome with fitness 1.0 gets exp(-1), fitness 2.0 gets exp(-2)
        # num_parents=2; both selected; total = exp(-1) + exp(-2)
        population = make_population(1.0, 2.0, 3.0)
        strategy = BoltzmannSelection(temperature=1.0, num_parents=2)
        ancestry = strategy.select_ancestry(population[0], population)

        sorted_pop = sorted(population, key=lambda g: g.fitness)
        w0 = math.exp(-1.0)
        w1 = math.exp(-2.0)
        total = w0 + w1

        probs = {uuid: prob for prob, uuid in ancestry}
        assert abs(probs[sorted_pop[0].uuid] - w0 / total) < 1e-9
        assert abs(probs[sorted_pop[1].uuid] - w1 / total) < 1e-9
        assert probs[sorted_pop[2].uuid] == 0.0

    def test_num_parents_one_gives_winner_takes_all(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = BoltzmannSelection(temperature=1.0, num_parents=1)
        ancestry = strategy.select_ancestry(population[0], population)

        sorted_pop = sorted(population, key=lambda g: g.fitness)
        probs = {uuid: prob for prob, uuid in ancestry}

        assert probs[sorted_pop[0].uuid] == 1.0
        assert probs[sorted_pop[1].uuid] == 0.0
        assert probs[sorted_pop[2].uuid] == 0.0

    def test_lower_temperature_concentrates_probability_on_best(self):
        # At very low temperature, best genome should receive much higher share
        population = make_population(1.0, 2.0, 3.0, 4.0)
        sorted_pop = sorted(population, key=lambda g: g.fitness)
        best_uuid = sorted_pop[0].uuid

        high_temp = BoltzmannSelection(temperature=100.0, num_parents=2)
        low_temp = BoltzmannSelection(temperature=0.01, num_parents=2)

        high_ancestry = high_temp.select_ancestry(population[0], population)
        low_ancestry = low_temp.select_ancestry(population[0], population)

        high_probs = {uuid: prob for prob, uuid in high_ancestry}
        low_probs = {uuid: prob for prob, uuid in low_ancestry}

        assert low_probs[best_uuid] > high_probs[best_uuid]

    def test_temperature_affects_distribution_among_selected(self):
        # At high temp, two selected genomes should have similar probabilities
        # At low temp, best should dominate
        population = make_population(1.0, 2.0, 3.0)
        sorted_pop = sorted(population, key=lambda g: g.fitness)

        high_temp = BoltzmannSelection(temperature=1000.0, num_parents=2)
        high_ancestry = high_temp.select_ancestry(population[0], population)
        high_probs = {uuid: prob for prob, uuid in high_ancestry}

        # At high temp, ratio of top two probs approaches 1.0
        ratio = high_probs[sorted_pop[1].uuid] / high_probs[sorted_pop[0].uuid]
        assert ratio > 0.9  # Nearly equal

    def test_deterministic_output_independent_of_my_genome(self):
        population = make_population(1.0, 2.0, 3.0)
        strategy = BoltzmannSelection()

        ancestry_from_best = strategy.select_ancestry(population[0], population)
        ancestry_from_worst = strategy.select_ancestry(population[2], population)

        probs_best = {uuid: prob for prob, uuid in ancestry_from_best}
        probs_worst = {uuid: prob for prob, uuid in ancestry_from_worst}

        assert probs_best == probs_worst

    def test_original_population_order_preserved_in_output(self):
        population = make_population(3.0, 1.0, 4.0, 2.0)
        strategy = BoltzmannSelection()
        ancestry = strategy.select_ancestry(population[0], population)
        for i, (prob, uuid) in enumerate(ancestry):
            assert uuid == population[i].uuid
