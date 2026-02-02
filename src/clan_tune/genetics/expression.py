"""
GenomeExpression: Registry-based dispatch for mode-dependent genome expression.

Translates a Genome's alleles into patch and cache dicts given a mode.
Sits between Genome and Member — Genome doesn't know about expression,
Member doesn't know about mode-dependent resolution.

Stateless. Owns nothing. Receives Genome and communicator as needed.

## Allele Metadata Schema (owned here)

Each allele in a Genome has a JSON-encoded key carrying expression metadata.
This is the authoritative definition of that schema:

- path (str): The target path in the State object tree
- is_cooperative (bool): Whether this allele participates in cooperative mode expression
- is_competitive (bool): Whether this allele participates in competitive mode expression
- is_patchable (bool): Whether this allele's expressed value is included in the patch dict

WARNING: Same registry footgun as TreeNodeHandler. Dispatch is first-match
by definition order. A catch-all handler will shadow any handlers defined after it.
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

from .genome import Genome
from ..clan.communication import Communication

class GenomeExpression(ABC):
    """
    GenomeExpression does two things: it lets you add alleles to a Genome with
    expression metadata attached, and it lets you express a Genome into patch
    and cache dicts given a mode.

    To add an allele, call set_allele on a Genome. You provide the path (where
    in the State tree this allele targets), three booleans controlling expression
    behavior (is_cooperative, is_competitive, is_patchable), and then whatever
    the Genome itself needs to create the allele (name, value, type, bounds,
    etc.) as keyword arguments.

    To express, call express with a Genome, a communicator, and a mode string.
    The mode is one of "cooperative", "competitive", or "all". It returns two dicts:

    - patch_dict: ready to hand directly to State.apply_patches(). Contains only
      alleles where is_patchable is True.
    - cache_dict: contains all alleles regardless of patchability. Superset of
      patch_dict.

    Both dicts are {path: value}, where the values have been resolved for the
    given mode. What "resolved" means depends on the mode and the allele's
    metadata — some alleles express their own value, others get averaged across
    the clan via the communicator.
    """

    _registry: list = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        GenomeExpression._registry.append(cls)

    @staticmethod
    @abstractmethod
    def _predicate(mode: str) -> bool:
        """Does this handler own this mode?"""
        ...

    @staticmethod
    @abstractmethod
    def _express(
        value: Any,
        path: str,
        is_cooperative: bool,
        is_competitive: bool,
        communicator: Any,
    ) -> Any:
        """
        Resolve a single allele's value for the current mode.

        Returns:
            The expressed value
        """
        ...

    @classmethod
    def set_allele(
        cls,
        genome: Genome,
        path: str,
        is_cooperative: bool,
        is_competitive: bool,
        is_patchable: bool,
        **genome_kwargs,
    ) -> None:
        """
        Add an allele to a Genome with expression metadata.

        Constructs the JSON key from the metadata fields, passes
        **genome_kwargs through to Genome for allele creation.

        Args:
            genome: Genome to add the allele to
            path: Patch target path in the State object tree
            is_cooperative: Expressed during cooperative mode
            is_competitive: Expressed during competitive mode
            is_patchable: Valid patch target
            **genome_kwargs: Passed through to Genome (name, value, type, bounds, etc.)
        """
        key = json.dumps({
            "path": path,
            "is_cooperative": is_cooperative,
            "is_competitive": is_competitive,
            "is_patchable": is_patchable,
        })
        genome.add_allele(name=key, **genome_kwargs)

    @classmethod
    def express(
        cls,
        genome: Genome,
        communicator: Communication,
        mode: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Express a Genome's alleles given a mode.

        Draws alleles, deserializes keys, filters to patchable, dispatches
        each to the appropriate handler, and assembles the results.

        Args:
            genome: Genome to express
            communicator: Communication object for gather operations
            mode: "cooperative", "competitive", or "all"

        Returns:
            (patch_dict, cache_dict) — patch_dict is ready for State.apply_patches(),
            cache_dict mirrors it for .get_value() lookups

        Raises:
            ValueError: If no handler matches the mode
        """
        handler = None
        for h in cls._registry:
            if h._predicate(mode):
                handler = h
                break
        if handler is None:
            raise ValueError(f"No handler registered for mode '{mode}'")

        patch_dict = {}
        cache_dict = {}

        for json_key, value in genome.to_dict().items():
            metadata = json.loads(json_key)
            if not metadata["is_patchable"]:
                continue

            expressed_value = handler._express(
                value=value,
                path=metadata["path"],
                is_cooperative=metadata["is_cooperative"],
                is_competitive=metadata["is_competitive"],
                communicator=communicator,
            )
            cache_dict[metadata["path"]] = expressed_value
            if metadata["is_patchable"]:
                patch_dict[metadata["path"]] = expressed_value

        return patch_dict, cache_dict


class CooperativeExpression(GenomeExpression):
    """Cooperative mode: is_cooperative alleles expressed directly, is_competitive alleles averaged."""

    @staticmethod
    def _predicate(mode: str) -> bool:
        return mode == "cooperative"

    @staticmethod
    def _express(
        value: Any,
        path: str,
        is_cooperative: bool,
        is_competitive: bool,
        communicator: Communication,
    ) -> Any:
        if is_cooperative:
            return value
        all_values = communicator.gather_objects_list(value)
        return sum(all_values) / len(all_values)


class CompetitiveExpression(GenomeExpression):
    """Competitive mode: is_competitive alleles expressed directly, is_cooperative alleles averaged."""

    @staticmethod
    def _predicate(mode: str) -> bool:
        return mode == "competitive"

    @staticmethod
    def _express(
        value: Any,
        path: str,
        is_cooperative: bool,
        is_competitive: bool,
        communicator: Communication,
    ) -> Any:
        if is_competitive:
            return value
        all_values = communicator.gather_objects_list(value)
        return sum(all_values) / len(all_values)


class AllExpression(GenomeExpression):
    """All mode: everything expressed directly, no gathering."""

    @staticmethod
    def _predicate(mode: str) -> bool:
        return mode == "all"

    @staticmethod
    def _express(
        value: Any,
        path: str,
        is_cooperative: bool,
        is_competitive: bool,
        communicator: Communication,
    ) -> Any:
        return value