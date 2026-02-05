# Allele Spec

## Overview

An allele is an immutable data container representing a single evolvable parameter. Alleles form trees via their metadata — metadata can contain other alleles, which themselves have metadata. This recursive structure enables metalearning: mutation parameters evolve under selection pressure alongside the values they control.

This system is entirely immutable. 

Note concrete implementations should include type hints. 

## Core Structure

Every allele has five fields:

**`value: Any`** — the actual parameter value. Type depends on subclass. Shows the final product, but perhaps not internal state used to get to it. 
**`domain: Dict`** — constraints on valid values (min/max bounds or discrete choices). Exact details will follow.
**`can_mutate: bool`** — signals whether this allele's value should participate in mutation. This is signaling only — the allele does not enforce it. Utilities and strategies should be setup to respect it
**`can_crossbreed: bool`** — signals whether this allele's value should participate in crossbreeding. Signaling only, not enforced by the allele.

**`metadata: Dict[str, Any]`** — recursive tree. Values can be alleles (which recurse) or raw values (which don't).

## Core Methods

**`with_value(new_value) -> Allele`** — returns a new allele with updated value. Applies domain validation and clamping through constructor
**`with_metadata(**updates) -> Allele`** — returns a new allele with metadata entries added or updated. Used for incremental construction.
**`flatten() -> Allele`** — returns a new allele where all alleles in metadata are replaced with their `.value`. Raw metadata values unchanged. Used by tree synthesis to create templates and flattened source nodes.
**`unflatten(resolved_metadata: Dict[str, Allele]) -> Allele`** — returns a new allele with metadata alleles restored from resolved_metadata dict. Replaces flattened values with actual allele objects. Used by tree synthesis to re-inject resolved children after handler returns.
**`walk_tree(handler) -> Generatort[Any, None, None]`** — walks this allele's tree and yields results. Thin wrapper around `walk_allele_trees` for single-tree use.
**`update_tree(handler) -> Allele`** — transforms this allele's tree. Thin wrapper around `synthesize_allele_trees` for single-tree use. Returns a new tree with the updates
**`serialize() -> Dict`** — converts to dict, including recursive serialization of metadata alleles.
**`deserialize(data) -> Allele`** (classmethod) — reconstructs from dict, including recursive deserialization.
** Others: Concrete types can add their own methods.

## Concrete Types

**FloatAllele** — floating point values with linear semantics.
**IntAllele** — integer values. `with_value` rounds and clamps.
**LogFloatAllele** — floating point with log-space semantics. Min >0 required
**BoolAllele** — boolean flags. Domain must be `{True, False}`.
**StringAllele** — strings from a discrete set.

## Tree Structure

Metadata forms trees. An allele's metadata can contain other alleles, which have their own metadata. This recursion continues until raw values (the base case) are reached.

Trees enable metalearning. Mutation parameters (like std or scale) are not algorithm hyperparameters — they are genetic material. They evolve under selection pressure alongside the values they control.

Example tree:
```
FloatAllele (learning rate)
  └─ metadata["std"] → FloatAllele (mutation std)
       └─ metadata["mutation_std"] → 0.05 (raw value: how std itself mutates)
```

Children are processed before parents. Metadata values feed into parent operations.

**Terminology note:** "Source nodes" refers to the input alleles being operated on by tree utilities (e.g., parent individuals in crossbreeding, or the original tree in mutation). This distinguishes from "parent node" which refers to tree structure relationships (a node and its metadata children). "Template tree" refers to the source tree whose structure (domain, flags, raw metadata values) is used as the base for synthesis - alleles in metadata are resolved recursively, raw values are taken from the template.

---

## Tree Utilities

The allele module provides functional tree walking and synthesis utilities. These handle recursion and metadata flattening — user code never sees nested alleles, only flat data.

### walk_allele_trees

The utility handles tree recursion and node traversal. The user specifies what information to extract from each node. Returns a generator stream of extracted results.

```python
def walk_allele_trees(
    alleles: List[Allele],
    handler: Callable[[List[Allele]], Optional[Any]],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> Generator[Any, None, None]:
```

Walks multiple allele trees in parallel (depth-first, children-first). List order is preserved across recursion. At each node:
1. Recursively processes all metadata alleles first
2. Checks filtering: if node excluded by `include_can_mutate` or `include_can_crossbreed`, skips to next node
3. Flattens metadata: Invokes flatten on all nodes so only raw types are present in metadata when viewed
4. Passes a list of flattened alleles (one per input tree) to `handler`
5. If `handler` returns a value (not None), yields it directly. Otherwise continues to next node.

**Error Conditions**:
- Type matching: Corresponding values must be the same type, whether alleles or raw values. Raises TypeError.
- Schema matching NOT required: Raw values (domain, flags, metadata) may differ. Useful for comparing trees with different schemas. 

### synthesize_allele_trees

The utility handles recursive tree synthesis (N source nodes → 1 result tree) and metadata resolution. The user specifies how to construct each node from a template and source nodes. Returns a new synthesized tree.

```python
def synthesize_allele_trees(
    template_tree: Allele,
    alleles: List[Allele],
    handler: Callable[[Allele, List[Allele]], Allele],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> Allele:
```

Walks multiple trees and synthesizes a single result tree. The template_tree identifies which source tree's structure to use for the result (must be in alleles list). List order is preserved across recursion. At each node:
1. Recursively synthesizes metadata children first (N→1 for each metadata key, producing resolved child alleles)
2. Handles validation logic and base cases
3. Creates template (source node at template_tree's position with resolved metadata)
4. Checks filtering: if node excluded by `include_can_mutate` or `include_can_crossbreed`, returns template (skips handler)
5. Flattens both template and source nodes via `flatten()`
6. Passes (template, flattened_source_nodes) to handler
7. Handler returns new allele (typically constructed from template using `with_value()`)
8. Re-injects resolved children into result via `unflatten()` and returns synthesized tree
**Error Conditions:** Checked in step 2:
- Type matching: All corresponding values (domain, flags, metadata) must be same type. Raises TypeError.
- Schema matching: All raw values (domain, can_mutate, can_crossbreed, raw metadata values) must match exactly across source nodes. Only alleles in metadata may differ (they get synthesized). Raises ValueError if raw values don't match.

**Handler contract:** Receives template allele (with flattened resolved metadata) and list of flattened source nodes. Returns new allele, typically constructed from template via `template.with_value(new_value)`. Template provides resolved metadata and domain. Source nodes provide values to combine/transform.

**Implementation recommendation:** Use recursive dispatch on metadata types (alleles vs raw values). Base case: all raw values must match exactly - validate and return the shared value. Recursive case: alleles - synthesize children first, then build parent. This progressively constructs the result tree from children up. To find the template position at each recursion level, use `alleles.index(template_tree)` to identify which source is the template. 

### Instance Methods: walk_tree / update_tree

Allele provides convenience wrappers for single-tree operations:

```python
def walk_tree(self, handler: Callable[[Allele], Optional[Any]], include_can_mutate=True, include_can_crossbreed=True) -> Generator[Any, None, None]:
    ...
def update_tree(self, handler: Callable[[Allele], Allele], include_can_mutate=True, include_can_crossbreed=True) -> Allele:
    ...
```

These wrappers:
- Hide the list-based API (internally call core utilities with `[self]`)
- Adapt handler signatures for single-tree convenience (handler receives single allele, not list)
- For `update_tree`, automatically use `self` as template_tree
- Preserve filtering capability via `include_can_mutate` and `include_can_crossbreed` parameters

### Flattening and Unflattening

Tree utilities use flattening and unflattening to simplify handler logic while preserving tree structure.

**Flattening** (via `flatten()` method) replaces alleles in metadata with their `.value`, leaving raw values unchanged:
```python
flattened_metadata = {
    key: node.value if isinstance(node, AbstractAllele) else node
    for key, node in allele.metadata.items()
}
```

Handlers receive flattened alleles where metadata contains only raw values. Decision logic is simple — no need to understand recursion or tree structure.

**Unflattening** (via `unflatten(resolved_metadata)` method) restores allele structure after handler returns. Takes a dict mapping metadata keys to resolved alleles and replaces the flattened values. This re-injects the recursively synthesized children into the result tree, preserving the full allele structure.

## Tree Construction

Trees are intended to be constructed functionally,
and can be constructed a bit at a time using 
with_metadata(**updates). They may also be constructed
by directly passing the relevant metadata into the constructor

## Domain

Domain defines valid values for an allele. Domain contains raw values only (not alleles). Structure depends on allele type (Dict for continuous, Set for discrete). Domain enforcement happens at construction and when `with_value()` is called: values are clipped to domain bounds when a clear metric exists (continuous domains), and an exception is raised when no clipping metric exists (discrete domains with no clear choice).

**Continuous (min/max):**
```python
{"min": 0.0, "max": 1.0}    # Bounded
{"min": 0.0, "max": None}   # Unbounded above
```

Used by `FloatAllele`, `IntAllele`, `LogFloatAllele`. Note `LogFloatAllele` requires `"min"` and requires it is greater than zero.

**Discrete (set):**
```python
{"adam", "sgd"}  # String domains
{True, False}    # Bool domain
```

Used by `StringAllele`, `BoolAllele`.

---

## Ownership

The allele owns:
- Value storage and type semantics
- Domain enforcement via constructor
- Immutable copy operations
- Serialization/deserialization

The utilities own:

- Allele walking
- Allele updating
- Allele filtering

Not owned include:

- Mutation logic — strategies handle this via `update_tree` or `synthesize_allele_trees`
- Crossbreeding logic — strategies handle this via `walk_allele_trees` and `synthesize_allele_trees`

---

## Subclassing for Strategy-Specific Alleles

Users extend concrete types (FloatAllele, IntAllele, etc.) to create strategy-specific allele types. These custom types are used in metadata when constructing alleles for that strategy.

**Why subclass:** Strategies need custom parameters. A Gaussian mutation strategy needs `std` and `mutation_chance`. Rather than using generic FloatAlleles, you define `GaussianStd` and `GaussianMutationChance` with appropriate defaults and constraints.

**Example:** Gaussian mutation strategy defines custom types:

```python
class GaussianStd(FloatAllele):
    def __init__(self, 
                 base_std: float,
                 can_change=True, **kwargs):
        super().__init__(base_std, 
                         can_crossbreed=can_change,
                         can_mutate=can_change,
                         domain={"min" :0.1*base_std, "max" : 5.0*base_std},
                         **kwargs)
        

class GaussianMutationChance(FloatAllele):
    def __init__(self, value, **kwargs):
        super().__init__(value,
                         can_mutate = False,
                         can_crossbreed=False,
                         domain={"min" : 0.1, "max" : 0.9}, 
                        **kwargs)
```

Then constructs alleles using these subclasses:

```python
learning_rate_allele = LogFloatAllele(
    value=0.01,
    domain={"min" : 1e-6, "max" : 1e-2},
).with_metadata(
    mutation_chance=GaussianMutationChance(0.15),
    std=GaussianStd(0.1, can_change=True).with_metadata(
        mutation_chance=0.05,  # Raw value: constant
        std=0.1 # Raw value; knows how to mutate it, but no deeper metamutation.
    )
)
```

Or alternatively

```python


lr_std = GaussianStd(0.1, 
                     can_change=True,
                     metadata = {"mutation_chance" : 0.1, "std" : 0.1}
)
lr_mutation_rate = GaussianMutationChance(0.25)

learning_rate_allele = LogFloatAllele(
    value=0.01,
    domain={"min" : 1e-6, "max" : 1e-2},
    metadata ={"mutation_chance" : lr_mutation_rate, "std" : lr_std}
)


```

The Gaussian mutation handler recognizes these types in metadata and knows how to use them. Other strategies (Cauchy, differential, etc.) would define their own subclasses.

**Integration:** When you design a strategy, you:
1. Define custom allele subclasses for your parameters
2. Expose a setup genome method that handles the necessary allele modifications.
3. Write handlers that recognize and use those subclasses

This keeps strategy-specific logic in strategy-specific types, not scattered across generic alleles.

---

## Example: Self-Adaptive Gaussian Mutation

```python
def gaussian_mutate(allele):
    def mutate_value(node):
        # node.metadata is flattened: all raw values
        chance = node.metadata["mutation_chance"]
        std = node.metadata["std"]

        if random.random() > chance:
            return node  # No mutation

        # Return new allele with mutated value
        new_value = node.value + random.gauss(0, std)
        return node.with_value(new_value)

    return allele.update_tree(mutate_value)
```

The handler never sees nested alleles — `node.metadata["std"]` is a raw float. The tree utilities handled recursion and flattening.

---

## Key Contracts

- Value is never an allele. Always a raw type.
- Metadata can contain alleles or raw values. Alleles recurse, raw values don't.
- Use  `include_can_mutate=False` or `include_can_crossbreed=False` to exclude marked nodes while walking.
- Alleles are immutable. All modifications return new instances.
- Domain must match allele type.
- Tree utilities flatten metadata before calling handlers.
- Tree operations are depth-first, children-first.
- List order is preserved across recursion in tree utilities.
- Domain validation and clamping happens in `__init__` and `with_value`.
- Users extend concrete types (FloatAllele, etc.) for strategy-specific alleles, not AbstractAllele.
- Handlers in `synthesize_allele_trees` return a new allele.
- When walking trees in parallel, all nodes must be the same type or the walkers will throw. 