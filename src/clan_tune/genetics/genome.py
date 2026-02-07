"""Genome system for ClanTune genetics."""

from uuid import UUID, uuid4
from typing import Dict, List, Optional, Any, Callable, Generator, Tuple, Literal

from .alleles import (
    AbstractAllele,
    FloatAllele,
    IntAllele,
    LogFloatAllele,
    BoolAllele,
    StringAllele,
    walk_allele_trees,
    synthesize_allele_trees,
)


# Type registry for string-based dispatch
_ALLELE_TYPE_REGISTRY: Dict[str, type] = {
    "float": FloatAllele,
    "int": IntAllele,
    "logfloat": LogFloatAllele,
    "bool": BoolAllele,
    "string": StringAllele,
}

AlleleTypeKey = Literal["float", "int", "logfloat", "bool", "string"]


# Module utilities (public, stateless)

def walk_genome_alleles(
    genomes: List["Genome"],
    handler: Callable[[List[AbstractAllele]], Optional[Any]],
    predicate: Optional[Callable[[AbstractAllele], bool]] = None,
    **kwargs
) -> Generator[Any, None, None]:
    """
    Walk multiple genomes' alleles in parallel, yield handler results.

    Orchestrates parallel walking of genomes for information retrieval. Delegates
    tree walking to walk_allele_trees while handling genome-level coordination.

    Lists are passed in population/rank order. Handlers can extract information
    about specific population members by index.

    Args:
        genomes: List of genomes to walk in parallel (in rank order)
        handler: Function receiving list of alleles (one per genome) and kwargs,
            returns Optional[Any]. Called at each node passing predicate.
        predicate: Optional filter deciding whether to call handler at a node.
            Applied to all alleles at a node; handler called only if all pass.
        **kwargs: Keyword arguments passed to handler at each invocation

    Yields:
        Non-None values returned by handler

    Raises:
        ValueError: If genomes have different hyperparameter keys
        TypeError: If alleles are not all the same type at any node (from walk_allele_trees)
    """
    if not genomes:
        return

    # Validate all genomes have same hyperparameter keys
    first_keys = set(genomes[0].alleles.keys())
    for genome in genomes[1:]:
        if set(genome.alleles.keys()) != first_keys:
            raise ValueError("All genomes must have same hyperparameter keys")

    # Walk each hyperparameter in parallel
    for hyperparam_name in genomes[0].alleles.keys():
        # Extract alleles for this hyperparameter from all genomes
        alleles = [genome.alleles[hyperparam_name] for genome in genomes]

        # Create closure adapting handler to inject kwargs
        def adapted_handler(allele_list: List[AbstractAllele]) -> Optional[Any]:
            return handler(allele_list, **kwargs)

        # Delegate to allele utility
        yield from walk_allele_trees(alleles, adapted_handler, predicate)


def synthesize_genomes(
    main_genome: "Genome",
    population: List["Genome"],
    handler: Callable[[AbstractAllele, List[AbstractAllele]], AbstractAllele],
    predicate: Optional[Callable[[AbstractAllele], bool]] = None,
    **kwargs
) -> "Genome":
    """
    Synthesize new genome from population using handler.

    Orchestrates genome synthesis by delegating allele tree synthesis to
    synthesize_allele_trees. The main_genome defines structure (template);
    allele utilities handle tree synthesis; this utility adapts handlers and
    constructs results.

    Result has new UUID, no fitness, no ancestry. Strategies should add ancestry
    separately via with_ancestry().

    Args:
        main_genome: Template genome (must be in population). Used for structure
            and as default when predicate skips nodes.
        population: List of genomes to synthesize from (must include main_genome).
            Alleles extracted in list order (typically rank order).
        handler: Function receiving (template_allele, source_alleles, **kwargs)
            and returning new allele. Template has resolved metadata (children
            already synthesized). Sources are flattened.
        predicate: Optional filter. Handler called only if template passes.
            If template fails, template allele used as-is (skip handler).
        **kwargs: Keyword arguments passed to handler at each invocation

    Returns:
        New genome with synthesized alleles (new UUID, no parents, no fitness)

    Raises:
        ValueError: If main_genome not in population, population empty, or genomes
            have different hyperparameter keys
        TypeError/ValueError: Schema mismatches (from synthesize_allele_trees)
    """
    # Validate inputs
    if not population:
        raise ValueError("synthesize_genomes requires non-empty population")
    if main_genome not in population:
        raise ValueError("main_genome must be present in population")

    # Validate all genomes have same hyperparameter keys
    first_keys = set(population[0].alleles.keys())
    for genome in population[1:]:
        if set(genome.alleles.keys()) != first_keys:
            raise ValueError("All genomes must have same hyperparameter keys")

    # Find template position
    template_idx = population.index(main_genome)

    # Synthesize alleles for each hyperparameter
    new_alleles = {}
    for hyperparam_name in population[0].alleles.keys():
        # Extract alleles for this hyperparameter
        alleles = [genome.alleles[hyperparam_name] for genome in population]
        template_allele = alleles[template_idx]

        # Create closure adapting handler to inject kwargs
        def adapted_handler(
            template: AbstractAllele,
            sources: List[AbstractAllele]
        ) -> AbstractAllele:
            return handler(template, sources, **kwargs)

        # Delegate to allele utility
        synthesized_allele = synthesize_allele_trees(
            template_allele,
            alleles,
            adapted_handler,
            predicate
        )

        new_alleles[hyperparam_name] = synthesized_allele

    # Return new genome with synthesized alleles (new UUID, no parents, no fitness)
    return Genome(uuid=uuid4(), alleles=new_alleles, parents=None, fitness=None)


class Genome:
    """
    Immutable container for evolvable hyperparameters.

    A genome stores a collection of named alleles (hyperparameters), tracks fitness,
    and records parent ancestry for genetic lineage. All operations return new genome
    instances - genomes are never modified in place.

    Genome is a thin coordination layer that delegates tree operations to allele
    utilities (walk_allele_trees, synthesize_allele_trees) while providing convenient
    APIs for orchestrators and strategies.
    """

    def __init__(
        self,
        uuid: Optional[UUID] = None,
        alleles: Optional[Dict[str, AbstractAllele]] = None,
        parents: Optional[List[Tuple[float, UUID]]] = None,
        fitness: Optional[float] = None,
    ):
        """
        Construct a genome.

        Args:
            uuid: Unique identifier. If None, generates new UUID.
            alleles: Mapping of hyperparameter names to alleles. If None, empty dict.
            parents: Ancestry record as list of (probability, uuid) tuples in rank order.
                None for initial genomes with no ancestry.
            fitness: Evaluation result. None until assigned.
        """
        self._uuid = uuid if uuid is not None else uuid4()
        self._alleles = alleles if alleles is not None else {}
        self._parents = parents
        self._fitness = fitness

    # Properties

    @property
    def uuid(self) -> UUID:
        """Unique immutable identifier for this genome."""
        return self._uuid

    @property
    def alleles(self) -> Dict[str, AbstractAllele]:
        """Mapping of hyperparameter names to alleles."""
        return self._alleles

    @property
    def parents(self) -> Optional[List[Tuple[float, UUID]]]:
        """
        Ancestry record.

        Returns None for initial genomes with no ancestry, otherwise a list of
        (probability, uuid) tuples in rank order where index corresponds to rank.
        Probability 0.0 means no contribution from that rank.
        """
        return self._parents

    @property
    def fitness(self) -> Optional[float]:
        """Evaluation result. None until assigned."""
        return self._fitness

    # Core rebuilding method

    def with_overrides(
        self,
        uuid: Optional[UUID] = None,
        alleles: Optional[Dict[str, AbstractAllele]] = None,
        parents: Optional[List[Tuple[float, UUID]]] = None,
        fitness: Optional[float] = None,
    ) -> "Genome":
        """
        Reconstruct genome with specified fields replaced.

        This is the only method that can preserve UUID when rebuilding. All other
        methods generate new UUIDs. Use this for general-purpose rebuilding.

        Args:
            uuid: New UUID, or None to preserve current UUID
            alleles: New alleles dict, or None to preserve current alleles
            parents: New parents, or None to preserve current parents
            fitness: New fitness, or None to preserve current fitness

        Returns:
            New genome with specified fields replaced
        """
        return Genome(
            uuid=uuid if uuid is not None else self._uuid,
            alleles=alleles if alleles is not None else self._alleles,
            parents=parents if parents is not None else self._parents,
            fitness=fitness if fitness is not None else self._fitness,
        )

    # Orchestrator methods

    def add_hyperparameter(
        self,
        name: str,
        value: Any,
        allele_type: AlleleTypeKey,
        **allele_kwargs
    ) -> "Genome":
        """
        Return new genome with added hyperparameter.

        Uses string-based type dispatch to create the appropriate allele type.
        Supported types: "float", "int", "logfloat", "bool", "string".

        Args:
            name: Hyperparameter name (conventionally encodes patch path, e.g., "optimizer/0/lr")
            value: Initial value for the hyperparameter
            allele_type: String key specifying allele type
            **allele_kwargs: Additional arguments passed to allele constructor
                (e.g., domain, can_mutate, can_crossbreed, metadata)

        Returns:
            New genome with hyperparameter added (new UUID, preserves parents and fitness)

        Raises:
            KeyError: If allele_type is not a recognized type key
        """
        # Dispatch to concrete allele class
        allele_class = _ALLELE_TYPE_REGISTRY[allele_type]
        new_allele = allele_class(value, **allele_kwargs)

        # Build new alleles dict
        new_alleles = {**self._alleles, name: new_allele}

        # Use with_overrides to preserve parents and fitness, generate new UUID
        return self.with_overrides(uuid=uuid4(), alleles=new_alleles)

    def as_hyperparameters(self) -> Dict[str, Any]:
        """
        Extract hyperparameters as name → value mapping.

        Returns allele values (not allele objects) for use by orchestrators
        applying hyperparameters to training systems.

        Returns:
            Dict mapping hyperparameter names to their values
        """
        return {name: allele.value for name, allele in self._alleles.items()}

    def set_fitness(self, value: float, new_uuid: bool = False) -> "Genome":
        """
        Return new genome with fitness assigned.

        By default, preserves UUID (this is the only method besides with_overrides
        that can do so). Set new_uuid=True to generate new UUID.

        Args:
            value: Fitness value to assign
            new_uuid: If True, generate new UUID; if False (default), preserve UUID

        Returns:
            New genome with fitness assigned
        """
        if new_uuid:
            return self.with_overrides(uuid=uuid4(), fitness=value)
        else:
            return self.with_overrides(fitness=value)

    def get_fitness(self) -> Optional[float]:
        """
        Retrieve current fitness value.

        Returns:
            Fitness value, or None if not yet assigned
        """
        return self._fitness

    # Serialization methods

    def serialize(self) -> Dict[str, Any]:
        """
        Convert genome to dict, including recursive allele serialization.

        Returns:
            Dict with "uuid", "alleles", "parents", "fitness" fields.
            Alleles are recursively serialized via allele.serialize().
            UUIDs are converted to strings for JSON compatibility.
        """
        # Serialize alleles dict (recursive via allele.serialize())
        serialized_alleles = {
            name: allele.serialize() for name, allele in self._alleles.items()
        }

        # Serialize parents (convert UUIDs to strings)
        serialized_parents = None
        if self._parents is not None:
            serialized_parents = [
                (probability, str(uuid)) for probability, uuid in self._parents
            ]

        return {
            "uuid": str(self._uuid),
            "alleles": serialized_alleles,
            "parents": serialized_parents,
            "fitness": self._fitness,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "Genome":
        """
        Reconstruct genome from serialized dict.

        Args:
            data: Dict from serialize() containing "uuid", "alleles", "parents", "fitness"

        Returns:
            Reconstructed Genome instance with exact state from serialization
        """
        # Deserialize UUID
        uuid = UUID(data["uuid"])

        # Deserialize alleles (recursive via AbstractAllele.deserialize())
        alleles = {
            name: AbstractAllele.deserialize(allele_data)
            for name, allele_data in data["alleles"].items()
        }

        # Deserialize parents (convert UUID strings back to UUIDs)
        parents = None
        if data["parents"] is not None:
            parents = [
                (probability, UUID(uuid_str))
                for probability, uuid_str in data["parents"]
            ]

        fitness = data["fitness"]

        return cls(uuid=uuid, alleles=alleles, parents=parents, fitness=fitness)

    # Strategy support methods

    def with_alleles(self, alleles: Dict[str, AbstractAllele]) -> "Genome":
        """
        Reconstruct genome with new allele package.

        Args:
            alleles: New alleles dict to use

        Returns:
            New genome with new alleles (new UUID, preserves parents and fitness)
        """
        return self.with_overrides(uuid=uuid4(), alleles=alleles)

    def with_ancestry(self, parents: List[Tuple[float, UUID]]) -> "Genome":
        """
        Reconstruct genome with new ancestry package.

        Args:
            parents: New parents list in rank order

        Returns:
            New genome with new ancestry (new UUID, preserves alleles and fitness)
        """
        return self.with_overrides(uuid=uuid4(), parents=parents)

    def update_alleles(
        self,
        handler: Callable[[AbstractAllele], AbstractAllele],
        predicate: Optional[Callable[[AbstractAllele], bool]] = None,
        **kwargs
    ) -> "Genome":
        """
        Walk alleles, apply handler to each, return new genome with transformed alleles.

        Thin wrapper over synthesize_genomes for single-genome updates (mutation pattern).
        Handler receives single allele, returns new allele. Alleles failing predicate
        are skipped (preserved unchanged).

        Args:
            handler: Function receiving allele and kwargs, returns new allele
            predicate: Optional filter. Handler called only if allele passes.
            **kwargs: Keyword arguments passed to handler

        Returns:
            New genome with transformed alleles (new UUID, no parents, no fitness)
        """
        # Adapt handler from (allele, **kwargs) to (template, sources, **kwargs)
        def adapted_handler(
            template: AbstractAllele,
            sources: List[AbstractAllele],
            **handler_kwargs
        ) -> AbstractAllele:
            # Single-allele handler - just use template
            return handler(template, **handler_kwargs)

        # Delegate to synthesize_genomes with self as both template and only source
        return synthesize_genomes(self, [self], adapted_handler, predicate, **kwargs)

    def synthesize_new_alleles(
        self,
        population: List["Genome"],
        handler: Callable[[AbstractAllele, List[AbstractAllele]], AbstractAllele],
        predicate: Optional[Callable[[AbstractAllele], bool]] = None,
        **kwargs
    ) -> "Genome":
        """
        Synthesize new genome from self and population (crossbreeding pattern).

        Thin wrapper over synthesize_genomes using self as template. Result has
        new alleles, new UUID, no fitness, no parents. Strategies should add ancestry
        separately via with_ancestry().

        Args:
            population: List of genomes to synthesize from (should include self)
            handler: Function receiving (template_allele, source_alleles, **kwargs)
                and returning new allele
            predicate: Optional filter. Handler called only if template passes.
            **kwargs: Keyword arguments passed to handler

        Returns:
            New genome with synthesized alleles (new UUID, no parents, no fitness)
        """
        # Ensure self is in population (validation in synthesize_genomes will check)
        return synthesize_genomes(self, population, handler, predicate, **kwargs)
