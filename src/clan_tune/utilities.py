"""Centralized utilities, such as checks for if batch phase """
# clan_training/phase.py


def is_cooperative_phase(batch_idx: int,
                         round_length: int,
                         duty_cycle: float,
                         ) -> bool:
    """
    Determine if a given batch index (as measured by batches yielded from the dataloader)
    corrosponds to operation in a cooperative or competitive phase

    Args:
        batch_idx: Global batch index in training
        round_length: Total batches per round
        duty_cycle: Fraction of round spent in competitive phase (e.g., 0.1 = 10%)

    Returns:
        True if cooperative phase, False if competitive
    """
    cooperative_batches = int(round_length * (1 - duty_cycle))
    position_in_round = batch_idx % round_length
    return position_in_round < cooperative_batches