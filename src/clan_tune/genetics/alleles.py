"""
Allele system for ClanTune genetics.

Alleles are immutable data containers representing evolvable parameters.
They form trees via metadata, enabling metalearning where mutation parameters
evolve alongside the values they control.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable, Generator, Union


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

    def flatten(self) -> "AbstractAllele":
        """
        Return a new allele with metadata alleles replaced by their values.

        Flattening simplifies handler logic in tree utilities by hiding recursion.
        Handlers receive alleles with only raw values in metadata, never nested alleles.

        Raw metadata values (int, float, str, etc.) remain unchanged.
        Allele values in metadata are replaced with their .value property.

        Returns:
            New allele instance with flattened metadata

        Example:
            >>> child = FloatAllele(10.0)
            >>> parent = FloatAllele(5.0, metadata={"std": child, "rate": 0.1})
            >>> flat = parent.flatten()
            >>> flat.metadata["std"]  # 10.0 (raw value, not allele)
            >>> flat.metadata["rate"]  # 0.1 (unchanged)
        """
        flattened_metadata = {}
        for key, val in self._metadata.items():
            if isinstance(val, AbstractAllele):
                flattened_metadata[key] = val.value
            else:
                flattened_metadata[key] = val
        return self.with_metadata(**flattened_metadata)

    def unflatten(self, resolved_metadata: Dict[str, "AbstractAllele"]) -> "AbstractAllele":
        """
        Return a new allele with resolved alleles merged back into metadata.

        Unflattening restores tree structure after handlers return. Takes a dict
        mapping metadata keys to resolved allele objects and replaces flattened
        values with the actual alleles.

        Keys in resolved_metadata replace corresponding entries in self.metadata.
        Keys not in resolved_metadata remain unchanged.

        Args:
            resolved_metadata: Dict mapping metadata keys to resolved Allele objects

        Returns:
            New allele instance with resolved alleles restored

        Example:
            >>> flat = FloatAllele(5.0, metadata={"std": 10.0, "rate": 0.1})
            >>> resolved = {"std": FloatAllele(20.0)}
            >>> unflat = flat.unflatten(resolved)
            >>> isinstance(unflat.metadata["std"], FloatAllele)  # True
            >>> unflat.metadata["std"].value  # 20.0
            >>> unflat.metadata["rate"]  # 0.1 (unchanged)
        """
        merged_metadata = self._metadata.copy()
        merged_metadata.update(resolved_metadata)
        return self.with_metadata(**merged_metadata)

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


class FloatAllele(AbstractAllele):
    """
    Floating point allele with linear semantics.

    Domain is a dict with optional "min" and "max" keys defining the valid range.
    Values are clamped to bounds during construction and with_value().
    Anything not provided is unbounded (indicated by absence from domain dict).
    max can be None for unbounded above.

    Example:
        >>> allele = FloatAllele(0.5, domain={"min": 0.0, "max": 1.0})
        >>> allele.value
        0.5
        >>> clamped = FloatAllele(1.5, domain={"min": 0.0, "max": 1.0})
        >>> clamped.value
        1.0
        >>> unbounded = FloatAllele(100.0)
        >>> unbounded.value
        100.0
    """

    def __init__(
        self,
        value: float,
        domain: Optional[Dict[str, Optional[float]]] = None,
        can_mutate: bool = True,
        can_crossbreed: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a FloatAllele.

        Args:
            value: The float value
            domain: Dict with "min" and "max" keys. None indicates unbounded.
                If not provided, defaults to fully unbounded.
            can_mutate: Whether this allele should participate in mutation
            can_crossbreed: Whether this allele should participate in crossbreeding
            metadata: Optional metadata dict
        """
        # Normalize domain to always have both keys
        if domain is None:
            self._domain = {"min": None, "max": None}
        else:
            self._domain = {
                "min": domain.get("min"),
                "max": domain.get("max"),
            }

        # Clamp value to domain bounds
        clamped_value = value
        if self._domain["min"] is not None:
            clamped_value = max(self._domain["min"], clamped_value)
        if self._domain["max"] is not None:
            clamped_value = min(self._domain["max"], clamped_value)

        super().__init__(clamped_value, can_mutate, can_crossbreed, metadata)

    @property
    def value(self) -> float:
        """The float value."""
        return super().value

    @property
    def domain(self) -> Dict[str, Optional[float]]:
        """Return domain constraints (copy for safety)."""
        return self._domain.copy()

    def with_overrides(self, **constructor_overrides: Any) -> "FloatAllele":
        """
        Construct new FloatAllele with specified overrides.

        Args:
            **constructor_overrides: Constructor arguments to override

        Returns:
            New FloatAllele instance
        """
        return FloatAllele(
            value=constructor_overrides.get("value", self.value),
            domain=constructor_overrides.get("domain", self._domain),
            can_mutate=constructor_overrides.get("can_mutate", self.can_mutate),
            can_crossbreed=constructor_overrides.get("can_crossbreed", self.can_crossbreed),
            metadata=constructor_overrides.get("metadata", self._metadata),
        )

    def serialize_subclass(self) -> Dict[str, Any]:
        """
        Serialize FloatAllele-specific fields.

        Returns:
            Dict with value, domain, and flags
        """
        return {
            "value": self.value,
            "domain": self.domain,
            "can_mutate": self.can_mutate,
            "can_crossbreed": self.can_crossbreed,
        }

    @classmethod
    def deserialize_subclass(
        cls, data: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "FloatAllele":
        """
        Deserialize FloatAllele from data.

        Args:
            data: Serialized data dict
            metadata: Pre-deserialized metadata

        Returns:
            Reconstructed FloatAllele
        """
        return cls(
            value=data["value"],
            domain=data["domain"],
            can_mutate=data["can_mutate"],
            can_crossbreed=data["can_crossbreed"],
            metadata=metadata,
        )


class IntAllele(AbstractAllele):
    """
    Integer allele with float backing.

    IntAllele stores a float internally but exposes a rounded integer via the
    value property. This design enables smooth continuous exploration during
    mutation (mutating the underlying float) while presenting discrete integer
    values to the training system.

    The with_value method accepts floats to support this exploration pattern.
    The raw_value property exposes the underlying float for inspection.

    Domain is a dict with "min" and "max" keys (int or None).
    Values are clamped to bounds as floats, then value property rounds to int.
    None indicates unbounded in that direction.

    Example:
        >>> allele = IntAllele(3.7, domain={"min": 0, "max": 10})
        >>> allele.value  # Rounded int
        4
        >>> allele.raw_value  # Underlying float
        3.7
        >>> allele.with_value(4.2).value
        4
    """

    def __init__(
        self,
        value: Union[int, float],
        domain: Optional[Dict[str, Optional[int]]] = None,
        can_mutate: bool = True,
        can_crossbreed: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an IntAllele.

        Args:
            value: The value (int or float, converted to float internally)
            domain: Dict with "min" and "max" keys (int or None). None indicates unbounded.
            can_mutate: Whether this allele should participate in mutation
            can_crossbreed: Whether this allele should participate in crossbreeding
            metadata: Optional metadata dict
        """
        # Normalize domain to always have both keys
        if domain is None:
            self._domain = {"min": None, "max": None}
        else:
            self._domain = {
                "min": domain.get("min"),
                "max": domain.get("max"),
            }

        # Convert to float internally
        float_value = float(value)

        # Clamp the float to domain bounds
        if self._domain["min"] is not None:
            float_value = max(float(self._domain["min"]), float_value)
        if self._domain["max"] is not None:
            float_value = min(float(self._domain["max"]), float_value)

        # Store the float in superclass
        super().__init__(float_value, can_mutate, can_crossbreed, metadata)

    @property
    def value(self) -> int:
        """The rounded integer value."""
        return round(super().value)

    @property
    def raw_value(self) -> float:
        """The underlying float value."""
        return super().value

    @property
    def domain(self) -> Dict[str, Optional[int]]:
        """Return domain constraints (copy for safety)."""
        return self._domain.copy()

    def with_value(self, new_value: Union[int, float]) -> "IntAllele":
        """
        Return a new allele with updated value.

        Args:
            new_value: The new value (int or float, converted to float internally)

        Returns:
            New IntAllele instance with updated value
        """
        return self.with_overrides(value=float(new_value))

    def with_overrides(self, **constructor_overrides: Any) -> "IntAllele":
        """
        Construct new IntAllele with specified overrides.

        Args:
            **constructor_overrides: Constructor arguments to override

        Returns:
            New IntAllele instance
        """
        return IntAllele(
            value=constructor_overrides.get("value", self.raw_value),
            domain=constructor_overrides.get("domain", self._domain),
            can_mutate=constructor_overrides.get("can_mutate", self.can_mutate),
            can_crossbreed=constructor_overrides.get("can_crossbreed", self.can_crossbreed),
            metadata=constructor_overrides.get("metadata", self._metadata),
        )

    def serialize_subclass(self) -> Dict[str, Any]:
        """
        Serialize IntAllele-specific fields.

        Returns:
            Dict with value (float), domain, and flags
        """
        return {
            "value": self.raw_value,
            "domain": self.domain,
            "can_mutate": self.can_mutate,
            "can_crossbreed": self.can_crossbreed,
        }

    @classmethod
    def deserialize_subclass(
        cls, data: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "IntAllele":
        """
        Deserialize IntAllele from data.

        Args:
            data: Serialized data dict
            metadata: Pre-deserialized metadata

        Returns:
            Reconstructed IntAllele
        """
        return cls(
            value=data["value"],
            domain=data["domain"],
            can_mutate=data["can_mutate"],
            can_crossbreed=data["can_crossbreed"],
            metadata=metadata,
        )


class LogFloatAllele(AbstractAllele):
    """
    Floating point allele with log-space semantics.

    Domain is a dict with "min" and "max" keys.
    min must be provided and must be > 0 (raises ValueError otherwise).
    Values are clamped to bounds during construction and with_value().
    None indicates unbounded in that direction.

    Example:
        >>> allele = LogFloatAllele(0.001, domain={"min": 1e-6, "max": 1e-2})
        >>> allele.value
        0.001
        >>> clamped = LogFloatAllele(1e-10, domain={"min": 1e-6, "max": 1e-2})
        >>> clamped.value
        1e-06
    """

    def __init__(
        self,
        value: float,
        domain: Optional[Dict[str, Optional[float]]] = None,
        can_mutate: bool = True,
        can_crossbreed: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a LogFloatAllele.

        Args:
            value: The float value
            domain: Dict with "min" and "max" keys. min must be > 0. None indicates unbounded.
            can_mutate: Whether this allele should participate in mutation
            can_crossbreed: Whether this allele should participate in crossbreeding
            metadata: Optional metadata dict

        Raises:
            ValueError: If domain min is missing or <= 0
        """
        # Normalize domain to always have both keys
        if domain is None:
            self._domain = {"min": None, "max": None}
        else:
            self._domain = {
                "min": domain.get("min"),
                "max": domain.get("max"),
            }

        # Validate that min exists and is > 0
        if self._domain["min"] is None:
            raise ValueError("LogFloatAllele requires domain min to be specified")
        if self._domain["min"] <= 0:
            raise ValueError(f"LogFloatAllele domain min must be > 0, got {self._domain['min']}")

        # Clamp value to domain bounds
        clamped_value = value
        if self._domain["min"] is not None:
            clamped_value = max(self._domain["min"], clamped_value)
        if self._domain["max"] is not None:
            clamped_value = min(self._domain["max"], clamped_value)

        super().__init__(clamped_value, can_mutate, can_crossbreed, metadata)

    @property
    def value(self) -> float:
        """The float value."""
        return super().value

    @property
    def domain(self) -> Dict[str, Optional[float]]:
        """Return domain constraints (copy for safety)."""
        return self._domain.copy()

    def with_overrides(self, **constructor_overrides: Any) -> "LogFloatAllele":
        """
        Construct new LogFloatAllele with specified overrides.

        Args:
            **constructor_overrides: Constructor arguments to override

        Returns:
            New LogFloatAllele instance
        """
        return LogFloatAllele(
            value=constructor_overrides.get("value", self.value),
            domain=constructor_overrides.get("domain", self._domain),
            can_mutate=constructor_overrides.get("can_mutate", self.can_mutate),
            can_crossbreed=constructor_overrides.get("can_crossbreed", self.can_crossbreed),
            metadata=constructor_overrides.get("metadata", self._metadata),
        )

    def serialize_subclass(self) -> Dict[str, Any]:
        """
        Serialize LogFloatAllele-specific fields.

        Returns:
            Dict with value, domain, and flags
        """
        return {
            "value": self.value,
            "domain": self.domain,
            "can_mutate": self.can_mutate,
            "can_crossbreed": self.can_crossbreed,
        }

    @classmethod
    def deserialize_subclass(
        cls, data: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "LogFloatAllele":
        """
        Deserialize LogFloatAllele from data.

        Args:
            data: Serialized data dict
            metadata: Pre-deserialized metadata

        Returns:
            Reconstructed LogFloatAllele
        """
        return cls(
            value=data["value"],
            domain=data["domain"],
            can_mutate=data["can_mutate"],
            can_crossbreed=data["can_crossbreed"],
            metadata=metadata,
        )


class BoolAllele(AbstractAllele):
    """
    Boolean allele for flag values.

    Domain is always {True, False}.
    Raises ValueError if value is not True or False.

    Example:
        >>> allele = BoolAllele(True)
        >>> allele.value
        True
    """

    def __init__(
        self,
        value: bool,
        can_mutate: bool = True,
        can_crossbreed: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a BoolAllele.

        Args:
            value: The boolean value
            can_mutate: Whether this allele should participate in mutation
            can_crossbreed: Whether this allele should participate in crossbreeding
            metadata: Optional metadata dict

        Raises:
            ValueError: If value is not True or False
        """
        # Domain is always {True, False}
        self._domain = {True, False}

        # Validate value is boolean
        if value not in self._domain:
            raise ValueError(f"Value {value} not in domain {self._domain}")

        super().__init__(value, can_mutate, can_crossbreed, metadata)

    @property
    def value(self) -> bool:
        """The boolean value."""
        return super().value

    @property
    def domain(self) -> set:
        """Return domain constraints (always {True, False})."""
        return self._domain.copy()

    def with_overrides(self, **constructor_overrides: Any) -> "BoolAllele":
        """
        Construct new BoolAllele with specified overrides.

        Args:
            **constructor_overrides: Constructor arguments to override

        Returns:
            New BoolAllele instance
        """
        return BoolAllele(
            value=constructor_overrides.get("value", self.value),
            can_mutate=constructor_overrides.get("can_mutate", self.can_mutate),
            can_crossbreed=constructor_overrides.get("can_crossbreed", self.can_crossbreed),
            metadata=constructor_overrides.get("metadata", self._metadata),
        )

    def serialize_subclass(self) -> Dict[str, Any]:
        """
        Serialize BoolAllele-specific fields.

        Returns:
            Dict with value and flags
        """
        return {
            "value": self.value,
            "can_mutate": self.can_mutate,
            "can_crossbreed": self.can_crossbreed,
        }

    @classmethod
    def deserialize_subclass(
        cls, data: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "BoolAllele":
        """
        Deserialize BoolAllele from data.

        Args:
            data: Serialized data dict
            metadata: Pre-deserialized metadata

        Returns:
            Reconstructed BoolAllele
        """
        return cls(
            value=data["value"],
            can_mutate=data["can_mutate"],
            can_crossbreed=data["can_crossbreed"],
            metadata=metadata,
        )


class StringAllele(AbstractAllele):
    """
    String allele for discrete choices.

    Domain is a set of valid string values.
    Raises ValueError if value is not in domain set.

    Example:
        >>> allele = StringAllele("adam", domain={"adam", "sgd", "rmsprop"})
        >>> allele.value
        'adam'
    """

    def __init__(
        self,
        value: str,
        domain: Optional[set] = None,
        can_mutate: bool = True,
        can_crossbreed: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a StringAllele.

        Args:
            value: The string value
            domain: Set of valid string values
            can_mutate: Whether this allele should participate in mutation
            can_crossbreed: Whether this allele should participate in crossbreeding
            metadata: Optional metadata dict

        Raises:
            ValueError: If domain is None or value is not in domain
        """
        # Domain is required for StringAllele
        if domain is None:
            raise ValueError("StringAllele requires domain to be specified")

        self._domain = domain

        # Validate value is in domain
        if value not in self._domain:
            raise ValueError(f"Value '{value}' not in domain {self._domain}")

        super().__init__(value, can_mutate, can_crossbreed, metadata)

    @property
    def value(self) -> str:
        """The string value."""
        return super().value

    @property
    def domain(self) -> set:
        """Return domain constraints (copy for safety)."""
        return self._domain.copy()

    def with_overrides(self, **constructor_overrides: Any) -> "StringAllele":
        """
        Construct new StringAllele with specified overrides.

        Args:
            **constructor_overrides: Constructor arguments to override

        Returns:
            New StringAllele instance
        """
        return StringAllele(
            value=constructor_overrides.get("value", self.value),
            domain=constructor_overrides.get("domain", self._domain),
            can_mutate=constructor_overrides.get("can_mutate", self.can_mutate),
            can_crossbreed=constructor_overrides.get("can_crossbreed", self.can_crossbreed),
            metadata=constructor_overrides.get("metadata", self._metadata),
        )

    def serialize_subclass(self) -> Dict[str, Any]:
        """
        Serialize StringAllele-specific fields.

        Returns:
            Dict with value, domain (as list for JSON compatibility), and flags
        """
        return {
            "value": self.value,
            "domain": list(self.domain),
            "can_mutate": self.can_mutate,
            "can_crossbreed": self.can_crossbreed,
        }

    @classmethod
    def deserialize_subclass(
        cls, data: Dict[str, Any], metadata: Dict[str, Any]
    ) -> "StringAllele":
        """
        Deserialize StringAllele from data.

        Args:
            data: Serialized data dict
            metadata: Pre-deserialized metadata

        Returns:
            Reconstructed StringAllele
        """
        return cls(
            value=data["value"],
            domain=set(data["domain"]),
            can_mutate=data["can_mutate"],
            can_crossbreed=data["can_crossbreed"],
            metadata=metadata,
        )


# Tree utility functions


def _validate_parallel_types(alleles: List[AbstractAllele]) -> None:
    """
    Validate that all alleles in a list are the same type.

    Args:
        alleles: List of alleles to validate

    Raises:
        TypeError: If alleles are not all the same type
    """
    if not alleles:
        return

    first_type = type(alleles[0])
    if not all(type(a) == first_type for a in alleles):
        types = [type(a).__name__ for a in alleles]
        raise TypeError(f"All alleles must be the same type, got: {types}")


# NOTE: _flatten_metadata() was removed. Use allele.flatten().metadata instead.
# The flatten() method is now part of the public AbstractAllele API.
# Migrate callers to use the instance method rather than this private helper.


def _validate_schemas_match(alleles: List[AbstractAllele]) -> None:
    """
    Validate all alleles have matching schemas (domain, flags).

    Args:
        alleles: List of alleles to validate

    Raises:
        ValueError: If domains or flags don't match across alleles
    """
    first_domain = alleles[0].domain
    if not all(a.domain == first_domain for a in alleles):
        domains = [a.domain for a in alleles]
        raise ValueError(f"Domain mismatch across sources: {domains}")

    first_mutate = alleles[0].can_mutate
    if not all(a.can_mutate == first_mutate for a in alleles):
        flags = [a.can_mutate for a in alleles]
        raise ValueError(f"can_mutate mismatch across sources: {flags}")

    first_crossbreed = alleles[0].can_crossbreed
    if not all(a.can_crossbreed == first_crossbreed for a in alleles):
        flags = [a.can_crossbreed for a in alleles]
        raise ValueError(f"can_crossbreed mismatch across sources: {flags}")


def _should_include_node(
    allele: AbstractAllele, include_can_mutate: bool, include_can_crossbreed: bool
) -> bool:
    """
    Determine if a node should be included based on filtering flags.

    Args:
        allele: The allele to check
        include_can_mutate: If False, exclude nodes with can_mutate=False
        include_can_crossbreed: If False, exclude nodes with can_crossbreed=False

    Returns:
        True if node should be included, False otherwise
    """
    if not include_can_mutate and not allele.can_mutate:
        return False
    if not include_can_crossbreed and not allele.can_crossbreed:
        return False
    return True


def _collect_metadata_keys(alleles: List[AbstractAllele]) -> List[str]:
    """
    Collect all unique metadata keys across multiple alleles in sorted order.

    Args:
        alleles: List of alleles to collect keys from

    Returns:
        Sorted list of unique metadata keys
    """
    all_keys = set()
    for allele in alleles:
        all_keys.update(allele.metadata.keys())
    return sorted(all_keys)


# Main tree walking utilities


def walk_allele_trees(
    alleles: List[AbstractAllele],
    handler: Callable[[List[AbstractAllele]], Optional[Any]],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> Generator[Any, None, None]:
    """
    Walk multiple allele trees in parallel (depth-first, children-first).

    At each node:
    1. Recursively processes all metadata alleles first
    2. Checks filter (can_mutate/can_crossbreed) - skips if filtered out
    3. Flattens metadata: replaces allele entries with .value, leaves raw values unchanged
    4. Passes list of flattened alleles to handler
    5. If handler returns non-None, yields it

    Args:
        alleles: List of allele trees to walk in parallel
        handler: Function receiving list of flattened alleles, returns Optional[Any]
        include_can_mutate: If False, skip nodes with can_mutate=False
        include_can_crossbreed: If False, skip nodes with can_crossbreed=False

    Yields:
        Non-None values returned by handler

    Raises:
        TypeError: If alleles are not all the same type at any node
    """
    # Validate type consistency
    _validate_parallel_types(alleles)

    # Recursively walk all metadata alleles first (children-first)
    for key in _collect_metadata_keys(alleles):
        # Peek to check if this key contains alleles or raw values
        first_value = alleles[0].metadata[key]
        if not isinstance(first_value, AbstractAllele):
            continue  # Raw values, no recursion needed

        # Extract alleles from all trees (validation will catch type mismatches)
        subtrees = [allele.metadata[key] for allele in alleles]
        yield from walk_allele_trees(
            subtrees,
            handler,
            include_can_mutate=include_can_mutate,
            include_can_crossbreed=include_can_crossbreed,
        )

    # Apply filter to current node
    if not _should_include_node(alleles[0], include_can_mutate, include_can_crossbreed):
        return

    # Flatten metadata for handler
    flattened_alleles = [allele.flatten() for allele in alleles]

    # Call handler and yield result if not None
    result = handler(flattened_alleles)
    if result is not None:
        yield result


def _synthesize_allele_trees_impl(
    template_idx: int,
    nodes: List[Union[AbstractAllele, Any]],
    handler: Callable[[AbstractAllele, List[AbstractAllele]], AbstractAllele],
    include_can_mutate: bool,
    include_can_crossbreed: bool,
) -> Union[AbstractAllele, Any]:
    """
    Inner helper for synthesize_allele_trees.

    Handles recursion with template index preservation. Accepts both alleles and raw values,
    using base case check to terminate recursion.

    Args:
        template_idx: Index of template node in nodes list
        nodes: List of nodes (alleles or raw values) to synthesize
        handler: Function receiving (template, sources) and returning new allele
        include_can_mutate: If False, skip nodes with can_mutate=False
        include_can_crossbreed: If False, skip nodes with can_crossbreed=False

    Returns:
        Synthesized allele or validated raw value

    Raises:
        TypeError: If nodes are not all the same type
        ValueError: If raw values don't match or schema mismatch
    """
    # Base case: all raw values (not alleles)
    if not isinstance(nodes[0], AbstractAllele):
        # Validate all raw values match exactly
        if not all(v == nodes[0] for v in nodes):
            raise ValueError(f"Raw value mismatch: {nodes}")
        return nodes[0]

    # We're dealing with alleles - cast for type checker
    alleles: List[AbstractAllele] = nodes  # type: ignore

    # Validate type consistency and schema matching
    _validate_parallel_types(alleles)
    _validate_schemas_match(alleles)

    # Recursively synthesize metadata children first (children-first)
    resolved_metadata = {}
    for key in _collect_metadata_keys(alleles):
        # Always recurse - base case handles raw values
        values = [a.metadata[key] for a in alleles]
        resolved_metadata[key] = _synthesize_allele_trees_impl(
            template_idx,
            values,
            handler,
            include_can_mutate,
            include_can_crossbreed,
        )

    # Create template: source node at template position with resolved metadata
    template_source = alleles[template_idx]
    template = template_source.with_metadata(**resolved_metadata)

    # Check filtering: if excluded, return template (skip handler)
    if not _should_include_node(template, include_can_mutate, include_can_crossbreed):
        return template

    # Flatten template and sources for handler
    flattened_template = template.flatten()
    flattened_sources = [a.flatten() for a in alleles]

    # Call handler with (template, sources)
    result = handler(flattened_template, flattened_sources)

    # Unflatten to restore resolved metadata structure
    return result.unflatten(resolved_metadata)


def synthesize_allele_trees(
    template_tree: AbstractAllele,
    alleles: List[AbstractAllele],
    handler: Callable[[AbstractAllele, List[AbstractAllele]], AbstractAllele],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> AbstractAllele:
    """
    Synthesize multiple allele trees into a single result tree.

    Mental model: You have N source alleles and want to create one result by combining
    their values. The template_tree determines the result's structure (domain, flags,
    metadata schema), while the handler determines how to combine values.

    Handler receives:
    - template: Allele with result structure and resolved metadata (children already
      synthesized and restored to template's metadata)
    - sources: List of flattened source alleles (metadata contains raw values only)

    Handler returns: New allele, typically via template.with_value(combined_value)

    Guarantees:
    - Result structure matches template (domain, flags, metadata keys)
    - All sources validated for schema compatibility (raises ValueError if mismatch)
    - List order preserved across recursion (important for crossbreeding)
    - Filtering respected (can_mutate/can_crossbreed flags)

    See documents/Allele.md lines 89-118 for detailed algorithm specification.

    Args:
        template_tree: Source allele whose structure to use (must be in alleles list)
        alleles: List of source allele trees to synthesize from
        handler: Function receiving (template, sources) and returning new allele
        include_can_mutate: If False, skip nodes with can_mutate=False
        include_can_crossbreed: If False, skip nodes with can_crossbreed=False

    Returns:
        New synthesized tree with template structure and handler-computed values

    Raises:
        ValueError: If template_tree not in alleles, or schema mismatch
        TypeError: If alleles are not all the same type at any node

    Example:
        >>> def average_handler(template, sources):
        ...     avg = sum(s.value for s in sources) / len(sources)
        ...     return template.with_value(avg)
        >>> result = synthesize_allele_trees(parent1, [parent1, parent2], average_handler)
    """
    if not alleles:
        raise ValueError("synthesize_allele_trees requires at least one allele")

    # Validate template_tree is in alleles list
    try:
        template_idx = alleles.index(template_tree)
    except ValueError:
        raise ValueError("template_tree must be present in alleles list")

    # Call inner helper with template index
    return _synthesize_allele_trees_impl(
        template_idx, alleles, handler, include_can_mutate, include_can_crossbreed
    )
