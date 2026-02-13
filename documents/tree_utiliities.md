# TreeNodeHandler Spec

## Overview

TreeNodeHandler is a registry-based dispatch system for reading and writing into heterogeneous object trees. It normalizes access across different container types so that callers never need to know what kind of node they are dealing with. Everything goes through a uniform string-keyed dict interface.

This is not a general-purpose extensible utility. The registry has a catch-all handler (ObjectHandler) that matches anything with a `__dict__`. No handlers defined after it will ever match. Do not define new handlers after ObjectHandler.

## Public Interface

All methods are classmethods on TreeNodeHandler. Do not instantiate it.

`TreeNodeHandler.has_children(node) -> bool`
Returns True if any registered handler can handle this node. Used to distinguish containers from leaves during tree walking.

`TreeNodeHandler.children(node) -> Dict[str, Any]`
Returns the node's immediate children as a string-keyed dict. The keys are the path segments that would appear in a slash-separated path string.

- For dicts: keys are the dict's own keys
- For lists and tuples: keys are stringified integer indices ("0", "1", ...)
- For objects: keys are public attribute names (anything not starting with `_`)

Raises TypeError if no handler matches.

`TreeNodeHandler.patch(node, updates: Dict[str, Any]) -> Any`
Applies updates (same format as children() returns) back into the node. Returns the node. For mutable containers, this is the same object mutated in place. For tuples, this is a new tuple — caller must reassign.

Raises TypeError if no handler matches. Raises KeyError if an update key does not exist in the node.

## Concrete Handlers

Defined in order. First match wins. ObjectHandler is last and is a catch-all.

**DictHandler** — matches `isinstance(node, dict)`. Keys are strings directly.

**ListHandler** — matches `isinstance(node, list)`. Keys are stringified indices. Patch validates index is in range.

**TupleHandler** — matches `isinstance(node, tuple)`. Same as ListHandler for children. Patch reconstructs a new tuple — this is the only handler where patch returns a different object than it received.

**ObjectHandler** — matches anything with `__dict__` that is not a type. Catch-all, must be last. Children excludes attributes starting with `_`. Patch uses setattr.

## Usage

Here is an example of a utility that replaces all lists with tuples anywhere in a tree:

```python
def freeze_lists(node):
    """Recursively replace all lists with tuples in a tree."""
    if not TreeNodeHandler.has_children(node):
        return node

    children = TreeNodeHandler.children(node)
    updates = {}
    for key, child in children.items():
        frozen = freeze_lists(child)
        if isinstance(child, list):
            frozen = tuple(frozen)
        if frozen is not child:
            updates[key] = frozen

    if updates:
        node = TreeNodeHandler.patch(node, updates)
    return node
```

This works on dicts, lists, tuples, and objects without ever checking which one it is dealing with — it just asks TreeNodeHandler. If a list is nested inside an object inside a dict, it will find it and freeze it. Note that we patch the update back in regardless of whether the node was mutated in place or not — this is the correct pattern, since patch may return a new object (e.g. if node itself is a tuple).

## Mutability and Patch Return Values

This is the most important contract in the system. `patch()` always returns the node, but what that means depends on mutability:

**Mutable containers (dict, list, object):** patch mutates the node in place and returns the same object. Reassigning the return value is a no-op but harmless.

**Immutable containers (tuple):** patch cannot mutate in place. It constructs a new tuple with the updates applied and returns that. The caller *must* reassign the return value, or the update is lost. This is the only case where the returned object is different from the one passed in.

This distinction propagates up recursive patch operations. If you patch a value inside a tuple that is inside a dict, the tuple handler returns a new tuple, and the dict handler must reassign it into the dict at the tuple's key. State's `_apply_patch` handles this by always reassigning the return value at every level of recursion — this is why it works transparently regardless of what types are in the path.

## Key Contracts

- `children()` and `patch()` use the same key format. What children() yields, patch() can consume.
- Patch always returns the node. Caller should always reassign the return value — this is a no-op for mutable types but necessary for tuples.
- ObjectHandler filters out private attributes (prefixed with `_`). These are invisible to both walk and patch.
- has_children() returning False means the node is a leaf. Callers (e.g. State) use this to decide whether to recurse or yield.