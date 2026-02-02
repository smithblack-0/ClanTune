"""
ClanStrategy: DDP coordination for Clan Training.

This module provides PyTorch Lightning strategy components for Clan Training,
a PBT-style approach where N Ray Tune trials form a single DDP group for
cooperative gradient sharing.
"""

import os
from typing import Any, Optional

from lightning.fabric.plugins import ClusterEnvironment
from lightning.pytorch.strategies import DDPStrategy
from lightning.pytorch.utilities.rank_zero import rank_zero_warn


class ClanClusterEnvironmentWrapper(ClusterEnvironment):
    """
    Wrapper for ClusterEnvironment that overrides rank/world_size/address/port
    while delegating all other methods to the wrapped environment.

    This is used internally by ClanStrategy to handle the edge case where a user
    provides their own ClusterEnvironment but needs Clan Training coordination.

    Args:
        wrapped: The user-provided ClusterEnvironment to wrap
        rank: Override for global_rank()
        world_size: Override for world_size()
        master_addr: Override for main_address()
        master_port: Override for main_port()
    """

    def __init__(
            self,
            wrapped: ClusterEnvironment,
            rank: int,
            world_size: int,
            master_addr: str,
            master_port: int,
    ):
        self._wrapped = wrapped
        self._rank = rank
        self._world_size = world_size
        self._master_addr = master_addr
        self._master_port = master_port

    def world_size(self) -> int:
        """Return the Clan world size."""
        return self._world_size

    def global_rank(self) -> int:
        """Return the Clan global rank."""
        return self._rank

    def main_address(self) -> str:
        """Return the Clan master address."""
        return self._master_addr

    def main_port(self) -> int:
        """Return the Clan master port."""
        return self._master_port

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the wrapped ClusterEnvironment."""
        return getattr(self._wrapped, name)


class ClanStrategy(DDPStrategy):
    """
    Strategy for Clan Training: PBT-style population training where N Ray Tune
    trials form a single DDP group for cooperative gradient sharing.

    The ClanStrategy sets up and ensures the successful running of a
    torch DistributedDataParallel environment using the native DDP
    system of Lightning. It does this by overriding per process


    Requirements:
        - Processes launched externally (e.g., by Ray Tune)
        - Each process controls exactly 1 GPU (configured by Ray)
        - All processes use same master_addr and master_port
        - Each process has unique rank (0 to world_size-1)

    Args:
        rank: Global rank of this process (0 to world_size-1)
        world_size: Total number of processes in the clan
        master_addr: Address for DDP coordination (default: "localhost")
        master_port: Port for DDP coordination (default: 29500)
        **kwargs: Additional arguments passed to DDPStrategy

    Notes:
        - ClanStrategy sets environment variables (MASTER_ADDR, MASTER_PORT,
          RANK, WORLD_SIZE) that are used by PyTorch's DDP initialization.
        - If a custom cluster_environment is provided, it will be wrapped to
          override the coordination parameters while preserving other methods.
        - Use with ClanDataLoader for phase-aware batch filtering.
        - Use with ClanTrainingCallback for gradient sync toggling.
    """

    def __init__(
            self,
            rank: int,
            world_size: int,
            master_addr: str = "localhost",
            master_port: int = 29500,
            **kwargs: Any,
    ):
        # Always set environment variables for DDP coordination
        os.environ['MASTER_ADDR'] = master_addr
        os.environ['MASTER_PORT'] = str(master_port)
        os.environ['RANK'] = str(rank)
        os.environ['WORLD_SIZE'] = str(world_size)

        super().__init__(**kwargs)

