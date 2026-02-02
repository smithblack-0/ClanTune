# State Spec

## Overview

State is the central object tree for ClanTune training. It holds a Genome, a DDP-wrapped model, and an optimizer as a unified walkable and patchable tree. It is the object that Individual holds internally and patches into when the genome is expressed.

From State's perspective, there is one datatype: tree. It does not know or care how the tree is implemented internally — whether a given node is a dict, a list, an object, or anything else. That is entirely TreeNodeHandler's responsibility. State owns the traversal logic (cycle detection, depth control, path assembly) and the path-based navigation for patching, but delegates all node-level read and write operations to TreeNodeHandler.

## Construction

```python
State(
    genome: Genome,                                    # Genome instance
    model: torch.nn.parallel.DistributedDataParallel, # DDP-wrapped model
    optimizer: torch.optim.Optimizer,                  # PyTorch optimizer
)
```

## Public Interface

### Walking

`walk(max_depth=-1) -> Generator[(path, value)]`

Yields (path, value) pairs for every leaf in the object tree, starting from self. Paths are slash-separated strings (e.g. `"optimizer/param_groups/0/lr"`). Uses cycle detection to avoid infinite recursion on shared references. `max_depth=-1` means unlimited.

### Filtering

`get_paths_to_hyperparameters(predicate) -> List[str]`

Walks the full tree and returns paths where `predicate(path, value)` is True. This is how the builder discovers valid patch targets.

### Patching

`apply_patches(patches: Dict[str, Any]) -> None`

Takes a `{path: value}` dict and writes each value into the tree at its path. Handles tuple reconstruction transparently — if a node in the path is immutable, patching returns a new node which gets reassigned at the parent. State does not need to know this is happening; TreeNodeHandler handles it. Throws with context if any path doesn't exist — the error message includes the full path and value that failed.

### Serialization

`state_dict() -> Dict[str, Any]`

Returns `{"genome": ..., "model": ..., "optimizer": ...}` using each object's own serialization convention. Genome uses `.serialize()`, model and optimizer use PyTorch's `.state_dict()`.

`load_state_dict(data: Dict[str, Any]) -> None`

Restores state in place from a dict produced by `state_dict()`.

### Gradient Sync

`no_sync() -> context manager`

Passthrough to the DDP model's `no_sync()`. Disables gradient synchronization for the duration of the block. Individual calls this during competitive phase; during cooperative phase it is not called and DDP sync is active by default.

## Key Contracts

- State does not know how tree nodes are implemented internally. All node-level read and write operations are TreeNodeHandler's job. If walk or patch behaves unexpectedly, look there first.
- Cycle detection is by object id. Shared references will only be walked once.
- Patching always reassigns the return value up the call stack. This is transparent to State — TreeNodeHandler handles it for whatever node types require it.
- `apply_patches` contextualizes errors — the raised exception includes the full path and value that failed, not just the failing segment.