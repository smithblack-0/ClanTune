# Genome Spec

## Overview

This is the overview specification for the genome.py module.

The genome module provides data structures and utilities for managing evolvable hyperparameter sets in population-based training. The primary component is the Genome class, an immutable container that stores named alleles, tracks fitness, and records parent ancestry for genetic lineage. A set of important utility functions also exist in the module. Thorough testing supports all of it.

All datastructures structures are immutable. Modifications return new instances. Functional handlers are an important pattern to keep in mind.

## Alleles, Genomes, and Populations

The genetics system has a three-tier hierarchy. Understanding where genome fits in this structure clarifies its responsibilities and design. Genome is a thin coordination layer. Alleles handle tree complexity, orchestration handles population complexity. Genome bridges the two, providing methods that translate genome-level operations (update all hyperparameters, synthesize from population) into allele-level operations (walk trees, synthesize trees).

**Alleles** are the foundation. An allele is an immutable tree datastructure representing a single evolvable parameter (see Allele.md). Alleles store a value, domain constraints, and metadata. Metadata can contain other alleles, forming recursive trees that enable metalearning - mutation parameters evolve alongside the values they control. Alleles provide utilities for walking and synthesizing these trees (walk_allele_trees, synthesize_allele_trees). The top level alleles in a genome always correspond one-to-one with tracked hyperparameters, however, rather than metalearning systems.

**Genomes** are a representation of an individual state of hyperparameters. A genome is a lightweight wrapper around a collection of named alleles. It adds genome-level concerns: a unique identifier (UUID), fitness tracking, and ancestry recording. Genomes do NOT manipulate allele trees directly - they delegate to allele utilities. The genome's role is to manage the collection, provide a convenient API for orchestrators and strategies, and handle genome-specific metadata (fitness, parents). When strategies need to mutate or crossbreed, genome methods call into allele tree utilities, passing handlers that operate on individual alleles. Importantly, genome is a passive datastructure - it stores hyperparameter values but does not apply them to models or optimizers. External orchestration reads genome values and applies them to training systems. 

**Populations** are the top tier. A population is a list of genomes, where index corresponds to rank in distributed training. Population management (selection, pruning, repopulation) is handled by external orchestration (Individual and State classes in the clan package). Genomes are not responsible for population-level logic. The parents field in each genome records ancestry as a rank-indexed list to support orchestration's model state reconstruction, but the genome itself does not interpret or act on this - it simply stores it. Information on rank in distributed context is consistently encoded by the index an entry is in a population list. 

## The Genome Class

The core datastructure is the Genome. It is a lightweight wrapper around a group of Alleles with some additional custom methods of its own. The genome class is the primary user-facing datastructure for handling hyperparameter state and mutation

### Core Fields

The Genome class has four fields:

**`uuid: UUID`** — unique immutable identifier. Generated at construction or provided explicitly (for deserialization).
**`alleles: Dict[str, AbstractAllele]`** — mapping of hyperparameter names to alleles. Orchestrators conventionally use the name field to encode a path, like "optimizer/0/lr", telling themselves where to patch in that particular allele. This is not enforced in any way in genome; genome just adds by name.
**`parents: Optional[List[Tuple[float, UUID]]]`** — ancestry record. `None` for initial genomes. Non-None list has length equal to population size, where index corresponds to rank. Entry `(probability, uuid)` indicates contribution from that rank's parent. Probability 0.0 means no contribution. Used by orchestration for distributed model state reconstruction and by internal strategy subsystems.
**`fitness: Optional[float]`** — evaluation result. `None` until assigned.

### Core Methods

The Genome object has two notable modes of operation. One is intended to be interfaced with by whatever orchestrator exists, and is used to insert and set datastructure elements relevant for broader usage as part of ClanTune. The other subset is used interally by strategies. Note that unless listed otherwise, any method that rebuilds a node produces a new uuid. Use with_overrides and pass in the old uuid to get around this if needed. 

**Orchestrator access:**

* **`add_hyperparameter(name: str, value: Any, allele_type: str, **allele_kwargs) -> Genome`** — returns new genome with added hyperparameter.
* **`as_hyperparameters() -> Dict[str, Any]`** — extracts hyperparameters as name → value mapping. Returns values, not alleles.
* **`set_fitness(value: float, new_uuid: bool = False) -> Genome`** — returns new genome with fitness assigned. 
* **`get_fitness() -> Optional[float]`** — retrieves current fitness value. 

**Strategy support:**

* **`with_alleles(alleles: Dict[str, AbstractAllele]) -> Genome`** — reconstructs genome with a new allele package. 
* **`with_ancestry(parents: List[Tuple[float, UUID]]) -> Genome`** — reconstructs genome with a new ancestry package.
* **`update_alleles(handler: Callable[[AbstractAllele, ...], AbstractAllele], predicate: Optional[Callable[[AbstractAllele], bool]], kwargs: Optional[Dict[str, Any]] = None) -> Genome`** — walks alleles, applies handler to each, returns new genome with transformed alleles. Used for mutation pattern. Handler receives `(allele, **unpacked_kwargs)`. Anything that does not pass filtration is skipped.
* **`synthesize_new_alleles(population: List[Genome], handler: Callable[[AbstractAllele, List[AbstractAllele], ...], AbstractAllele], predicate: Optional[Callable[[AbstractAllele], bool]], kwargs: Optional[Dict[str, Any]] = None) -> Genome`** — walks alleles across self and population in parallel, applies handler receiving `(template, allele_population, **unpacked_kwargs)`, returns new genome with synthesized alleles. Uses self as template.

**Serialization:**

Serialization is just a straightforward required function.

* **`serialize() -> Dict`** — converts genome to dict, including recursive allele serialization.
* **`deserialize(data: Dict) -> Genome`** (classmethod) — reconstructs genome from dict.

**Rebuilding:**

* **`with_overrides(**kwargs) -> Genome`** — Reconstruct the given genome with the indicated constructor arguments replaced. Used for almost any function that rebuilds, and the most general-purpose rebuild utility. This is the only thing that can avoid resetting a uuid on rebuild.
* 
---

## Module Utilities Detail


The module provides a small suite of stateless utility functions supporting genome operations. These largely delegate to existing allele utilities (walk_allele_trees, synthesize_allele_trees) while handling genome-level concerns. They exist independently of their instance method wrappers to enable stateless testing - the core logic can be tested without instantiating Genome objects. Instance methods like `update_alleles` and `synthesize_new_alleles` are thin wrappers providing convenient APIs over these utilities.

* **`walk_genome_alleles`** — walks multiple genomes' alleles in parallel, yields handler results.
* **`synthesize_genomes`** — synthesizes multiple genomes into single result using template structure and handler.


### walk_genome_alleles

Orchestrates parallel walking of genomes to allele value for information retrieval. User provides handler that is invoked at each allele node. Internally works by delegating tree walking to `walk_allele_trees`. The utility handles genome-level coordination (collecting hyperparameters, extracting alleles); allele utilities handle tree traversal and recursion. Populations move in rank order allowing information extraction by relevant indexes. 

Note that lists are passed around in population order. This means it is expected that to extract information about a particular population entry you can design your handler closure to extract that entry, by index, from passed in lists. 

```python
def walk_genome_alleles(
    genomes: List[Genome],
    handler: Callable[[List[AbstractAllele], ...], Optional[Any]],
    predicate: Optional[Callable[[AbstractAllele], bool]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
) -> Generator[Any, None, None]:
```

**Algorithm:**
1. Collect hyperparameters across genomes
2. For each hyperparameter: extract alleles, delegate to `walk_allele_trees`
3. Yield results from allele walker

**Handler contract:**

User handler receives `List[AbstractAllele]` (one per genome, in population list order) and any entries from `kwargs` unpacked as keyword arguments. Returns `Optional[Any]`. Pass `kwargs={'key': value}` at the call site; handler receives them as `handler(alleles, key=value)`.

**Invariants:**
- Genomes must have matching schemas for corresponding hyperparameters
- Type consistency enforced by `walk_allele_trees` (raises TypeError on mismatch)

### synthesize_genomes

Orchestrates genome synthesis by delegating allele tree synthesis to `synthesize_allele_trees`. The template genome defines structure; allele utilities handle tree synthesis; genome utility adapts handlers and constructs results. Kwargs can be passed in externally to contextualize synthesis. This will produce a new genome with new uuid, no fitness, and no ancestry. 

```python
def synthesize_genomes(
    main_genome: Genome,
    population: List[Genome],
    handler: Callable[[AbstractAllele, List[AbstractAllele], ...], AbstractAllele],
    predicate: Optional[Callable[[AbstractAllele], bool]] = None,
    kwargs: Optional[Dict[str, Any]] = None,
) -> Genome:
```

- `main_genome`: The primary genome, or 'self' of the process. Used to isolate the allele region to use for autofill when filtration skips a node, and also ensures allele nodes at that population slot are available in the appropriate part of the handler
- `population`: Usually the population, but technically just needs to be a list of genomes. Note that the main genome must be in this list. The alleles at the corrosponding spots will be exposed to the handler for resolution.
- `handler`: Handles transforming allele nodes. See the handler section below. 
- `predicate`: An allele predicate. See allele.md, or use allele.py filters. 

Note that main genome serves as the default when predicate skips handler

**Algorithm:**
1. Validate the inputs are sane.
2. Adapt the user-provided handler to the expectations of the allele walking utilities
3. Walk alleles in parallel, dispatching populations of alleles into allele utilities and collecting the resulting merged allele list.
4. Rebuild genome using "with_overrides" on template genome with new alleles.

**Handler Expectations**

The handler creates a new allele for the next generation from the template allele and population alleles. It accepts:

* **template allele** (AbstractAllele): The allele from the template genome. Note that it contains any updated metalearning suballeles already flattened to raw value for easy usage. No need to do GaussianSTD.value; it is already extacted. 
* **allele population** (List[AbstractAllele]): Across the population, at this common tree node, what alleles exist at the various ranks.
* **keyword arguments**: entries from `kwargs` dict, unpacked as named parameters. Pass `kwargs={'scale': 2.0}` at call site; handler receives `handler(template, allele_population, scale=2.0)`.

The handler should use `template.with_value(new_value)` to create the new allele. The template provides domain and structure; the handler computes the new value from the population alleles.

**Adapting handlers:**

User handler expects `(template, population, **unpacked_kwargs) -> allele`. Allele utility `synthesize_allele_trees` expects `(template, population) -> allele` (no kwargs). The adapter bridges this by closing over `kwargs`:

```python
def adapted_handler(template, allele_population):
    # Called by synthesize_allele_trees (no kwargs parameter)
    # Unpack kwargs dict into named arguments
    return user_handler(template, allele_population, **(kwargs or {}))
```


**Invariants:**
- Template genome present in genomes list
- All genomes have matching schemas for corresponding hyperparameters (enforced by `synthesize_allele_trees`)

**Error conditions:**
- ValueError: main_genome not in genomes list
- TypeError/ValueError: schema mismatches (raised by `synthesize_allele_trees`)

## Ownership

Genome is largely about coordination and orchestration. It owns

* Holding the top level alleles themselves
* Providing access into those allele through handler functions.
* Walking the top-level alleles.
* Fitness, ids, and ancestry
* Supporting hyperparameter extraction for primary training
* Dispatching through add_allele to string-keyword relevant concrete types.

It does not own

* What mutations or crossbreeding to make

It forwards

* How to walk the allele tree (instead delegated, with an access point here)

