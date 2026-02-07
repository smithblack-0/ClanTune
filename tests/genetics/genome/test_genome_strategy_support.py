"""
Test suite for Genome strategy support methods.

Tests with_alleles, with_ancestry, update_alleles, synthesize_new_alleles as thin
wrappers over module utilities.
"""

import pytest
from uuid import UUID
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele, CanMutateFilter


class TestWithAlleles:
    """Test with_alleles rebuilding method."""

    def test_with_alleles_replaces_alleles(self):
        """with_alleles replaces allele package."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")
        new_alleles = {"wd": FloatAllele(0.001)}

        result = genome.with_alleles(new_alleles)

        assert result.alleles == new_alleles
        assert "lr" not in result.alleles
        assert "wd" in result.alleles

    def test_with_alleles_generates_new_uuid(self):
        """with_alleles generates new UUID."""
        genome = Genome()
        original_uuid = genome.uuid

        result = genome.with_alleles({})

        assert result.uuid != original_uuid

    def test_with_alleles_preserves_parents(self):
        """with_alleles preserves parent ancestry."""
        parent_uuid = UUID("11111111-1111-1111-1111-111111111111")
        genome = Genome(parents=[(1.0, parent_uuid)])

        result = genome.with_alleles({})

        assert result.parents == [(1.0, parent_uuid)]

    def test_with_alleles_preserves_fitness(self):
        """with_alleles preserves fitness."""
        genome = Genome(fitness=0.85)

        result = genome.with_alleles({})

        assert result.fitness == 0.85


class TestWithAncestry:
    """Test with_ancestry rebuilding method."""

    def test_with_ancestry_replaces_parents(self):
        """with_ancestry replaces parent ancestry."""
        genome = Genome()
        new_parents = [(0.7, UUID("11111111-1111-1111-1111-111111111111"))]

        result = genome.with_ancestry(new_parents)

        assert result.parents == new_parents

    def test_with_ancestry_generates_new_uuid(self):
        """with_ancestry generates new UUID."""
        genome = Genome()
        original_uuid = genome.uuid

        result = genome.with_ancestry([])

        assert result.uuid != original_uuid

    def test_with_ancestry_preserves_alleles(self):
        """with_ancestry preserves alleles."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")

        result = genome.with_ancestry([])

        assert result.alleles == genome.alleles

    def test_with_ancestry_preserves_fitness(self):
        """with_ancestry preserves fitness."""
        genome = Genome(fitness=0.85)

        result = genome.with_ancestry([])

        assert result.fitness == 0.85


class TestUpdateAlleles:
    """Test update_alleles method (single-genome mutation pattern)."""

    def test_update_alleles_applies_handler(self):
        """update_alleles applies handler to all alleles."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")

        def double(allele):
            return allele.with_value(allele.value * 2)

        result = genome.update_alleles(double)

        assert result.as_hyperparameters()["lr"] == 0.02

    def test_update_alleles_multiple_hyperparameters(self):
        """update_alleles handles multiple hyperparameters."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float").add_hyperparameter("wd", 0.001, "float")

        def double(allele):
            return allele.with_value(allele.value * 2)

        result = genome.update_alleles(double)

        hyperparams = result.as_hyperparameters()
        assert hyperparams["lr"] == 0.02
        assert hyperparams["wd"] == 0.002

    def test_update_alleles_with_predicate(self):
        """update_alleles respects predicate filter."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float", can_mutate=True)
        genome = genome.add_hyperparameter("wd", 0.001, "float", can_mutate=False)

        def double(allele):
            return allele.with_value(allele.value * 2)

        result = genome.update_alleles(double, predicate=CanMutateFilter(True))

        hyperparams = result.as_hyperparameters()
        # lr doubled (passed filter)
        assert hyperparams["lr"] == 0.02
        # wd unchanged (filtered out)
        assert hyperparams["wd"] == 0.001

    def test_update_alleles_with_kwargs(self):
        """update_alleles passes kwargs to handler."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")

        def scale(allele, factor):
            return allele.with_value(allele.value * factor)

        result = genome.update_alleles(scale, factor=10.0)

        assert result.as_hyperparameters()["lr"] == 0.1

    def test_update_alleles_generates_new_uuid(self):
        """update_alleles generates new UUID."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")
        original_uuid = genome.uuid

        result = genome.update_alleles(lambda a: a)

        assert result.uuid != original_uuid

    def test_update_alleles_clears_fitness(self):
        """update_alleles produces genome with no fitness."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")
        genome = genome.set_fitness(0.95)

        result = genome.update_alleles(lambda a: a)

        assert result.fitness is None

    def test_update_alleles_clears_parents(self):
        """update_alleles produces genome with no parents."""
        parent_uuid = UUID("11111111-1111-1111-1111-111111111111")
        genome = Genome().add_hyperparameter("lr", 0.01, "float")
        genome = genome.with_overrides(parents=[(1.0, parent_uuid)])

        result = genome.update_alleles(lambda a: a)

        assert result.parents is None

    def test_update_alleles_nested_alleles(self):
        """update_alleles handles nested metadata alleles."""
        lr_allele = FloatAllele(0.01, metadata={"std": FloatAllele(0.001)})
        genome = Genome(alleles={"lr": lr_allele})

        def double(allele):
            return allele.with_value(allele.value * 2)

        result = genome.update_alleles(double)

        # Both lr and nested std should be doubled
        assert result.alleles["lr"].value == 0.02
        assert result.alleles["lr"].metadata["std"].value == 0.002


class TestSynthesizeNewAlleles:
    """Test synthesize_new_alleles method (crossbreeding pattern)."""

    def test_synthesize_new_alleles_combines_population(self):
        """synthesize_new_alleles synthesizes from population."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        def average(template, sources):
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        result = genome1.synthesize_new_alleles([genome1, genome2], average)

        assert result.as_hyperparameters()["lr"] == 0.015

    def test_synthesize_new_alleles_uses_self_as_template(self):
        """synthesize_new_alleles uses self as template."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float", domain={"min": 0.0, "max": 0.1})
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float", domain={"min": 0.0, "max": 0.1})

        def use_second(template, sources):
            return template.with_value(sources[1].value)

        result = genome1.synthesize_new_alleles([genome1, genome2], use_second)

        # Value from sources[1], domain from template (genome1)
        assert result.alleles["lr"].value == 0.02
        assert result.alleles["lr"].domain == {"min": 0.0, "max": 0.1}

    def test_synthesize_new_alleles_with_predicate(self):
        """synthesize_new_alleles respects predicate filter."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float", can_crossbreed=True)
        genome1 = genome1.add_hyperparameter("wd", 0.001, "float", can_crossbreed=False)

        genome2 = Genome().add_hyperparameter("lr", 0.02, "float", can_crossbreed=True)
        genome2 = genome2.add_hyperparameter("wd", 0.002, "float", can_crossbreed=False)

        def use_second(template, sources):
            return template.with_value(sources[1].value)

        from src.clan_tune.genetics.alleles import CanCrossbreedFilter

        result = genome1.synthesize_new_alleles(
            [genome1, genome2],
            use_second,
            predicate=CanCrossbreedFilter(True)
        )

        hyperparams = result.as_hyperparameters()
        # lr synthesized (passed filter)
        assert hyperparams["lr"] == 0.02
        # wd unchanged (filtered out, template used)
        assert hyperparams["wd"] == 0.001

    def test_synthesize_new_alleles_with_kwargs(self):
        """synthesize_new_alleles passes kwargs to handler."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        def scale_average(template, sources, scale):
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg * scale)

        result = genome1.synthesize_new_alleles([genome1, genome2], scale_average, scale=10.0)

        assert result.as_hyperparameters()["lr"] == 0.15

    def test_synthesize_new_alleles_generates_new_uuid(self):
        """synthesize_new_alleles generates new UUID."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")
        original_uuid = genome.uuid

        result = genome.synthesize_new_alleles([genome], lambda t, s: t)

        assert result.uuid != original_uuid

    def test_synthesize_new_alleles_clears_fitness(self):
        """synthesize_new_alleles produces genome with no fitness."""
        genome = Genome().add_hyperparameter("lr", 0.01, "float")
        genome = genome.set_fitness(0.95)

        result = genome.synthesize_new_alleles([genome], lambda t, s: t)

        assert result.fitness is None

    def test_synthesize_new_alleles_clears_parents(self):
        """synthesize_new_alleles produces genome with no parents."""
        parent_uuid = UUID("11111111-1111-1111-1111-111111111111")
        genome = Genome().add_hyperparameter("lr", 0.01, "float")
        genome = genome.with_overrides(parents=[(1.0, parent_uuid)])

        result = genome.synthesize_new_alleles([genome], lambda t, s: t)

        assert result.parents is None

    def test_synthesize_new_alleles_requires_self_in_population(self):
        """synthesize_new_alleles requires self to be in population."""
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")

        # genome1 calls method but isn't in population
        with pytest.raises(ValueError, match="main_genome must be present"):
            genome1.synthesize_new_alleles([genome2], lambda t, s: t)


class TestStrategyWorkflow:
    """Test typical strategy usage patterns."""

    def test_mutation_workflow(self):
        """Typical mutation strategy workflow."""
        # Initial genome
        genome = Genome().add_hyperparameter("lr", 0.01, "float", can_mutate=True)
        genome = genome.add_hyperparameter("wd", 0.001, "float", can_mutate=False)
        genome = genome.set_fitness(0.85)

        # Mutation: update mutable alleles
        def mutate(allele):
            return allele.with_value(allele.value * 1.1)

        mutated = genome.update_alleles(mutate, predicate=CanMutateFilter(True))

        # Verify mutation applied correctly
        assert mutated.as_hyperparameters()["lr"] == pytest.approx(0.011)
        assert mutated.as_hyperparameters()["wd"] == 0.001
        # Fitness and parents cleared (ready for evaluation)
        assert mutated.fitness is None
        assert mutated.parents is None

    def test_crossbreeding_workflow(self):
        """Typical crossbreeding strategy workflow."""
        # Population
        genome1 = Genome().add_hyperparameter("lr", 0.01, "float")
        genome1 = genome1.set_fitness(0.9)

        genome2 = Genome().add_hyperparameter("lr", 0.02, "float")
        genome2 = genome2.set_fitness(0.85)

        population = [genome1, genome2]

        # Crossbreeding: synthesize offspring
        def weighted_average(template, sources):
            # Simple average for this example
            avg = sum(s.value for s in sources) / len(sources)
            return template.with_value(avg)

        offspring = genome1.synthesize_new_alleles(population, weighted_average)

        # Offspring has synthesized alleles
        assert offspring.as_hyperparameters()["lr"] == 0.015

        # Offspring has no fitness/parents (cleared by synthesize)
        assert offspring.fitness is None
        assert offspring.parents is None

        # Strategy adds ancestry
        ancestry = [(0.6, genome1.uuid), (0.4, genome2.uuid)]
        offspring = offspring.with_ancestry(ancestry)

        # Now offspring has ancestry for model state reconstruction
        assert offspring.parents == ancestry
