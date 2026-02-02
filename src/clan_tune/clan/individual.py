"""
Individual: User-facing training object for Clan Training.

Bundles a State (genome + model + optimizer) with round orchestration,
distributed communication, and genome expression. The user trains through
Individual — it is the only object they interact with during a round.

The round proceeds in two phases. The cooperative phase runs first — the genome
is expressed in "cooperative" mode and gradient synchronization is active. At
the transition point (determined by round_length and duty_cycle), the genome
is re-expressed in "all" mode and gradient sync turns off for the remainder
of the round (the competitive phase). The user sees these as cooperative and
competitive phases; the underlying expression modes are cooperative and all.
"""

from contextlib import contextmanager
from typing import Any, Dict, Generator

import torch

from .state import State
from ..genetics.genome import Genome
from .communication import Communication
from src.clan_tune.genetics.expression import GenomeExpression


class Individual:
    """
    Orchestrates a single training round for one member of the clan.

    Individual manages the round lifecycle: it tracks where you are in the
    round, triggers genome re-expression at phase transitions, controls
    gradient synchronization, and collects fitness across ranks. It is the
    only object the user interacts with during training.

    The round proceeds in two phases. The cooperative phase runs first —
    gradient sync is active and only cooperative alleles are individually
    expressed. At the transition point, the competitive phase begins — gradient
    sync turns off and all alleles are individually expressed. The transition
    point is determined by round_length and duty_cycle.

    Can be used as a context manager (see examples below) or via the explicit
    interface (.sync(), .step(), .done).

    Note: examples below reflect the current API but the contract may change.
    Check the user guide for the latest.

    Examples::

        # Context manager style — sync and step are handled automatically
        individual = clan.round()
        for batch, labels in loader:
            with individual as state:
                loss = state.model(batch)
                loss.backward()
                state.optimizer.step()
                state.optimizer.zero_grad()

            if individual.done:
                validation_loss = get_validation_loss(individual.model, val_loader)
                clan.step(validation_loss)
                individual = clan.round()

        # Explicit style — useful if you need finer control over sync scope
        with individual.sync():
            loss.backward()
        individual.optimizer.step()
        individual.step()
    """

    def __init__(
        self,
        state: State,
        communicator: Communication,
        round_length: int,
        duty_cycle: float,
    ):
        """
        Args:
            state: Fully configured State instance (genome + model + optimizer)
            communicator: Communication object exposing .gather_objects_list()
            round_length: Total number of steps in a round
            duty_cycle: Fraction of the round spent in competitive phase (all mode)
        """
        self._state = state
        self._communicator = communicator
        self._round_length = round_length
        self._duty_cycle = duty_cycle
        self._step_num = 0
        self._done = False
        self._cache: Dict[str, Any] = {}

        # Express genome at start of round
        self.express()

    # -------------------------------------------------------------------------
    # Facade
    # -------------------------------------------------------------------------

    @property
    def model(self) -> torch.nn.Module:
        """The underlying model, for direct use in the training loop."""
        return self._state.model

    @property
    def optimizer(self) -> torch.optim.Optimizer:
        """The underlying optimizer, for direct use in the training loop."""
        return self._state.optimizer

    @property
    def done(self) -> bool:
        """True when the round is complete. Check this after each step."""
        return self._done

    @property
    def mode(self) -> str:
        """Current phase — "cooperative" or "competitive"."""
        competitive_start = int(self._round_length * (1.0 - self._duty_cycle))
        return "competitive" if self._step_num >= competitive_start else "cooperative"

    def get_value(self, path: str) -> Any:
        """
        Look up a currently expressed value by its State path.

        Useful for reading back values that were set by expression, e.g.
        gradient accumulation steps that you need to act on in your training loop.

        Args:
            path: Path in the State object tree

        Returns:
            The currently expressed value at that path

        Raises:
            KeyError: If path is not in the current expression cache
        """
        return self._cache[path]

    @contextmanager
    def sync_context(self) -> Generator[None, None, None]:
        """
        Context manager controlling gradient synchronization.

        During cooperative phase, this activates DDP gradient sync for the
        duration of the block. During competitive phase, this syncronization
        is then disabled. This effect can be overridden and so is compatible
        with techniques like gradient accumulation.

        Wrap at least the backward pass inside this context:
            with individual.sync():
                loss.backward()
        """
        if self.mode == "competitive":
            with self._state.no_sync():
                yield
        else:
            yield

    def step(self) -> None:
        """
        Advance the round by one step.

        If the phase has changed, re-expresses the genome. Sets done when
        the round is complete.

        Raises:
            RuntimeError: If called after the round is done
        """
        if self._done:
            raise RuntimeError("Cannot step: round is complete")

        prev_mode = self.mode
        self._step_num += 1

        if self.mode != prev_mode:
            self.express()

        if self._step_num >= self._round_length:
            self._done = True

    def express(self) -> None:
        """
        Re-express the genome for the current phase.

        Translates the user-facing phase to the expression mode GenomeExpression
        expects: cooperative stays cooperative, competitive becomes all.

        Produces patch and cache dicts via GenomeExpression, applies patches
        to State, and updates the cache. Called automatically at phase
        transitions, but can also be called manually if you need to force
        a re-expression after adjusting hyperparameters.
        """
        expression_mode = "cooperative" if self.mode == "cooperative" else "all"
        patch_dict, self._cache = GenomeExpression.express(
            self._state.genome,
            self._communicator,
            expression_mode,
        )
        self._state.apply_patches(patch_dict)

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def state_dict(self) -> Dict[str, Any]:
        """Passthrough to State serialization."""
        return self._state.state_dict()

    def load_state_dict(self, data: Dict[str, Any]) -> None:
        """Passthrough to State deserialization."""
        self._state.load_state_dict(data)

    # -------------------------------------------------------------------------
    # Distributed
    # -------------------------------------------------------------------------

    def get_world_fitness(
        self,
        fitness: float,
    ) -> Dict[int, Genome]:
        """
        Gather fitness from all ranks and return annotated Genomes.

        Every rank calls this with its own name and fitness value. Every rank
        gets back the full picture — a dict mapping each name to its Genome
        with fitness set.

        Args:
            fitness: This rank's fitness value

        Returns:
            Dict mapping {name: Genome} with fitness set on each
        """
        genome = self.genome
        genome.set_fitness(fitness)
        genomes = self._communicator.gather_objects_list()
        return {i : genome for i, genome in enumerate(genomes)}

    # -------------------------------------------------------------------------
    # Context manager
    # -------------------------------------------------------------------------

    def __enter__(self) -> State:
        """Set up sync for current phase, return State for model/optimizer access."""
        self._sync_ctx = self.sync_context()
        self._sync_ctx.__enter__()
        return self._state

    def __exit__(self, *args) -> None:
        """Close sync context and advance the round."""
        self._sync_ctx.__exit__(*args)
        self.step()