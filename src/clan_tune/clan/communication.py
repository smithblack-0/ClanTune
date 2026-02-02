"""
Communication: Distributed gathering operations for Clan Training.

Wraps torch.distributed primitives for all-gathering objects across ranks.
All methods are all-gather style — every rank calls, every rank gets the
full result.
"""

from typing import Any, List

from torch import distributed as dist


class Communication:
    """
    Handles distributed gathering across ranks.

    Requires torch.distributed to be initialized before use. All gather
    operations are all-gather style — every participating rank calls the
    method and receives the full result.
    """

    def __init__(self):
        """
        Initialize Communication.

        Raises:
            EnvironmentError: If torch.distributed is not initialized
        """
        if not dist.is_initialized():
            raise EnvironmentError("Distributed world is not initialized")

    @property
    def world_size(self) -> int:
        """Number of ranks in the distributed group."""
        return dist.get_world_size()

    @property
    def rank(self) -> int:
        """This process's rank in the distributed group."""
        return dist.get_rank()

    def gather_objects_list(
        self,
        obj: Any,
    ) -> List[Any]:
        """
        All-gather an arbitrary object from every rank.

        Each rank provides one object. Every rank receives back a list
        containing all objects, ordered by rank.

        Args:
            obj: Any picklable object to gather

        Returns:
            List of objects from all ranks (length = world_size),
            ordered by rank index

        Raises:
            RuntimeError: If torch.distributed is not available or initialized
        """
        if not (dist.is_available() and dist.is_initialized()):
            raise RuntimeError("Cannot gather in non-distributed mode")
        output = [None] * self.world_size
        dist.all_gather_object(output, obj)
        return output