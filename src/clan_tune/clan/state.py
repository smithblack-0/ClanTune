"""
State: Central object tree management for ClanTune training.

Holds genome, model, and optimizer as a unified object tree.
Provides walking, filtering, patching, and serialization over
the combined state using TreeNodeHandler for type dispatch.
"""

from contextlib import contextmanager
from typing import Any, Callable, Dict, Generator, List, Set, Tuple

import torch
from torch.nn.parallel import DistributedDataParallel

from ..genetics.genome import Genome
from .tree_utilities import TreeNodeHandler


class State:
    """
    Manages the combined training state as a walkable, patchable object tree.

    Holds genome, model, and optimizer. Provides:
    - Object tree walking with cycle detection
    - Path-based filtering to find hyperparameters
    - Path-based patching to apply values into the tree
    - Serialization via PyTorch state_dict convention
    - Gradient sync control via no_sync()
    """

    def __init__(
        self,
        genome: Genome,
        model: DistributedDataParallel,
        optimizer: torch.optim.Optimizer,
    ):
        """
        Initialize state with training objects.

        Args:
            genome: Genome instance holding hyperparameter alleles
            model: DDP-wrapped PyTorch model
            optimizer: PyTorch optimizer
        """
        self.genome = genome
        self.model = model
        self.optimizer = optimizer

    def walk(
        self,
        max_depth: int = -1,
    ) -> Generator[Tuple[str, Any], None, None]:
        """
        Walk the full object tree from self, yielding (path, value) pairs.

        Uses cycle detection to avoid infinite recursion on shared references.

        Args:
            max_depth: Maximum depth to walk. -1 for unlimited.

        Yields:
            (path, value) tuples for each leaf found
        """
        seen: Set[int] = set()
        yield from self._walk_node(self, None, max_depth, seen)

    def _walk_node(
        self,
        node: Any,
        path: str,
        remaining_depth: int,
        seen: Set[int],
    ) -> Generator[Tuple[str, Any], None, None]:
        """
        Recursively walk a single node in the object tree.

        Args:
            node: Current node to walk
            path: Path to this node (None for root)
            remaining_depth: Remaining depth to walk (-1 for unlimited)
            seen: Set of object ids already visited (cycle detection)

        Yields:
            (path, value) tuples for each leaf found
        """
        # Depth check (negative values never hit zero)
        if remaining_depth == 0:
            return
        next_depth = remaining_depth - 1 if remaining_depth > 0 else -1

        # Cycle detection for mutable containers and objects
        node_id = id(node)
        if node_id in seen:
            return
        seen.add(node_id)

        # Ask TreeNodeHandler if this is a container we know how to walk
        if TreeNodeHandler.has_children(node):
            for key, child in TreeNodeHandler.children(node).items():
                child_path = key if path is None else path + "/" + key
                yield from self._walk_node(child, child_path, next_depth, seen)
        else:
            # Leaf node
            if path is not None:
                yield path, node

    def get_paths_to_hyperparameters(
        self,
        predicate: Callable[[str, Any], bool],
    ) -> List[str]:
        """
        Walk the object tree and return paths matching a predicate.

        Args:
            predicate: Function(path, value) -> bool to filter by

        Returns:
            List of path strings matching the predicate
        """
        return [
            path for path, value in self.walk()
            if predicate(path, value)
        ]

    def apply_patches(
        self,
        patches: Dict[str, Any],
    ) -> None:
        """
        Apply a dict of {path: value} patches into the object tree.

        Handles dicts, lists, tuples, and object attributes. Tuples are
        reconstructed and reassigned at parent. Throws if path doesn't exist.

        Args:
            patches: Dict mapping paths to values to set

        Raises:
            KeyError: If a path does not exist in the object tree
            TypeError: If a node along the path is not a supported container
        """
        for path, value in patches.items():
            try:
                self._apply_patch(self, path, value)
            except (KeyError, TypeError) as e:
                raise type(e)(f"Failed to apply patch '{path}' = {value!r}: {e}") from e

    def _apply_patch(
        self,
        node: Any,
        path: str,
        value: Any,
    ) -> Any:
        """
        Recursively navigate and patch a single value into the object tree.

        Navigates one path segment at a time using TreeNodeHandler.children()
        to resolve keys, then applies the final value via TreeNodeHandler.patch().
        Always returns the (possibly new) node to support tuple reconstruction
        up the call stack.

        Args:
            node: Current node in the tree
            path: Remaining path to target
            value: Value to set

        Returns:
            The node (same object for mutable, new object for tuples)

        Raises:
            KeyError: If path segment doesn't exist
            TypeError: If a node along the path is not a supported container
        """
        parts = path.split("/", 1)
        key = parts[0]
        has_suffix = len(parts) > 1

        # Validate key exists by checking against children
        children = TreeNodeHandler.children(node)
        if key not in children:
            raise KeyError(f"Path segment '{key}' not found in {type(node).__name__}")

        if has_suffix:
            # Recurse deeper, then patch the result back into this node
            result = self._apply_patch(children[key], parts[1], value)
            return TreeNodeHandler.patch(node, {key: result})
        else:
            # Leaf — patch value directly
            return TreeNodeHandler.patch(node, {key: value})

    def state_dict(self) -> Dict[str, Any]:
        """
        Serialize complete state to dict.

        Returns:
            Dict containing genome serialization, model state dict,
            and optimizer state dict
        """
        return {
            "genome": self.genome.serialize(),
            "model": self.model.state_dict(),
            "optimizer": self.optimizer.state_dict(),
        }

    def load_state_dict(
        self,
        data: Dict[str, Any],
    ) -> None:
        """
        Load state from a state dict in place.

        Args:
            data: Dict from state_dict() containing genome, model,
                  and optimizer state
        """
        self.genome = Genome.deserialize(data["genome"])
        self.model.load_state_dict(data["model"])
        self.optimizer.load_state_dict(data["optimizer"])

    @contextmanager
    def no_sync(self) -> Generator[None, None, None]:
        """
        Context manager that disables gradient synchronization on the model.

        Passthrough to the underlying DDP model's no_sync(). Use this when
        you want to run forward/backward without synchronizing gradients
        across ranks.
        """
        with self.model.no_sync():
            yield