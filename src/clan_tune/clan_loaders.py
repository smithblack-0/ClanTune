"""
Clan Training DataLoader Module

Provides a specialized DataLoader for Clan Training that implements phase-aware
batch filtering. During cooperative phases, data is sharded across distributed
ranks. During competitive phases, all ranks process identical batches.
"""

from typing import Any, Iterator, Optional

from torch.utils.data import DataLoader, Dataset, IterableDataset

from src.clan_tune import utilities

class ClanDataLoader(DataLoader):
    """
    DataLoader for Clan Training that filters batches based on cooperative/competitive phases.

    During cooperative phases, data is sharded across ranks (each rank processes every
    world_size-th batch). During competitive phases, all ranks process all batches.
    Works with iteratable and set datasets, but shuffling should be done separately.

    Args:
        dataset: PyTorch Dataset or IterableDataset
        round_length: Total number of batches per training round
        duty_cycle: Fraction of round spent in competitive phase (e.g., 0.1 = 10% competitive)
        rank: Current process rank in distributed group
        world_size: Total number of processes in distributed group
        **kwargs: All standard PyTorch DataLoader arguments (batch_size, num_workers,
                  pin_memory, etc.)

    Example:
        >>> loader = ClanDataLoader(
        ...     dataset=my_dataset,
        ...     round_length=1000,
        ...     duty_cycle=0.1,
        ...     rank=0,
        ...     world_size=8,
        ...     batch_size=32,
        ...     num_workers=4
        ... )
    """

    def __init__(
        self,
        dataset: Dataset | IterableDataset,
        rank: int,
        world_size: int,
        round_length: int = 1000,
        duty_cycle: float = 0.1,
        **kwargs: Any
    ) -> None:
        super().__init__(dataset, **kwargs)
        self.round_length = round_length
        self.duty_cycle = duty_cycle
        self.rank = rank
        self.world_size = world_size

    def __iter__(self) -> Iterator[Any]:
        """
        Iterate over batches with phase-aware filtering.

        Yields:
            Batches from the underlying dataset, filtered according to current phase
            and rank assignment.
        """
        batch_idx = 0  # Tracks batches actually yielded to training loop
        batch_iterator = super().__iter__()

        while True:
            if utilities.is_cooperative_phase(batch_idx, self.round_length, self.duty_cycle):
                # In a cooperative case, we draw world_size batches all together,
                # ensuring we throw together across processes, but only yield
                # at the end.
                rank_batch = None
                for i in range(self.world_size):
                    batch = next(batch_iterator)
                    if i == self.rank:
                        rank_batch = batch
                yield rank_batch
                batch_idx += 1
            else:
                # In the competitive space, we basically just yield
                # everything like normal so competitors have the same
                # challenge
                batch = next(batch_iterator)
                yield batch
                batch_idx += 1

