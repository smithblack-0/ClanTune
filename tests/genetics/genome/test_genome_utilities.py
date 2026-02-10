"""
Test suite for Genome module utilities (walk_genome_alleles, synthesize_genomes).

Tests parallel walking, handler invocation, kwargs passing, predicate filtering,
synthesis behavior, and delegation to allele utilities.
"""

import pytest
from uuid import UUID
from src.clan_tune.genetics.genome import Genome, walk_genome_alleles, synthesize_genomes
from src.clan_tune.genetics.alleles import FloatAllele, IntAllele, CanMutateFilter


class TestWalkGenomeAlleles:
    """Test walk_genome_alleles utility function."""

    def test_walk_empty_genome_list(self):
        """Walking empty genome list yields nothing."""
        results = list(walk_genome_alleles([], lambda alleles: alleles[0].value))

        assert results == []

    def test_walk_single_hyperparameter(self):
        """Walking genomes with single hyperparameter yields results."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        def extract_values(alleles):
            return [a.value for a in alleles]

        results = list(walk_genome_alleles([genome1, genome2], extract_values))

        assert results == [[0.01, 0.02]]

    def test_walk_multiple_hyperparameters(self):
        """Walking genomes with multiple hyperparameters yields results for each."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float").add_hyperparameter("wd", 0.001, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float").add_hyperparameter("wd", 0.002, "float")

        def extract_first_value(alleles):
            return alleles[0].value

        results = list(walk_genome_alleles([genome1, genome2], extract_first_value))

        # Two hyperparameters -> two results
        assert len(results) == 2
        assert 0.01 in results
        assert 0.001 in results

    def test_walk_preserves_population_order(self):
        """Handler receives alleles in same order as genome list."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")
        genome3 = Genome().add_hyperparameter("lr", 0.03, "float")

        def check_order(alleles):
            return [a.value for a in alleles]

        results = list(walk_genome_alleles([genome1, genome2, genome3], check_order))

        assert results == [[0.01, 0.02, 0.03]]

    def test_walk_with_kwargs(self):
        """Handler receives kwargs passed to walk_genome_alleles."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        def scale_values(alleles, scale):
            return [a.value * scale for a in alleles]

        results = list(walk_genome_alleles([genome1, genome2], scale_values, kwargs={'scale': 10.0}))

        assert results == [[0.1, 0.2]]

    def test_walk_with_predicate_filter(self):
        """walk_genome_alleles respects predicate filter."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float", can_mutate=True)
        genome1 = genome1.add_hyperparameter("wd", 0.001, "float", can_mutate=False)

        genome2 = Genome().add_hyperparameter("lr", 0.02, "float", can_mutate=True)
        genome2 = genome2.add_hyperparameter("wd", 0.002, "float", can_mutate=False)

        def extract_values(alleles):
            return alleles[0].value

        # Only walk alleles with can_mutate=True
        results = list(walk_genome_alleles(
            [genome1, genome2],
            extract_values,
            predicate=CanMutateFilter(True)
        ))

        # Only lr should be yielded (wd filtered out)
        assert results == [0.01]

    def test_walk_handler_returns_none_filters_out(self):
        """Handler returning None doesn't yield result."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        def conditional_extract(alleles):
            # Only return value if first allele > 0.015
            if alleles[0].value > 0.015:
                return alleles[0].value
            return None

        results = list(walk_genome_alleles([genome1, genome2], conditional_extract))

        assert results == []  # 0.01 <= 0.015, so None returned, nothing yielded

    def test_walk_nested_alleles(self):
        """walk_genome_alleles walks nested metadata alleles."""
        # Create alleles with nested metadata
        lr1 = FloatAllele(0.01, metadata={"std": FloatAllele(0.001)})
        lr2 = FloatAllele(0.02, metadata={"std": FloatAllele(0.002)})

        genome1 = Genome(alleles={"lr": lr1})
        genome2 = Genome(alleles={"lr": lr2})

        collected = []

        def collect_all(alleles):
            collected.append([a.value for a in alleles])
            return None  # Return None so nothing yielded, just collecting

        list(walk_genome_alleles([genome1, genome2], collect_all))

        # Should have walked both metadata std alleles and parent lr alleles
        assert len(collected) == 2  # std metadata + lr parent
        # Metadata walked first (children-first)
        assert collected[0] == [0.001, 0.002]  # std values
        assert collected[1] == [0.01, 0.02]  # lr values

    def test_walk_mismatched_hyperparameters_raises_error(self):
        """walk_genome_alleles raises ValueError if genomes have different hyperparameters."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("wd", 0.001, "float")  # Different key

        with pytest.raises(ValueError, match="same hyperparameter keys"):
            list(walk_genome_alleles([genome1, genome2], lambda a: a[0].value))


class TestSynthesizeGenomes:
    """Test synthesize_genomes utility function."""

    def test_synthesize_average_values(self):
        """synthesize_genomes combines alleles using handler."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        def average_handler(template, sources):
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        result = synthesize_genomes(genome1, [genome1, genome2], average_handler)

        assert result.as_hyperparameters()["lr"] == 0.015  # (0.01 + 0.02) / 2

    def test_synthesize_generates_new_uuid(self):
        """synthesize_genomes generates new UUID."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        original_uuid = genome1.uuid

        result = synthesize_genomes(genome1, [genome1], lambda t, s: t)

        assert result.uuid != original_uuid

    def test_synthesize_clears_fitness(self):
        """synthesize_genomes produces genome with no fitness."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome1 = genome1.set_fitness(0.95)

        result = synthesize_genomes(genome1, [genome1], lambda t, s: t)

        assert result.fitness is None

    def test_synthesize_clears_ancestry(self):
        """synthesize_genomes produces genome with no parents."""
        parent_uuid = UUID("11111111-1111-1111-1111-111111111111")
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome1 = genome1.with_overrides(parents=[(1.0, parent_uuid)])

        result = synthesize_genomes(genome1, [genome1], lambda t, s: t)

        assert result.parents is None

    def test_synthesize_with_kwargs(self):
        """synthesize_genomes passes kwargs to handler."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        def scale_average(template, sources, scale):
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg * scale)

        result = synthesize_genomes(genome1, [genome1, genome2], scale_average, kwargs={'scale': 10.0})

        assert result.as_hyperparameters()["lr"] == 0.15  # (0.015 avg) * 10

    def test_synthesize_with_predicate_filter(self):
        """synthesize_genomes respects predicate filter."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float", can_mutate=True)
        genome1 = genome1.add_hyperparameter("wd", 0.001, "float", can_mutate=False)

        genome2 = Genome().add_hyperparameter("lr", 0.02, "float", can_mutate=True)
        genome2 = genome2.add_hyperparameter("wd", 0.002, "float", can_mutate=False)

        def double_value(template, sources):
            return template.with_value(sources[0].value * 2)

        result = synthesize_genomes(
            genome1,
            [genome1, genome2],
            double_value,
            predicate=CanMutateFilter(True)
        )

        hyperparams = result.as_hyperparameters()
        # lr should be doubled (passed filter)
        assert hyperparams["lr"] == 0.02
        # wd should be unchanged (filtered out, template used)
        assert hyperparams["wd"] == 0.001

    def test_synthesize_uses_template_structure(self):
        """synthesize_genomes uses template for result structure."""
        # Both genomes must have matching schemas (domain, flags)
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float", domain={"min": 0.0, "max": 0.1})
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float", domain={"min": 0.0, "max": 0.1})

        def use_second(template, sources):
            return template.with_value(sources[1].value)

        # Use genome1 as template
        result = synthesize_genomes(genome1, [genome1, genome2], use_second)

        # Value from sources[1] (genome2), domain from template (same as genome1)
        assert result.alleles["lr"].value == 0.02
        assert result.alleles["lr"].domain == {"min": 0.0, "max": 0.1}

    def test_synthesize_multiple_hyperparameters(self):
        """synthesize_genomes handles multiple hyperparameters."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float").add_hyperparameter("wd", 0.001, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float").add_hyperparameter("wd", 0.002, "float")

        def average(template, sources):
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        result = synthesize_genomes(genome1, [genome1, genome2], average)

        hyperparams = result.as_hyperparameters()
        assert hyperparams["lr"] == 0.015
        assert hyperparams["wd"] == 0.0015

    def test_synthesize_nested_alleles(self):
        """synthesize_genomes handles nested metadata alleles."""
        lr1 = FloatAllele(0.01, metadata={"std": FloatAllele(0.001)})
        lr2 = FloatAllele(0.02, metadata={"std": FloatAllele(0.002)})

        genome1 = Genome(alleles={"lr": lr1})
        genome2 = Genome(alleles={"lr": lr2})

        def average(template, sources):
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        result = synthesize_genomes(genome1, [genome1, genome2], average)

        # Both lr and nested std should be averaged
        assert result.alleles["lr"].value == 0.015
        assert result.alleles["lr"].metadata["std"].value == 0.0015

    def test_synthesize_main_genome_not_in_population_raises_error(self):
        """synthesize_genomes raises ValueError if main_genome not in population."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        with pytest.raises(ValueError, match="main_genome must be present"):
            synthesize_genomes(genome1, [genome2], lambda t, s: t)

    def test_synthesize_empty_population_raises_error(self):
        """synthesize_genomes raises ValueError for empty population."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")

        with pytest.raises(ValueError, match="non-empty population"):
            synthesize_genomes(genome1, [], lambda t, s: t)

    def test_synthesize_mismatched_hyperparameters_raises_error(self):
        """synthesize_genomes raises ValueError if genomes have different hyperparameters."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("wd", 0.001, "float")

        with pytest.raises(ValueError, match="same hyperparameter keys"):
            synthesize_genomes(genome1, [genome1, genome2], lambda t, s: t)


class TestHandlerAdaptation:
    """Test that handlers receive kwargs correctly (delegation contract)."""

    def test_walk_handler_receives_multiple_kwargs(self):
        """walk handler receives all kwargs."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")

        def multi_kwarg_handler(alleles, scale, offset):
            return alleles[0].value * scale + offset

        results = list(walk_genome_alleles([genome1], multi_kwarg_handler, kwargs={'scale': 10.0, 'offset': 5.0}))

        assert results == [0.1 + 5.0]

    def test_synthesize_handler_receives_multiple_kwargs(self):
        """synthesize handler receives all kwargs."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")

        def multi_kwarg_handler(template, sources, scale, offset):
            return template.with_value(sources[0].value * scale + offset)

        result = synthesize_genomes(genome1, [genome1], multi_kwarg_handler, kwargs={'scale': 10.0, 'offset': 5.0})

        assert result.as_hyperparameters()["lr"] == 0.1 + 5.0
