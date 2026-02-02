# Allele Spec

## Overview

An allele is an immutable data container representing a single evolvable parameter. Alleles form trees via their metadata — metadata can contain other alleles, which themselves have metadata. This recursive structure enables metalearning: mutation parameters evolve under selection pressure alongside the values they control.

This system is entirely immutable. 

Note concrete implementations should include type hints. 

## Core Structure

Every allele has five fields:

**`value: Any`** — the actual parameter value. Type depends on subclass.
**`domain: Domain`** — constraints on valid values (min/max bounds or discrete choices). Exact details will follow.
**`can_mutate: bool`** — signals whether this allele's value should participate in mutation. This is signaling only — the allele does not enforce it. Utilities and strategies should be setup to respect it
**`can_crossbreed: bool`** — signals whether this allele's value should participate in crossbreeding. Signaling only, not enforced by the allele.

**`metadata: Dict[str, Any]`** — recursive tree. Values can be alleles (which recurse) or raw values (which don't).

## Core Methods

**`with_value(new_value) -> Allele`** — returns a new allele with updated value. Applies domain validation and clamping through constructor
**`with_metadata(**updates) -> Allele`** — returns a new allele with metadata entries added or updated. Used for incremental construction.
**`walk_tree(handler) -> Generatort[Any, None, None]`** — walks this allele's tree and yields results. Thin wrapper around `walk_allele_trees` for single-tree use.
**`update_tree(handler) -> Allele`** — transforms this allele's tree. Thin wrapper around `synthesize_allele_trees` for single-tree use. Returns a new tree with the updates
**`serialize() -> Dict`** — converts to dict, including recursive serialization of metadata alleles.
**`deserialize(data) -> Allele`** (classmethod) — reconstructs from dict, including recursive deserialization.

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

When this tree is mutated:
1. Mutate the std allele first (using its `mutation_std` constant)
2. Use the updated std value to mutate the learning rate
3. Return the new tree with both values updated

Children are processed before parents. Metadata values feed into parent operations.

---

## Tree Utilities

The allele module provides functional tree walking and synthesis utilities. These handle recursion and metadata flattening — user code never sees nested alleles, only flat data.

### walk_allele_trees

```python
def walk_allele_trees(
    alleles: List[Allele],
    handler: Callable[[List[Allele]], Optional[Any]],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> Generator[List[Any], None, None]:
```

Keep in mind the walk is depth-first and child-first.

Walks multiple allele trees in parallel (depth-first, children-first). At each node:
1. Recursively processes all metadata alleles first
2. Proceed if filter passes, else skip.
3. Flattens metadata: replaces allele entries with their `.value`, leaving raw values unchanged
4. Passes a list of flattened alleles (one per input tree) to `handler`
5. If `handler` returns a value (not None), collects it in the result list
6. Returns list of all values yielded by `handler` across the entire walk; skip if everything was none. 

**Flattened allele:** An Allele where `metadata` contains only raw values (allele entries replaced with their `.value`).

**Use case:** Inspection, collection, comparison. Crossbreeding strategies use this to see multiple parents' values side-by-side.

### synthesize_allele_trees

```python
def synthesize_allele_trees(
    alleles: List[Allele],
    handler: Callable[[List[Allele]], Any],
    include_can_mutate: bool = True,
    include_can_crossbreed: bool = True,
) -> Allele:
```

Walks multiple trees and synthesizes a single result tree. At each node:
1. Recursively processes all metadata alleles first (producing updated child alleles)
2. If case not included, just rebuild myself with my new metadata.
3. Flattens metadata of the original alleles
4. Passes list of flattened alleles to `handler`
5. `handler` returns a new **value** (not a new allele, just the value)
6. Reconstructs the first allele with the new value and the updated metadata from step 1
7. Returns the new tree

**Handler contract:** Returns only the new value. The utility handles rebuilding the allele with that value and the updated metadata.
**Use case:** Mutation strategies (transform one tree), crossbreeding strategies (combine multiple trees).

### Instance Methods: walk_tree / update_tree

Allele provides thin wrappers for single-tree operations:

```python
def walk_tree(self, handler, include_can_mutate=True, include_can_crossbreed=True)->Generator[Any, None, None]:
    ...
def update_tree(self, handler, include_can_mutate=True, include_can_crossbreed=True)->Generator[Any, None, None]:
    ...
```

These hide the list-based API when you're only operating on one tree.

### Metadata Flattening

Before calling user handlers, metadata is flattened:
```python
flattened_metadata = {
    key: node.value if isinstance(node, AbstractAllele) else node
    for key, node in allele.metadata.items()
}
```

Handlers receive alleles where metadata contains only raw values. Decision logic is simple — no need to understand recursion or tree structure.

## Tree Construction

Trees are intended to be constructed functionally,
and can be constructed a bit at a time using 
with_metadata(**updates). They may also be constructed
by directly passing the relevant metadata into the constructor

## Domain

Domain defines valid values. Must match allele type. They go off when 
the constructor is triggered. 

**Continuous (min/max):**
```python
Domain(min=0.0, max=1.0)   # Bounded
Domain(min=0.0, max=None)  # Unbounded above
```
Used by FloatAllele, IntAllele, LogFloatAllele. Note LogAllele requires min and requires it is greater than zero.

**Discrete (set):**
```python
Domain(choices={"adam", "sgd"})
Domain(choices={True, False})
```
Used by StringAllele, BoolAllele.

**Type matching:** Continuous domains for numeric alleles, discrete for string/bool. Domain validation and clamping happens in `__init__`.

---

## Ownership

The allele owns:
- Value storage and type semantics
- Domain enforcement via constructor
- Immutable copy operations
- Serialization/deserialization

The utilties own:

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
        super().__init__(value, 
                         can_crossbreed=can_change,
                         can_mutate=can_change,
                         domain={min=0.1*base_std, max=5.0*base_std},
                         **kwargs)
        

class GaussianMutationChance(FloatAllele):
    def __init__(self, value, **kwargs):
        super().__init__(value,
                         can_mutate = False,
                         can_change=False,
                         domain={min=0.1, max=0.9}, 
                        **kwargs)
```

Then constructs alleles using these subclasses:

```python
learning_rate_allele = LogFloatAllele(
    value=0.01,
    domain={min=1e-6, max=1e-2},

).with_metadata(
    mutation_chance=GaussianMutationChance(0.15),
    std=GaussianStd(0.1, can_change=True).with_metadata(
        mutation_chance=0.05  # Raw value: constant
        std = 0.1 # Raw value; knows how to mutate it, but no deeper metamutation.
    )
)
```

Or alternatively

```python


lr_std = GaussianSTD(0.1, can_change=True,
                     metadata = {mutation_chance : 0.1, std=0.1}
)
lr_mutation_rate = GaussianMutationChance(0.25)

learning_rate_allele = LogFloatAllele(
    value=0.01,
    domain={min=1e-6, max=1e-2},
    metadata ={"mutation_chance" : lr_mutation_rate, "std" lr_std}
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
            return node.value  # No mutation
        
        # Return new value only (not new allele)
        return node.value + random.gauss(0, std)
    
    return allele.update_tree(mutate_value)
```

The handler never sees nested alleles — `node.metadata["std"]` is a raw float. The tree utilities handled recursion and flattening.

---

## Key Contracts

- Value is never an allele. Always a raw type.
- Metadata can contain alleles or raw values. Alleles recurse, raw values don't.
- Use  `include_can_mutate=False` or `include_can_crossbreed=False` to override this behavior.
- Alleles are immutable. All modifications return new instances.
- Domain must match allele type.
- Tree utilities flatten metadata before calling handlers.
- Tree operations are depth-first, children-first.
- Domain validation and clamping happens in `__init__` and `with_value`.
- Users extend concrete types (FloatAllele, etc.) for strategy-specific alleles, not AbstractAllele.
- Handlers in `synthesize_allele_trees` return only the new value, not a new allele.