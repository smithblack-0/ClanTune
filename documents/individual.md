# Individual Spec

## Overview

Individual is the user-facing training object in Clan Training. It bundles a State (genome + model + optimizer) with round orchestration, a communication channel, and genome expression via GenomeExpression. The user trains through Individual — it is the only object they interact with during a round.

## Ownership

Individual owns two things: orchestration and scheduling. These are heavily coupled and cannot be cleanly separated.

- **Orchestration:** the round lifecycle — phase transitions, triggering re-expression, controlling when sync is active, signaling round completion.
- **Scheduling:** tracking where we are in the round and deciding when transitions happen, derived from round_length and duty_cycle.

Everything else is delegated:
- Genome expression → GenomeExpression
- Model, optimizer, and genome repository → State (which in turn delegates node-level operations to TreeNodeHandler)
- Gradient sync control → State (passthrough to DDP)
- Distributed communication → Communication

## Construction

Individual receives four things:

- `state`: A fully configured State instance (genome + model + optimizer). The Genome should be configured using GenomeExpression.set_allele() to ensure alleles have the correct expression metadata attached.
- `communicator`: Communication object for distributed gather operations
- `round_length`: Total number of steps in a round
- `duty_cycle`: Fraction of the round spent in the later competitive phase

## Internal State

- `_state`: State instance (genome + model + optimizer as unified walkable tree)
- `_communicator`: Communication object. All ranks call, all ranks get the full result. Used for genome averaging and fitness collection.
- `_cache`: Current expression snapshot — the last cache_dict produced by GenomeExpression.express(). Used by `.get_value()`.
- `_step_num`: Current step within the round
- `_round_length`: Total steps in a round
- `_duty_cycle`: Fraction of round spent in competitive phase
- `_done`: Flag, set when the round is complete

## Public Interface

- `.model` — direct access to the underlying model
- `.optimizer` — direct access to the underlying optimizer
- `.genome` — direct access to the underlying Genome
- `.sync_context()` — context manager controlling gradient synchronization. Active during cooperative phase, no-op during competitive phase.
- `.step()` — advance the round by one step. Triggers re-expression automatically at phase transitions. Sets `_done` when the round is complete. Throws if called after `_done` is True.
- `.done` — bool, signals round completion
- `.mode` — current phase, "cooperative" or "competitive"
- `.get_value(path)` — look up a currently expressed value from the cache by path
- `.express()` — re-express the genome for the current phase. Called automatically at phase transitions, but also available manually if you need to force a re-expression.
- `state_dict()` / `load_state_dict()` — passthrough to State serialization
- `get_world_fitness(fitness)` — sets fitness on this rank's genome, gathers all genomes across ranks, returns `{rank: Genome}` dict. All ranks get the same result.

## Orchestration

The round has two phases. The cooperative phase runs first — only alleles marked `is_cooperative` are individually expressed; others are averaged across the clan. At the transition point (determined by round_length and duty_cycle), the competitive phase begins — all alleles are individually expressed.

The user-facing phases are "cooperative" and "competitive". Internally, these map to expression modes "cooperative" and "all" respectively when calling GenomeExpression.

At each phase transition, Individual calls GenomeExpression.express() with the appropriate mode, applies the resulting patch dict to State, and updates the cache.

## Context Manager

Individual can be used as a context manager as a convenience. `__enter__` sets up sync for the current phase and returns State for model and optimizer access. `__exit__` calls `.step()`. The underlying public interface (`.sync_context()`, `.step()`, `.done`) remains available for direct use.

## Example Usage

Note: these examples reflect the current API but the contract may change.
Check the user guide for the latest.

### Explicit style

```python
individual = clan.round()

for batch, labels in loader:
    logits = individual.model(batch)
    loss = cross_entropy(logits, labels)

    with individual.sync_context():
        loss.backward()

    individual.optimizer.step()
    individual.optimizer.zero_grad()
    individual.step()

    if individual.done:
        validation_loss = get_validation_loss(individual.model, val_loader)
        clan.step(validation_loss)
        individual = clan.round()
```

### Context manager style

```python
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
```

## Communication

Individual orchestrates all distributed communication via the communicator.

Used in two places:
- **Genome averaging:** GenomeExpression's handlers gather values via the communicator when averaging alleles during cooperative and all expression modes respectively.
- **Fitness collection:** `get_world_fitness` gathers all genomes (with fitness set) across ranks.

## Key Contracts

- `_cache` is always consistent with what was last patched into State. Users should not patch State directly.
- Re-expression happens automatically only at phase transitions, not every step. It can also be triggered manually via `.express()`.
- A gene that is not expressed means the clan average is used instead.
- `.step()` throws if called after `_done` is True.
- When the round is complete, `_done` is set to True. The Individual is spent — the user must obtain a new one via `clan.round()` to continue training.