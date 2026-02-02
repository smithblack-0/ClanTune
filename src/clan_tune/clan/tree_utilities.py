"""
TreeNodeHandler: Unified interface for walking and patching heterogeneous object trees.
Supported types at time of writing: dict, list, tuple, and arbitrary objects
with __dict__. Check the registry for any additions.

WARNING: This is not a 'subclass and go' kind of tree walking utility.
The resolution system goes off in the order seen in this file as
subclasses are defined. This means after the object handler is defined
no other handlers can be defined, as the object handler will catch any
other handler's cases first.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class TreeNodeHandler(ABC):
    """
    Dispatch layer for walking and patching object trees.

    Use children() and patch() — these are the public interface:
        kids = TreeNodeHandler.children(node)      # -> {"key": value, ...}
        node = TreeNodeHandler.patch(node, kids)   # always reassign

    Internally, these look up the first handler in _registry whose _predicate
    matches the node and delegate to it. Do not call handler methods directly.
    """

    _registry: list = []

    def __init_subclass__(cls, **kwargs):
        """Subclass registry"""
        super().__init_subclass__(**kwargs)
        TreeNodeHandler._registry.append(cls)

    @staticmethod
    @abstractmethod
    def _predicate(node: Any) -> bool:
        """Return True if this handler can handle the given node."""
        ...

    @staticmethod
    @abstractmethod
    def _children(node: Any) -> Dict[str, Any]:
        """Return the node's children as a string-keyed dict."""
        ...

    @staticmethod
    @abstractmethod
    def _patch(node: Any, updates: Dict[str, Any]) -> Any:
        """Return the node with updates applied."""
        ...

    @classmethod
    def _find_handler(cls, node: Any):
        for handler in cls._registry:
            if handler._predicate(node):
                return handler
        return None

    @classmethod
    def has_children(cls, node: Any) -> bool:
        """Return True if any registered handler can handle this node."""
        return cls._find_handler(node) is not None

    @classmethod
    def children(cls, node: Any) -> Dict[str, Any]:
        """
        Return node's children as a string-keyed dict.

        Args:
            node: Any supported container or object

        Returns:
            Dict mapping string keys to child values

        Raises:
            TypeError: If no handler matches the node
        """
        handler = cls._find_handler(node)
        if handler is None:
            raise TypeError(f"No handler registered for {type(node).__name__}")
        return handler._children(node)

    @classmethod
    def patch(cls, node: Any, updates: Dict[str, Any]) -> Any:
        """
        Return node with updates applied. Mutable containers are patched in
        place and returned; immutable containers (tuple) are reconstructed.
        Caller should always reassign the return value.

        Args:
            node: Any supported container or object
            updates: String-keyed dict of values to apply (same format as children())

        Returns:
            The patched node (same object for mutable, new object for tuple)

        Raises:
            TypeError: If no handler matches the node
            KeyError: If an update key does not exist in the node
        """
        handler = cls._find_handler(node)
        if handler is None:
            raise TypeError(f"No handler registered for {type(node).__name__}")
        return handler._patch(node, updates)


class DictHandler(TreeNodeHandler):
    """Handles plain dicts. Keys are used directly as path segments."""

    @staticmethod
    def _predicate(node: Any) -> bool:
        return isinstance(node, dict)

    @staticmethod
    def _children(node: dict) -> Dict[str, Any]:
        return dict(node)

    @staticmethod
    def _patch(node: dict, updates: Dict[str, Any]) -> dict:
        for key, value in updates.items():
            if key not in node:
                raise KeyError(f"Key '{key}' not found in dict")
            node[key] = value
        return node


class ListHandler(TreeNodeHandler):
    """Handles lists. Integer indices are stringified for path segments."""

    @staticmethod
    def _predicate(node: Any) -> bool:
        return isinstance(node, list)

    @staticmethod
    def _children(node: list) -> Dict[str, Any]:
        return {str(i): child for i, child in enumerate(node)}

    @staticmethod
    def _patch(node: list, updates: Dict[str, Any]) -> list:
        for key_str, value in updates.items():
            idx = int(key_str)
            if idx >= len(node):
                raise KeyError(f"Index {idx} out of range for list of length {len(node)}")
            node[idx] = value
        return node


class TupleHandler(TreeNodeHandler):
    """
    Handles tuples. Integer indices are stringified for path segments.

    Tuples are immutable, so _patch reconstructs a new tuple with updates
    applied. This is the one case where patch returns a different object
    than it received — caller must reassign.
    """

    @staticmethod
    def _predicate(node: Any) -> bool:
        return isinstance(node, tuple)

    @staticmethod
    def _children(node: tuple) -> Dict[str, Any]:
        return {str(i): child for i, child in enumerate(node)}

    @staticmethod
    def _patch(node: tuple, updates: Dict[str, Any]) -> tuple:
        as_list = list(node)
        for key_str, value in updates.items():
            idx = int(key_str)
            if idx >= len(as_list):
                raise KeyError(f"Index {idx} out of range for tuple of length {len(node)}")
            as_list[idx] = value
        return tuple(as_list)


class ObjectHandler(TreeNodeHandler):
    """
    Handles arbitrary objects with __dict__. Catch-all; must be defined last.

    Attributes prefixed with '_' are excluded from children, treating them
    as private/internal and not part of the walkable tree.
    """

    @staticmethod
    def _predicate(node: Any) -> bool:
        return hasattr(node, '__dict__') and not isinstance(node, type)

    @staticmethod
    def _children(node: object) -> Dict[str, Any]:
        return {
            k: v for k, v in vars(node).items()
            if not k.startswith("_")
        }

    @staticmethod
    def _patch(node: object, updates: Dict[str, Any]) -> object:
        for key, value in updates.items():
            if not hasattr(node, key):
                raise KeyError(f"Attribute '{key}' not found on {type(node).__name__}")
            setattr(node, key, value)
        return node