# Genetics Lifecycle

This document describes the high-level lifecycle of the genetic system in ClanTune, from raw parameters to adaptive metalearning structures. This system is called into by the clan package to handle the genetic learning abilities 

---

## Overview

The genetic system operates in distinct phases. Note critically that this happens in tandem with the main clan tune system and thus main model training. The evaluation step goes through the relevant cooperative/competitive phases. It should be kept in mind the genetics package is designed to be called into by higher level orchestration systems located in the clan package; "orchestration" refers primarily to responsibilities such as individual or state in clan.  

### Note

This is a living vision and guidance document. As such, it is something of an abstract not concrete spec. As concrete specs are designed and created, changes should be backpropogated into this document if possible. Still, it might end up slightly out of date. 

This is not a full specification, more analogous to an abstract specification listing major points of integration. As such, there will be methods or responsibilities that are not listed in this document.

### Design

The genetics system conceptually has a frontend and a backend. The frontend is where external users interface with the system, while the backend is of deeper concern when programming strategies and other utilities. Regardless, the intention is that programming for this unit uses utility methods and hooks rather than have concrete instances handle tree walking and processing directly; largely, the user defines processing functions that are applied where relevant. 

**User/Frontend Access:**
- Direct interaction with genome datastructure
- Operations: `add_hyperparameter(name, allele)`, `as_hyperparameters()`, `set_fitness()`, `get_fitness()`
- Simple, immediate access to genetic material
- Used during genome construction and result extraction

### Orchestration

Orchestration is imposed externally, not internally. This may change as development occurs. Nonetheless, the genetics package is intended to be called into. The setup phase involves creation of actual nodes. The execution phase edits the value in nodes of existing datastructures. 

A rough outline is as follows

1. **Setup**:
   * Process is created; communication setup.
   * Create empty genome; other systems create same model on all devices, or load from checkpoint
   * Populate empty genome with flat alleles for hyperparameters
   * Inject metalearning alleles if relevant using setup_strategies
2. **Execution Loop**
    * Orchestration systems elsewhere evaluate and set fitness on genomes: Main training process including cooperative phase and duty cycles, ending in a validation loss. This is set as genome fitness
    * Orchestration systems gather genomes from all devices.
    * Orchestration systems call into crossbreeding; down to one genome again based on fitness.
    * Orchestration systems call into mutation; genome mutates.
    * Orchestration systems builds new individual based on genome.

One final thing of note is orchestration passes populations around as a list where the index corrosponds to the rank.

### Subclassing and Implementing

Strategy and infrastructure access are subclasses that have to be defined internally. 

Datastructures follow a pattern where datastructures are defined with utilities such as walkers or updaters that take a "handler" function per node and handle the process, in a fairly functional manner. Concrete subclasses are intended to be coded with hooks that can be overridden, with those hooks ultimately being injected into the processing system by these kinds of utilities after whatever mangling is needed. 

- Indirect interaction via handlers passed to walking utilities
- Strategies provide small handler functions, genome/allele utilities handle traversal
- Handlers receive alleles with context (e.g., `is_hyperparameter` flag)
- During setup: strategies MAY insert tree nodes (metaparameters into metadata) - they code ONLY this part
- During apply: strategies are expected to manipulate the values in trees
- Walking/synthesis logic coded ONCE at genome/allele level
- Strategies stay lightweight and decoupled - no knowledge of genome structure

## Component Responsibilities

### Alleles

The alleles.py file.

**The Allele Class**
AbstractAllele is the internal tree datastructure. Concrete types: FloatAllele, IntAllele, LogFloatAllele, BoolAllele, StringAllele. Each represents a single genetic parameter with value, domain, and metadata. It is intended to be interfaced using the provided walking nodes by their contract, not manipulated directly.
- Store parameter value and domain constraints
- Store metadata dict (tree datastructure for metalearning)
  - MutationStrategy may inject alleles here for metalearning (GaussianStdAllele)
  - Metadata CAN contain alleles, which CAN have their own metadata (recursive trees)
- Provide tree walking utilities for allele trees (walk_tree, update_tree)
- Handle serialization/deserialization of alleles via registry
- Be subclassed for strategy-specific alleles (e.g., GaussianStd, GaussianMutationChance)

**The Allele Utilities**

Tree walking and synthesizing utilities exist as well, to walk collection of allele trees at the same time or even synthesize a tree out of an existing allele tree. These come as methods on the class, or freeform methods in the file. Regardless, the intention is that while creation of additional datastructure elements may sometimes occur manually, manipulation and editing is done almost entirely through the walker utilities. 

**What they DON'T do:**
- Decide how to mutate (MutationStrategy's job)
- Decide how to crossbreed (CrossbreedingStrategy's job)
- Track fitness (Genome's job)

**Concrete types:**
- **FloatAllele**: Linear floating point values
- **IntAllele**: Integer values (float-backed, rounded)
- **LogFloatAllele**: Log-space floating point (min > 0 required)
- **BoolAllele**: Boolean flags ({True, False})
- **StringAllele**: Discrete string choices

### Genome

**What it is:** The primary frontfacing genetics datastructure and associated utilities. Stores genetic material (alleles), tracks fitness, and provides walking/synthesis infrastructure for strategies.

**The Genome class:**
- Unique identifier (UUID) - immutable, set at creation. Note this can be passed in, but if none is manufactured.
- Stores Dict[name, allele] mapping
  - **Implementation note:** By convention, name encodes patch path for hyperparameters (e.g., "optimizer/0/lr"). However, this is externally caused by assignment, not enforced. 
- Parents field: Optional[List[Tuple[float, UUID]]] - records contribution probabilities of parent genomes by uuid for model state inheritance (orchestrator uses this to resolve which parent models to sample from)
- Fitness tracking (set_fitness, get_fitness) - stores evaluation result.
- Immutable - all operations return new genomes.
- Frontend access methods (add_hyperparameter, as_hyperparameters, etc.).
- Handle serialization/deserialization of genomes, genome fields, and thus also alleles
- Thin wrappers into module utilities on methods. 

**Utilities (module-level functions):**

The module utilities exist as stand alone behavior, and also in many cases can be accessed through thin wrappers on the methods. 

- `walk_genomes(genomes, handler, ...)` - walk genome alleles across multiple genomes
  - Walks hyperparameters and their trees in parallel
- `synthesize_genomes(template_genome, genomes, handler, ...)` - synthesize new genome from multiple sources. Used in crossbreeding and mutation.

**Instance convenience wrappers:**
- `genome.walk(handler, ...)` - wraps `walk_genomes([self], handler)`
  - Single-genome wrapper over multi-genome utility
- `genome.update(handler, ...)` - wraps `synthesize_genomes(self, [self], handler)`
  - Single-genome wrapper over multi-genome utility 
- `genome.synthesize(genomes, handler, ...)` - automatically fills in the template genome as self, ensuring skipped alleles remain as they were originally. useful in crossbreeding

**What it DOESN'T do:**
- Mutation logic (MutationStrategy provides handlers)
- Crossbreeding logic (CrossbreedingStrategy provides handlers)
- Strategy parameter injection logic (strategies provide setup handlers)
- Population-level selection/orchestration (higher-level concern)

### Strategies

Strategies are the main in-progress allele structure editors, and come in a crossbreed and a mutation flavor. They always have as a responsibility the need to handle their specific case when their apply method is called. They may, if so configured, also make their setup method inject additional metalearning alleles as well.

**The pattern:**
- The root abstract class defines the apply_strategy as a necessary field, and provides both the setup_genome public interface and define the handle_setup hook subclasses can override.
- The specialized abstract classes define their necessary apply_strategy abstract method, then release a new abstract method for handle_mutation or handle_crossbreed in whatever way is relevant. 
- Concrete instances can override their relevant hooks. If metalearning is desired, they may also override the handle_setup hook to inject top-level alleles with metadata learning alleles.
- Flags that are not present in metadata are instead filled in by default values
- Strategies can respond to each other's flags. A allele injected by a crossbreeding strategy with can_mutate on will be responded to by the default mutation strategy, allowing complete metalearning.

---

**AbstractStrategy:**

The abstract strategy is the root strategy class, and largely dedicated to metalearning support. It also exists to give a common ancestor to all strategies. 

- Provides optional setup capability (inject metalearning if desired)
- Public utility: `setup_genome(genome)->genome` - for injection of metalearning context. Publically available.
- Hook: `handle_setup(allele) → allele` - Called against all top level alleles. Gives an opportunity to inject additional allele metadata. 
- Setup injects ONLY metalearning trees (alleles in metadata), nothing else
- If setup not called or metalearning disabled, apply uses strategy's internal defaults
- Leaves `apply_strategy(*args, **kwargs)->genome` abstract - mutation and crossbreeding subclasses define their own signatures

**AbstractMutationStrategy:**

The mutation strategy is responsible for mutating active alleles. It can inject metalearning alleles to modify
mutation parameters on the fly.

- Schema: `apply_strategy(genome) → genome` (single genome in/out)
- Hook: `handle_mutating(allele) → allele` - concrete strategy for mutation logic. Called against anything
  where can_mutate flag is set to true. 
- Reads metadata for parameters, falls back to internal defaults (e.g., `self.default_std`) when missing;
  do not expect metadata to have necessary fields by default. 
- Preserves genome.parents field (doesn't change model ancestry)

**AbstractCrossbreedingStrategy:**

The crossbreeding strategy is the primary location fitness is processed. It reduces many genomes including the primary one down to one. This proceeds in two primary phases. In the first one, we evaluate fitness and select the ancestry the genome we are building will be considered to have. In the second phase, we use this ancestry and process our allele and the population alleles into the allele for the next generation, handling statistical random processes. Note that the ancestry is exposed on the resulting genome, and must be exposed so the orchestrator can handle model and optimizer crossbreeding in whatever method it desired. 

- Schema: `apply_strategy(my_genome, population_genomes) → genome` (multiple genomes in, single genome out)
- Multi-genome operations (combine parent genomes into offspring)
- Hook: `select_ancestry(my_genome, population_genomes)->ancestry` - concrete strategies decide which parents and contribution probabilities.
  - Returns ancestry: `List[Tuple[float, uuid]]` mapping contribution probabilities to parent UUIDs.
    All positions are filled; length is population and if unused probability is zero.
  - Genome-level decision: "which parents, how much each contributes"
  - Tournament, filtering, etc logic can go here.
- Hook: `handle_crossbreeding(my_allele, population_alleles, ancestry) → allele`
  - Allele-level execution: "combine these alleles using the ancestry, give me a new one"
  - Supports a wide range of strategies for crossbreeding.
- Sets offspring.parents to ancestry and fills in new genome with crossbreed allele.

---

**What strategies DON'T do:**
- Compute fitness (evaluation's job)
- Manipulate model state directly (parents field provides hints for orchestrator)
- Require coordination between strategies (each independent)

---

## Lifecycle Details 

The genetics system enables population-based hyperparameter adaptation during ML training. A population of genomes evolves over training rounds, with each genome paired with a model+optimizer. Genomes control hyperparameters (learning rate, dropout, etc.), models hold weights. Evolution discovers effective hyperparameter schedules through selection pressure.

Restating the flow from the introduction, we have: 

1. **Setup**:
   * Process is created; communication setup.
   * Create empty genome; other systems create same model on all devices, or load from checkpoint
   * Populate empty genome with flat alleles for hyperparameters
   * Inject metalearning alleles if relevant using setup_strategies
2. **Execution Loop**
    * Orchestration systems elsewhere evaluate and set fitness on genomes: Main training process including cooperative phase and duty cycles, ending in a validation loss. This is set as genome fitness
    * Orchestration systems gather genomes from all devices.
    * Orchestration systems call into crossbreeding; down to one genome again based on fitness.
    * Orchestration systems call into mutation; genome mutates.
    * Orchestration systems builds new individual based on genome.

It should be kept in mind the primary orchestration is external to the main genomes package, as it requires integration of the model and optimizer state. 

### Setup Phase

Population initialization begins with genome creation. Each genome is populated with hyperparameters as flat alleles - simple parameter values like `FloatAllele(0.001)` for learning rate or `IntAllele(256)` for batch size. Alleles are named by patch path convention (e.g., "optimizer/0/lr") indicating where they apply in the training configuration; this however is primarily caused externally by setting their name to such.

Strategy setup follows. Each strategy (mutation, crossbreeding) can inject metalearning genes into alleles if configured to do so, at which point those metadata alleles will then begin to respond appropriately to the default configuration in the strategies. 

For each genome, the orchestration mechanism initializes a corresponding model and optimizer. This pairing - genome + model + optimizer - forms a population member; the genetics system's responsibility is managing and manipulating the genome attached to it. The genome's parents field is initially None (no genetic history yet). The population is now ready for the evolution loop.

### Execution Loop

The evolution loop runs in rounds. Each round consists of evaluation, selection, genetic operations, and implementation.

**Evaluation:** Each population member trains for a round using its genome's hyperparameters to configure training (learning rate schedule, regularization, etc.). At round end, fitness is computed using validation loss and assigned to the genome via set_fitness(). Genomes are then extracted from the population class for evaluation.

**Selection and Genetic Operations:** The orchestrator applies the crossbreeding strategy. Crossbreeding strategies combine parent genomes to produce offspring genomes. The strategy's select_ancestry hook decides which parents contribute and with what probabilities, returning ancestry as `List[Tuple[float, uuid]]` in rank order with the selection probability and the parent uuid. The offspring genome receives this ancestry in its parents field - recording its genetic lineage. Metadata hooks are read first, then falling back to default if not used or present.

Mutation strategies modify offspring genomes. The handle_mutating hook applies mutations to alleles, reading metadata for parameters like std or mutation_chance and falling back to strategy internal defaults when metadata is absent. Mutation preserves the genome.parents field - the genetic lineage remains intact.

**Implementation:** For each offspring genome, a new population member must be constructed. The orchestrator reads genome.parents ancestry to determine how to construct the offspring model from parent models and optimizer state; the exact implementation is part of that portion of the model. The offspring genome's hyperparameters configure the new training run, with the final "phase" of crossbreeding being handled at the genetics/model interface. 

The new population (offspring genomes + models) replaces poor performers, and the next round begins. Over many rounds, genomes evolve toward effective hyperparameter schedules through selection pressure.

