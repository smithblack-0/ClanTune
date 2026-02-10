"""
Black-box tests for AbstractStrategy base class.

Tests setup infrastructure and hook patterns. Uses minimal concrete subclass
for testing abstract functionality.
"""

import pytest
from src.clan_tune.genetics.abstract_strategies import AbstractStrategy
from src.clan_tune.genetics.genome import Genome
from src.clan_tune.genetics.alleles import FloatAllele


class MinimalStrategy(AbstractStrategy):
    """Test double for testing AbstractStrategy functionality."""

    def apply_strategy(self, *args, **kwargs):
        """Minimal implementation for testing."""
        return "applied"


class MetalearningStrategy(AbstractStrategy):
    """Test double that injects metadata during setup."""

    def __init__(self, inject_metadata=True):
        self.inject_metadata = inject_metadata

    def handle_setup(self, allele):
        """Inject test metadata if enabled."""
        if not self.inject_metadata:
            return allele
        return allele.with_metadata(test_param=42.0)

    def apply_strategy(self, *args, **kwargs):
        return "applied"


# AbstractStrategy Tests - Setup Infrastructure


def test_abstract_strategy_cannot_instantiate_directly():
    """AbstractStrategy.apply_strategy raises NotImplementedError."""
    strategy = AbstractStrategy()
    with pytest.raises(NotImplementedError, match="Subclasses must implement apply_strategy"):
        strategy.apply_strategy()


def test_default_handle_setup_returns_unchanged():
    """Default handle_setup returns allele unchanged (no-op)."""
    strategy = MinimalStrategy()
    allele = FloatAllele(1.0, domain={"min": 0.0, "max": 10.0})

    result = strategy.handle_setup(allele)

    assert result.value == 1.0
    assert result.domain == {"min": 0.0, "max": 10.0}
    assert len(result.metadata) == 0


def test_setup_genome_orchestrates_handle_setup():
    """setup_genome walks alleles and calls handle_setup on each."""
    strategy = MetalearningStrategy(inject_metadata=True)
    genome = Genome(
        alleles={
            "lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0}),
            "wd": FloatAllele(0.001, domain={"min": 0.0, "max": 0.1}),
        }
    )

    result = strategy.setup_genome(genome)

    # Verify metadata was injected into both alleles
    assert result.alleles["lr"].metadata.get("test_param") == 42.0
    assert result.alleles["wd"].metadata.get("test_param") == 42.0
    # Values unchanged
    assert result.alleles["lr"].value == 0.01
    assert result.alleles["wd"].value == 0.001


def test_setup_genome_preserves_values():
    """setup_genome never modifies allele values, only metadata."""
    strategy = MetalearningStrategy(inject_metadata=True)
    genome = Genome(
        alleles={
            "param1": FloatAllele(5.0, domain={"min": 0.0, "max": 10.0}),
            "param2": FloatAllele(7.5, domain={"min": 0.0, "max": 10.0}),
        }
    )

    result = strategy.setup_genome(genome)

    # Values must be unchanged
    assert result.alleles["param1"].value == 5.0
    assert result.alleles["param2"].value == 7.5


def test_setup_genome_without_metalearning():
    """setup_genome with default handle_setup leaves genome unchanged."""
    strategy = MinimalStrategy()
    genome = Genome(
        alleles={
            "lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0}),
        }
    )

    result = strategy.setup_genome(genome)

    # Allele unchanged (default handle_setup is no-op)
    assert result.alleles["lr"].value == 0.01
    assert len(result.alleles["lr"].metadata) == 0


def test_setup_genome_returns_new_genome():
    """setup_genome returns new genome instance (doesn't mutate input)."""
    strategy = MinimalStrategy()
    original = Genome(
        alleles={"lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0})}
    )

    result = strategy.setup_genome(original)

    # Setup preserves UUID (it's augmenting, not reproducing)
    assert result.uuid == original.uuid
    # Original unchanged (immutability - new instance returned)
    assert len(original.alleles["lr"].metadata) == 0
    # But result is different instance
    assert result is not original


def test_multiple_strategies_can_inject_metadata_independently():
    """Multiple strategies can inject different metadata without coordination."""

    class StrategyA(AbstractStrategy):
        def handle_setup(self, allele):
            return allele.with_metadata(param_a=1.0)

        def apply_strategy(self, *args, **kwargs):
            return "a"

    class StrategyB(AbstractStrategy):
        def handle_setup(self, allele):
            return allele.with_metadata(param_b=2.0)

        def apply_strategy(self, *args, **kwargs):
            return "b"

    genome = Genome(alleles={"lr": FloatAllele(0.01, domain={"min": 0.0, "max": 1.0})})

    # Apply strategy A
    genome_a = StrategyA().setup_genome(genome)
    assert genome_a.alleles["lr"].metadata.get("param_a") == 1.0

    # Apply strategy B to result
    genome_ab = StrategyB().setup_genome(genome_a)
    assert genome_ab.alleles["lr"].metadata.get("param_a") == 1.0
    assert genome_ab.alleles["lr"].metadata.get("param_b") == 2.0


def test_setup_genome_works_with_empty_genome():
    """setup_genome handles genome with no alleles."""
    strategy = MetalearningStrategy(inject_metadata=True)
    genome = Genome(alleles={})

    result = strategy.setup_genome(genome)

    assert len(result.alleles) == 0
