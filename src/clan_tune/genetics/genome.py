"""
Genome class for ClanTune genetic algorithm toolbox.

This module provides the Genome class which orchestrates allele mutation
and manages the collection of hyperparameters. Uses Python's random module
for all stochastic operations.
"""

import json
from typing import Dict, Any, Optional, Literal

from .alleles import (
    AbstractAllele,
    MetaControlAllele,
    LogAllele,
    LinearAllele,
    LinearIntegerAllele,
    deserialize_allele,
)


class Genome:
    """
    Manages a collection of alleles (hyperparameters) with mutation capabilities.

    Acts as an orchestrator: delegates mutation logic to individual alleles,
    coordinates the two-phase mutation (std first, then values), and handles
    serialization/fitness tracking.
    """

    def __init__(
            self,
            mutation_rate: float = 0.15,
            mutation_std: float = 0.05,
            min_std_clamp: float = 0.01,
            max_std_clamp: float = 0.5,
            _alleles: Optional[Dict[str, AbstractAllele]] = None,
    ):
        """
        Initialize a genome with meta-mutation controls.

        Args:
            mutation_rate: Probability of mutation for each allele/std (default 0.15)
            mutation_std: Std used when mutating allele stds (default 0.05)
            min_std_clamp: Minimum allowed std for alleles (default 0.01)
            max_std_clamp: Maximum allowed std for alleles (default 0.5)
            _alleles: Internal alleles dict (for testing/deserialization, optional)
        """
        if _alleles is not None:
            self._alleles = _alleles
        else:
            self._alleles = {
                "__meta__": MetaControlAllele(
                    mutation_rate=mutation_rate,
                    mutation_std=mutation_std,
                    min_clamp=min_std_clamp,
                    max_clamp=max_std_clamp,
                )
            }

        self._fitness: Optional[float] = None

    def add_allele(
            self,
            name: str,
            type: Literal["log", "linear", "linear_integer"],
            starting_value: float,
            min: Optional[float] = None,
            max: Optional[float] = None,
            std: float = 0.1,
    ) -> None:
        """
        Add an allele (hyperparameter) to the genome.

        Args:
            name: Unique identifier for this allele
            type: Allele type - "log", "linear", or "linear_integer"
            starting_value: Initial value for this allele
            min: Minimum bound (required for log, optional for others)
            max: Maximum bound (optional)
            std: Initial mutation standard deviation (default 0.1)

        Raises:
            ValueError: If allele name conflicts with reserved keys or already exists
            ValueError: If type is unknown or parameters are invalid
        """
        # Validate name
        if name.startswith("__") and name.endswith("__"):
            raise ValueError(f"Allele name '{name}' conflicts with reserved keys")
        if name in self._alleles:
            raise ValueError(f"Allele '{name}' already exists")

        # Create appropriate allele type
        if type == "log":
            if min is None:
                raise ValueError(f"Log allele '{name}' requires min bound")
            allele = LogAllele(
                value=starting_value,
                std=std,
                min=min,
                max=max,
            )
        elif type == "linear":
            allele = LinearAllele(
                value=starting_value,
                std=std,
                min=min,
                max=max,
            )
        elif type == "linear_integer":
            allele = LinearIntegerAllele(
                value=int(starting_value),
                std=std,
                min=int(min) if min is not None else None,
                max=int(max) if max is not None else None,
            )
        else:
            raise ValueError(f"Unknown allele type: {type}")

        self._alleles[name] = allele

    def mutate(self) -> None:
        """
        Apply hierarchical mutation algorithm to the genome.

        Orchestrates two-phase mutation:
        1. Call mutate_std() on all alleles (using meta-control parameters)
        2. Call mutate() on all alleles (using their own stds)

        Uses Python's random module for all stochastic decisions.
        """
        meta = self._alleles["__meta__"].get_value()

        # Phase 1: Mutate all allele stds
        for name, allele in self._alleles.items():
            if name == "__meta__":
                continue  # Meta doesn't mutate itself

            allele.mutate_std(**meta)

        # Phase 2: Mutate all allele values
        mutation_rate = meta["mutation_rate"]
        for name, allele in self._alleles.items():
            if name == "__meta__":
                continue  # Meta doesn't mutate

            allele.mutate(mutation_rate)

    def crossbreed(
            self,
            other: "Genome",
    ) -> "Genome":
        """
        Create offspring genome via crossbreeding.

        Each allele independently chooses to inherit from self or other (50/50).

        Args:
            other: Another genome to crossbreed with

        Returns:
            New offspring genome

        Raises:
            ValueError: If genomes have incompatible allele sets
        """
        if set(self._alleles.keys()) != set(other._alleles.keys()):
            raise ValueError("Cannot crossbreed genomes with different allele sets")

        offspring_alleles = {}
        for name in self._alleles:
            offspring_alleles[name] = self._alleles[name].crossbreed(other._alleles[name])

        offspring = Genome(_alleles=offspring_alleles)
        return offspring

    def set_fitness(
            self,
            value: float,
    ) -> None:
        """
        Set the fitness value for this genome.

        Args:
            value: Fitness value (e.g., validation loss or accuracy)
        """
        self._fitness = value

    def get_fitness(self) -> Optional[float]:
        """
        Get the fitness value for this genome.

        Returns:
            Fitness value, or None if not yet set
        """
        return self._fitness

    def to_dict(self) -> Dict[str, Any]:
        """
        Export allele values as a simple dict for training.

        Returns:
            Dict mapping allele names to their current values
            (excludes meta-controls and fitness)
        """
        result = {}
        for name, allele in self._alleles.items():
            if name == "__meta__":
                continue
            result[name] = allele.get_value()
        return result

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the complete genome structure to a dict.

        Returns:
            Complete structure with all alleles and fitness (format-agnostic)
        """
        alleles_data = {}
        for name, allele in self._alleles.items():
            alleles_data[name] = allele.serialize()

        return {
            "alleles": alleles_data,
            "fitness": self._fitness,
        }

    @classmethod
    def deserialize(
            cls,
            data: Dict[str, Any],
    ) -> "Genome":
        """
        Reconstruct a Genome from serialized data.

        Args:
            data: Serialized genome structure (from serialize())

        Returns:
            Reconstructed Genome instance
        """
        # Deserialize all alleles
        alleles = {}
        for name, allele_data in data["alleles"].items():
            alleles[name] = deserialize_allele(allele_data)

        # Create genome with alleles
        genome = cls(_alleles=alleles)

        # Restore fitness if present
        if data.get("fitness") is not None:
            genome.set_fitness(data["fitness"])

        return genome

    def save(
            self,
            path: str,
    ) -> None:
        """
        Save genome to a JSON file.

        Args:
            path: File path to save to
        """
        with open(path, 'w') as f:
            json.dump(self.serialize(), f, indent=2)

    @classmethod
    def load(
            cls,
            path: str,
    ) -> "Genome":
        """
        Load genome from a JSON file.

        Args:
            path: File path to load from

        Returns:
            Loaded Genome instance
        """
        with open(path, 'r') as f:
            data = json.load(f)
        return cls.deserialize(data)

    def __repr__(self) -> str:
        """String representation of genome showing allele values and fitness."""
        alleles = self.to_dict()
        fitness = self.get_fitness()
        return f"Genome(alleles={alleles}, fitness={fitness})"