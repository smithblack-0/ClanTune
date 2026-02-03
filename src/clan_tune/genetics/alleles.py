"""
Allele system for ClanTune genetics.

Alleles are immutable data containers representing evolvable parameters.
They form trees via metadata, enabling metalearning where mutation parameters
evolve alongside the values they control.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable, Generator


class AbstractAllele(ABC):
    """
    Abstract base class for all allele types.

    Alleles are immutable containers with five core fields:
    - value: The actual parameter value (type depends on subclass)
    - domain: Constraints on valid values (subclass-specific)
    - can_mutate: Signals whether value should participate in mutation
    - can_crossbreed: Signals whether value should participate in crossbreeding
    - metadata: Recursive tree structure (can contain alleles or raw values)

    All modifications return new instances. Subclasses are automatically registered
    for serialization dispatch via __init_subclass__.

    Subclass Implementation Requirements
    ------------------------------------

    Subclasses must implement four abstract members:

    1. **domain property (Any):**
       - Return the domain constraints for this allele type
       - Type depends on allele: Dict[str, Any] for continuous, Set[Any] for discrete
       - Can be stored in instance variable or computed
       - Called during serialization

    2. **with_overrides(**constructor_overrides) -> AbstractAllele:**
       - Construct new instance with specified constructor arguments overridden
       - Unspecified arguments should default to current state
       - Must pass through constructor for validation

    3. **serialize_subclass() -> Dict[str, Any]:**
       - Serialize this node's fields only (value, domain, can_mutate, etc.)
       - Do not serialize branches (metadata children) - AbstractAllele handles tree recursion
       - Do NOT include "type" or "metadata" in returned dict

    4. **deserialize_subclass(data: Dict, metadata: Dict) -> AbstractAllele:**
       - Classmethod to reconstruct this node from serialized data
       - metadata parameter contains pre-deserialized branches (nested alleles already reconstructed)
       - Extract this node's fields from data dict and pass to constructor

    Constructor Contract
    --------------------

    Subclass constructors should:
    - Accept domain parameter and store it
    - Validate and clamp value according to domain BEFORE calling super().__init__()
    - Call super().__init__(value, can_mutate, can_crossbreed, metadata)
    - Raise errors for invalid values that cannot be clamped
    """

    _registry: Dict[str, type] = {}

    def __init_subclass__(cls, **kwargs):
        """Auto-register subclasses for serialization dispatch."""
        super().__init_subclass__(**kwargs)
        AbstractAllele._registry[cls.__name__] = cls

    def __init__(
        self,
        value: Any,
        can_mutate: bool = True,
        can_crossbreed: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an allele.

        Args:
            value: The parameter value (never an allele, always raw type)
            can_mutate: Whether this allele should participate in mutation
            can_crossbreed: Whether this allele should participate in crossbreeding
            metadata: Optional metadata dict (can contain alleles or raw values)

        Note: Subclasses should validate and clamp value according to their domain
        before calling super().__init__().
        """
        self._value = value
        self._can_mutate = can_mutate
        self._can_crossbreed = can_crossbreed
        self._metadata = metadata if metadata is not None else {}

    @property
    def value(self) -> Any:
        """The actual parameter value."""
        return self._value

    @property
    @abstractmethod
    def domain(self) -> Any:
        """
        Domain constraints on valid values.

        Type depends on subclass:
        - Dict[str, Any] for continuous types (min/max)
        - Set[Any] for discrete types
        """
        pass

    @property
    def can_mutate(self) -> bool:
        """Whether this allele should participate in mutation."""
        return self._can_mutate

    @property
    def can_crossbreed(self) -> bool:
        """Whether this allele should participate in crossbreeding."""
        return self._can_crossbreed

    @property
    def metadata(self) -> Dict[str, Any]:
        """Metadata dict (can contain alleles or raw values)."""
        return self._metadata.copy()

    def with_value(self, new_value: Any) -> "AbstractAllele":
        """
        Return a new allele with updated value.

        Applies domain validation and clamping through constructor.

        Args:
            new_value: The new value

        Returns:
            New allele instance with updated value
        """
        return self.with_overrides(value=new_value)

    def with_metadata(self, **updates: Any) -> "AbstractAllele":
        """
        Return a new allele with metadata entries added or updated.

        Args:
            **updates: Metadata entries to add or update

        Returns:
            New allele instance with updated metadata
        """
        new_metadata = self._metadata.copy()
        new_metadata.update(updates)
        return self.with_overrides(metadata=new_metadata)

    def walk_tree(
        self,
        handler: Callable[[List["AbstractAllele"]], Optional[Any]],
        include_can_mutate: bool = True,
        include_can_crossbreed: bool = True,
        _walker: Optional[Callable] = None,
    ) -> Generator[Any, None, None]:
        """
        Walk this allele's tree and yield results.

        Thin wrapper around walk_allele_trees for single-tree use.

        Args:
            handler: Function receiving list of flattened alleles
            include_can_mutate: If False, skip nodes with can_mutate=False
            include_can_crossbreed: If False, skip nodes with can_crossbreed=False

        Yields:
            Values returned by handler (if not None)
        """
        walker = _walker if _walker is not None else walk_allele_trees
        yield from walker(
            [self],
            handler,
            include_can_mutate=include_can_mutate,
            include_can_crossbreed=include_can_crossbreed,
        )

    def update_tree(
        self,
        handler: Callable[[List["AbstractAllele"]], Any],
        include_can_mutate: bool = True,
        include_can_crossbreed: bool = True,
        _updater: Optional[Callable] = None,
    ) -> "AbstractAllele":
        """
        Transform this allele's tree.

        Thin wrapper around synthesize_allele_trees for single-tree use.

        Args:
            handler: Function receiving list of flattened alleles and returning new value
            include_can_mutate: If False, skip nodes with can_mutate=False
            include_can_crossbreed: If False, skip nodes with can_crossbreed=False

        Returns:
            New tree with updated values
        """
        updater = _updater if _updater is not None else synthesize_allele_trees
        return updater(
            [self],
            handler,
            include_can_mutate=include_can_mutate,
            include_can_crossbreed=include_can_crossbreed,
        )

    def serialize(self) -> Dict[str, Any]:
        """
        Convert to dict, including recursive metadata serialization.

        Returns:
            Dict with "type", subclass fields, and recursively serialized metadata
        """
        # Handle universal metadata recursion
        serialized_metadata = {}
        for key, val in self._metadata.items():
            if isinstance(val, AbstractAllele):
                serialized_metadata[key] = val.serialize()
            else:
                serialized_metadata[key] = val

        # Get subclass-specific fields
        subclass_data = self.serialize_subclass()

        # Combine with type field and metadata
        return {
            "type": self.__class__.__name__,
            **subclass_data,
            "metadata": serialized_metadata,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "AbstractAllele":
        """
        Reconstruct from dict, dispatching to appropriate subclass.

        Handles type dispatch and recursive metadata deserialization.

        Args:
            data: Dict with "type" field identifying the subclass

        Returns:
            Reconstructed allele instance

        Raises:
            ValueError: If type field is missing or unknown
        """
        allele_type = data.get("type")
        if allele_type is None:
            raise ValueError("Missing 'type' field in serialized allele data")

        allele_class = cls._registry.get(allele_type)
        if allele_class is None:
            raise ValueError(f"Unknown allele type: {allele_type}")

        # Handle universal metadata recursion
        deserialized_metadata = {}
        for key, val in data.get("metadata", {}).items():
            if isinstance(val, dict) and "type" in val:
                # This is a serialized allele
                deserialized_metadata[key] = AbstractAllele.deserialize(val)
            else:
                deserialized_metadata[key] = val

        # Pass to subclass with metadata already handled
        return allele_class.deserialize_subclass(data, deserialized_metadata)

    @abstractmethod
    def serialize_subclass(self) -> Dict[str, Any]:
        """
        Serialize subclass-specific fields.

        Subclasses return dict with their fields (value, domain, can_mutate, etc.).
        Do not include "type" or "metadata" - AbstractAllele handles those.

        Returns:
            Dict with subclass-specific fields
        """
        pass

    @classmethod
    @abstractmethod
    def deserialize_subclass(cls, data: Dict[str, Any], metadata: Dict[str, Any]) -> "AbstractAllele":
        """
        Deserialize subclass from data with pre-deserialized metadata.

        Args:
            data: Dict with all serialized fields (including "type" and "metadata")
            metadata: Pre-deserialized metadata dict (alleles already reconstructed)

        Returns:
            Reconstructed allele instance
        """
        pass

    @abstractmethod
    def with_overrides(self, **constructor_overrides: Any) -> "AbstractAllele":
        """
        Construct a new allele with constructor argument overrides.

        Subclasses implement this to handle their specific constructor signature.
        All unspecified arguments should default to current state.

        Args:
            **constructor_overrides: Constructor arguments to override
                (e.g., value, domain, can_mutate, can_crossbreed, metadata)

        Returns:
            New allele instance constructed with overridden arguments
        """
        pass


# Tree utility functions (to be implemented)


def walk_allele_trees(
    alleles: List[AbstractAllele],
    handler: Callable[[List[AbstractAllele]], Optional[Any]],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> Generator[Any, None, None]:
    """Walk multiple allele trees in parallel. Implementation pending."""
    raise NotImplementedError("walk_allele_trees not yet implemented")


def synthesize_allele_trees(
    alleles: List[AbstractAllele],
    handler: Callable[[List[AbstractAllele]], Any],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> AbstractAllele:
    """Synthesize a single result tree from multiple trees. Implementation pending."""
    raise NotImplementedError("synthesize_allele_trees not yet implemented")
