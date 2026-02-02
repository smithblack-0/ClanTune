"""
Alleles module for ClanTune genetic algorithm toolbox.

Provides allele classes that encapsulate hyperparameter values, mutation logic,
and validation rules. Each allele type knows how to mutate itself and crossbreed
with another allele of the same type.

This module provides primitives - the Genome class orchestrates calling mutate_std
then mutate on all alleles.
"""

import random
import math
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class AbstractAllele(ABC):
    """
    Base class for all allele types.

    An allele represents a single hyperparameter with:
    - Current value
    - Mutation standard deviation (which itself can mutate)
    - Type-specific mutation logic
    - Bounds/constraints
    """

    def __init__(
            self,
            value: float,
            std: float,
    ):
        """
        Initialize allele with value and std.

        Args:
            value: Current value of this allele
            std: Standard deviation for mutations
        """
        self.value = value
        self.std = std

    def mutate_std(
            self,
            mutation_rate: float,
            mutation_std: float,
            min_clamp: float,
            max_clamp: float,
    ) -> None:
        """
        Mutate this allele's std parameter.

        Uses log-space mutation for all allele types (std is always positive).

        Args:
            mutation_rate: Probability of mutation occurring
            mutation_std: Std used when mutating this std
            min_clamp: Minimum allowed std value
            max_clamp: Maximum allowed std value
        """
        if random.random() < mutation_rate:
            perturbation = random.gauss(0, mutation_std)
            new_std = self.std * math.exp(perturbation)
            self.std = max(min_clamp, min(max_clamp, new_std))

    @abstractmethod
    def mutate(
            self,
            mutation_rate: float,
    ) -> None:
        """
        Mutate this allele's value.

        Uses internal self.std for perturbation magnitude.

        Args:
            mutation_rate: Probability of mutation occurring
        """
        pass

    @abstractmethod
    def crossbreed(
            self,
            other: "AbstractAllele",
    ) -> "AbstractAllele":
        """
        Create offspring allele via crossbreeding.

        Returns a new allele with 50/50 chance to inherit properties
        from self or other. Types must match.

        Args:
            other: Another allele of the same type

        Returns:
            New allele instance (copy of self or other)

        Raises:
            TypeError: If other is not the same allele type
        """
        pass

    def get_value(self) -> float:
        """
        Get the current value of this allele.

        Returns:
            Current hyperparameter value
        """
        return self.value

    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        """
        Serialize allele to dict.

        Returns:
            Dict containing all allele data
        """
        pass

    @classmethod
    @abstractmethod
    def deserialize(
            cls,
            data: Dict[str, Any],
    ) -> "AbstractAllele":
        """
        Reconstruct allele from serialized data.

        Args:
            data: Serialized allele data

        Returns:
            Reconstructed allele instance
        """
        pass


class MetaControlAllele(AbstractAllele):
    """
    Special allele that holds mutation control parameters.

    Its "value" is a dict containing:
    - mutation_rate: Probability of mutations
    - mutation_std: Std for mutating other allele stds
    - min_clamp: Floor for allele stds
    - max_clamp: Ceiling for allele stds

    This allele type doesn't mutate in the typical sense - it holds
    the parameters used to mutate other alleles.
    """

    def __init__(
            self,
            mutation_rate: float = 0.15,
            mutation_std: float = 0.05,
            min_clamp: float = 0.01,
            max_clamp: float = 0.5,
    ):
        """
        Initialize meta-control allele.

        Args:
            mutation_rate: Probability of mutations (default 0.15)
            mutation_std: Std for mutating allele stds (default 0.05)
            min_clamp: Minimum allowed std (default 0.01)
            max_clamp: Maximum allowed std (default 0.5)

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        if not 0 <= mutation_rate <= 1:
            raise ValueError(f"mutation_rate must be in [0, 1], got {mutation_rate}")
        if mutation_std <= 0:
            raise ValueError(f"mutation_std must be > 0, got {mutation_std}")
        if min_clamp <= 0:
            raise ValueError(f"min_clamp must be > 0, got {min_clamp}")
        if max_clamp <= min_clamp:
            raise ValueError(f"max_clamp must be > min_clamp, got max={max_clamp}, min={min_clamp}")

        # Store as dict "value"
        value_dict = {
            "mutation_rate": mutation_rate,
            "mutation_std": mutation_std,
            "min_clamp": min_clamp,
            "max_clamp": max_clamp,
        }
        # Meta-control doesn't have its own std, use 0.0 as placeholder
        super().__init__(value_dict, std=0.0)

    def mutate(
            self,
            mutation_rate: float,
    ) -> None:
        """Meta-control allele doesn't mutate."""
        pass

    def mutate_std(
            self,
            mutation_rate: float,
            mutation_std: float,
            min_clamp: float,
            max_clamp: float,
    ) -> None:
        """Meta-control allele's std doesn't mutate."""
        pass

    def crossbreed(
            self,
            other: "AbstractAllele",
    ) -> "MetaControlAllele":
        """Return copy of self or other with 50/50 probability."""
        if not isinstance(other, MetaControlAllele):
            raise TypeError(f"Cannot crossbreed MetaControlAllele with {type(other).__name__}")

        # 50/50 coin flip
        parent = self if random.random() < 0.5 else other
        parent_value = parent.value

        return MetaControlAllele(
            mutation_rate=parent_value["mutation_rate"],
            mutation_std=parent_value["mutation_std"],
            min_clamp=parent_value["min_clamp"],
            max_clamp=parent_value["max_clamp"],
        )

    def get_value(self) -> Dict[str, float]:
        """Get meta-control parameters as dict."""
        return self.value

    def serialize(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "type": "meta_control",
            "value": self.value,
        }

    @classmethod
    def deserialize(
            cls,
            data: Dict[str, Any],
    ) -> "MetaControlAllele":
        """Reconstruct from dict."""
        value = data["value"]
        return cls(
            mutation_rate=value["mutation_rate"],
            mutation_std=value["mutation_std"],
            min_clamp=value["min_clamp"],
            max_clamp=value["max_clamp"],
        )


class LogAllele(AbstractAllele):
    """
    Allele with log-space (multiplicative) mutations.

    Mutation applies: new_value = value * exp(N(0, std))
    Requires min bound > 0 (log-space requirement).
    """

    def __init__(
            self,
            value: float,
            std: float,
            min: float,
            max: Optional[float] = None,
    ):
        """
        Initialize log-space allele.

        Args:
            value: Starting value
            std: Initial mutation standard deviation
            min: Minimum bound (must be > 0)
            max: Maximum bound (optional)

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        if min <= 0:
            raise ValueError(f"LogAllele requires min > 0, got {min}")
        if value <= 0:
            raise ValueError(f"LogAllele requires value > 0 for log-space, got {value}")
        if value < min:
            raise ValueError(f"LogAllele value {value} is below min bound {min}")
        if max is not None and value > max:
            raise ValueError(f"LogAllele value {value} is above max bound {max}")
        if max is not None and max <= min:
            raise ValueError(f"LogAllele max {max} must be > min {min}")
        if std <= 0:
            raise ValueError(f"LogAllele std must be > 0, got {std}")

        super().__init__(value, std)
        self.min = min
        self.max = max

    def mutate(
            self,
            mutation_rate: float,
    ) -> None:
        """Mutate value using log-space perturbation."""
        if random.random() < mutation_rate:
            perturbation = random.gauss(0, self.std)
            new_value = self.value * math.exp(perturbation)

            # Clamp to bounds
            new_value = max(self.min, new_value)
            if self.max is not None:
                new_value = min(self.max, new_value)

            self.value = new_value

    def crossbreed(
            self,
            other: "AbstractAllele",
    ) -> "LogAllele":
        """Return copy of self or other with 50/50 probability."""
        if not isinstance(other, LogAllele):
            raise TypeError(f"Cannot crossbreed LogAllele with {type(other).__name__}")

        # 50/50 coin flip
        parent = self if random.random() < 0.5 else other

        # Return a copy of the chosen parent
        return LogAllele(
            value=parent.value,
            std=parent.std,
            min=parent.min,
            max=parent.max,
        )

    def serialize(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "type": "log",
            "value": self.value,
            "std": self.std,
            "bounds": {
                "min": self.min,
                "max": self.max,
            },
        }

    @classmethod
    def deserialize(
            cls,
            data: Dict[str, Any],
    ) -> "LogAllele":
        """Reconstruct from dict."""
        bounds = data["bounds"]
        return cls(
            value=data["value"],
            std=data["std"],
            min=bounds["min"],
            max=bounds.get("max"),
        )


class LinearAllele(AbstractAllele):
    """
    Allele with linear (additive) mutations.

    Mutation applies: new_value = value + N(0, std)
    Bounds are optional.
    """

    def __init__(
            self,
            value: float,
            std: float,
            min: Optional[float] = None,
            max: Optional[float] = None,
    ):
        """
        Initialize linear allele.

        Args:
            value: Starting value
            std: Initial mutation standard deviation
            min: Minimum bound (optional)
            max: Maximum bound (optional)

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        if std <= 0:
            raise ValueError(f"LinearAllele std must be > 0, got {std}")
        if min is not None and value < min:
            raise ValueError(f"LinearAllele value {value} is below min bound {min}")
        if max is not None and value > max:
            raise ValueError(f"LinearAllele value {value} is above max bound {max}")
        if min is not None and max is not None and max <= min:
            raise ValueError(f"LinearAllele max {max} must be > min {min}")

        super().__init__(value, std)
        self.min = min
        self.max = max

    def mutate(
            self,
            mutation_rate: float,
    ) -> None:
        """Mutate value using linear perturbation."""
        if random.random() < mutation_rate:
            perturbation = random.gauss(0, self.std)
            new_value = self.value + perturbation

            # Clamp to bounds if specified
            if self.min is not None:
                new_value = max(self.min, new_value)
            if self.max is not None:
                new_value = min(self.max, new_value)

            self.value = new_value

    def crossbreed(
            self,
            other: "AbstractAllele",
    ) -> "LinearAllele":
        """Return copy of self or other with 50/50 probability."""
        if not isinstance(other, LinearAllele):
            raise TypeError(f"Cannot crossbreed LinearAllele with {type(other).__name__}")

        # 50/50 coin flip
        parent = self if random.random() < 0.5 else other

        # Return a copy of the chosen parent
        return LinearAllele(
            value=parent.value,
            std=parent.std,
            min=parent.min,
            max=parent.max,
        )

    def serialize(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "type": "linear",
            "value": self.value,
            "std": self.std,
            "bounds": {
                "min": self.min,
                "max": self.max,
            },
        }

    @classmethod
    def deserialize(
            cls,
            data: Dict[str, Any],
    ) -> "LinearAllele":
        """Reconstruct from dict."""
        bounds = data["bounds"]
        return cls(
            value=data["value"],
            std=data["std"],
            min=bounds.get("min"),
            max=bounds.get("max"),
        )


class LinearIntegerAllele(AbstractAllele):
    """
    Allele for integer-valued hyperparameters with linear mutations.

    Stores value as float internally, applies Gaussian perturbations,
    then rounds to integer on get_value().

    Enforces minimum std of 1.0 to ensure meaningful integer jumps.
    """

    def __init__(
            self,
            value: int,
            std: float,
            min: Optional[int] = None,
            max: Optional[int] = None,
    ):
        """
        Initialize integer allele.

        Args:
            value: Starting integer value
            std: Initial mutation standard deviation (will be clamped >= 1.0)
            min: Minimum bound (optional, integer)
            max: Maximum bound (optional, integer)

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate parameters
        if std <= 0:
            raise ValueError(f"LinearIntegerAllele std must be > 0, got {std}")
        if min is not None and value < min:
            raise ValueError(f"LinearIntegerAllele value {value} is below min bound {min}")
        if max is not None and value > max:
            raise ValueError(f"LinearIntegerAllele value {value} is above max bound {max}")
        if min is not None and max is not None and max <= min:
            raise ValueError(f"LinearIntegerAllele max {max} must be > min {min}")

        # Ensure std is at least 1.0 for meaningful integer jumps
        std = max(1.0, std)

        # Store as float internally
        super().__init__(float(value), std)
        self.min = min
        self.max = max

    def mutate_std(
            self,
            mutation_rate: float,
            mutation_std: float,
            min_clamp: float,
            max_clamp: float,
    ) -> None:
        """
        Mutate std with custom minimum of 1.0.

        Overrides meta-control's min_clamp to enforce std >= 1.0
        for meaningful integer jumps.
        """
        if random.random() < mutation_rate:
            perturbation = random.gauss(0, mutation_std)
            new_std = self.std * math.exp(perturbation)
            # Custom clamp: minimum 1.0, respect max_clamp
            self.std = max(1.0, min(max_clamp, new_std))

    def mutate(
            self,
            mutation_rate: float,
    ) -> None:
        """Mutate value using linear perturbation, then clamp to integer bounds."""
        if random.random() < mutation_rate:
            perturbation = random.gauss(0, self.std)
            new_value = self.value + perturbation

            # Clamp to bounds if specified
            if self.min is not None:
                new_value = max(float(self.min), new_value)
            if self.max is not None:
                new_value = min(float(self.max), new_value)

            self.value = new_value

    def crossbreed(
            self,
            other: "AbstractAllele",
    ) -> "LinearIntegerAllele":
        """Return copy of self or other with 50/50 probability."""
        if not isinstance(other, LinearIntegerAllele):
            raise TypeError(f"Cannot crossbreed LinearIntegerAllele with {type(other).__name__}")

        # 50/50 coin flip
        parent = self if random.random() < 0.5 else other

        # Return a copy of the chosen parent (convert value back to int for constructor)
        return LinearIntegerAllele(
            value=round(parent.value),
            std=parent.std,
            min=parent.min,
            max=parent.max,
        )

    def get_value(self) -> int:
        """Get current value as rounded integer."""
        return round(self.value)

    def serialize(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "type": "linear_integer",
            "value": self.value,  # Store float internally
            "std": self.std,
            "bounds": {
                "min": self.min,
                "max": self.max,
            },
        }

    @classmethod
    def deserialize(
            cls,
            data: Dict[str, Any],
    ) -> "LinearIntegerAllele":
        """Reconstruct from dict."""
        bounds = data["bounds"]
        # Constructor expects int, but data has float - round it
        return cls(
            value=round(data["value"]),
            std=data["std"],
            min=bounds.get("min"),
            max=bounds.get("max"),
        )


# Registry for deserialization
ALLELE_TYPES = {
    "log": LogAllele,
    "linear": LinearAllele,
    "linear_integer": LinearIntegerAllele,
    "meta_control": MetaControlAllele,
}


def deserialize_allele(
        data: Dict[str, Any],
) -> AbstractAllele:
    """
    Deserialize an allele from dict data.

    Args:
        data: Serialized allele data with 'type' key

    Returns:
        Reconstructed allele instance

    Raises:
        ValueError: If type is unknown
    """
    allele_type = data.get("type")
    if allele_type not in ALLELE_TYPES:
        raise ValueError(f"Unknown allele type: {allele_type}")

    allele_class = ALLELE_TYPES[allele_type]
    return allele_class.deserialize(data)