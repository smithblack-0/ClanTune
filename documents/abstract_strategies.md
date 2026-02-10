# Abstract Strategies Specification

## Overview

This document specifies the abstract base classes for the strategy system. Strategies provide decision logic for genome evolution - which alleles to mutate, which parents to select, how to combine values. The abstract classes define the hook-based pattern and delegation contracts; concrete implementations provide the algorithms. This document specifies the abstract strategies. Concrete subclasses are specified elsewhere.

## Common points and Context

Certain behavior is common across the abstract strategy system, or enforced upon the system by the broader context.

**Hook-based architecture:** Strategies provide small handler functions that operate on individual alleles. Concrete classes when implemented only worry about implementing these hooks. The abstract classes main responibilities are providing and orchestrating these hooks. Tree walking is dispatched into genome or allele tree walking mechanisms.

**Concrete Vs Abstract** Since this defines only the abstract use cases, pay attention to whether a responsibility is abstract, and thus implemented in this spec, or concrete, and thus only the interface is declared in this spec. In some cases, it also may be a hook that just has a declared default action.

**Genomes and Alleles**: Familiarity with genomes and alleles in the manner of genetics lifecycle is presumed.

**Common patterns across all Abstract Strategies:**
- Metalearning responsibilities are supported but not implemented as hook infrastructure at the abstract level. Concrete strategies can implement their own hooks for metalearning.
- Abstract strategies delegate to utilities for tree and genome walking purpose., not implement their own logic themselves. A need to do all the logic ourself is a sign of a spec bug. The strongest algorithmic responsibility of these strategies is in fact this orchestration.
- Concrete subclasses should check metadata for their algorithm coefficients, and fill in using defaults if they do not exist, to support metalearning easily.

## AbstractStrategy

The root strategy class providing optional setup infrastructure. This is never intended to be driven to a concrete class directly, but is instead the parent of some other abstract classes, which are then made concrete.

Child Concrete strategies are provided a chance during orchestration to inject or modify existing alleles during setup. This is intended to support metalearning, by permitting the injection of additional alleles into metadata. The default action returns the same allele originally passed in, and the main owned responsibility is orchestration of concrete hooks into tree utilities in the setup system and interfaces; all other responsibilities are implemented elsewhere or delegated. 

Stateless.

### setup_genome

An optional setup hook that can be overridden by concrete subclasses, and will be given a chance to transform the allele tree once before training begins. Usable with the right tweaks for metalearning - one can inject additional alleles into metadata then look them up later during allele update and traversal

The hook and default implementation is owned here. Concrete subclasses are responsible for setting up their own metalearning alleles and remembering to check for the value during strategy application. 

```python
setup_genome(genome: Genome) -> Genome
```
Called once during genome initialization. Walks the allele dictionary directly as a key,value walk, calling handle_setup on each allele and rebuilding the dict. Returns genome with metadata alleles injected in top-level alleles.

### handle_setup

Small optional hook called into to setup metalearning. The default no-op implementation is owned here.

```python
handle_setup(allele: AbstractAllele)-> AbstractAllele
    """By default, no change."""
    return allele
```

Called on each top-level allele during setup. Concrete strategies override to inject metadata via `allele.with_metadata(**updates)`. Default implementation returns allele unchanged. Never modifies allele.value - setup injects only metadata.

**Implementation danger**

Do NOT make any algorithm you implement reliant on injecting raw values like "std" : 0.3 that is injected into metadata. This will break as, for example, the mutation strategy sets up additional nodes that need crossbreeding information, when the crossbreeding setup already went off. Instead, only inject alleles.

### apply_strategy

Abstract method which must be filled in by other subclasses,
indicating how exactly a genome or population of genomes is transformed. 

```python
apply_strategy(*args, **kwargs) -> Any
```

Subclasses should instead narrow down their typing to the necessary
typehints, and implement their own strategies. Aligning with the vision for concrete classes, this means downstreama abstract strategies calling into hooks.

### Contracts

- Setup is optional - orchestrator decides whether to call setup_genome
- Setup injects ONLY metadata alleles, never modifies values
- Apply methods must work with or without setup (using internal defaults)
- Multiple strategies can inject metadata without coordination - each defines its own schema
- Strategies are independent - no coordination required
- Ownership of the metadata infrastructure is here. Ownership of the decision to implement, dereference, flag usage, or anything beyond infrastructure is a concrete subclass issue.


## AbstractAncestryStrategy

Separates parent selection (declare) from allele synthesis (interpret) or model synthesis (interpret). Ancestry strategies decide which genomes become parents and their contribution probabilities; crossbreeding strategies interpret those decisions to synthesize allele values. This decoupling keeps genome package ignorant of model/optimizer crossbreeding - selection is about fitness, synthesis is about values.

The declare-interpret paradigm: AbstractAncestryStrategy declares "these parents with this strength" producing an ancestry data structure. Downstream systems (AbstractCrossbreedingStrategy, model state reconstruction) interpret that declaration. This separation enables mixing selection strategies (tournament, fitness-weighted, diversity-based) with synthesis strategies (weighted average, dominant parent, stochastic sampling) independently.t
An ancestry is a list of population length containing for each population member the probability assigned to that parent's contribution and the UUID of the parent. The sum of probabilities typically equals 1.0 (though not enforced - interpreters decide). UUIDs identify population members when ancestry was decided.

The owned responsibility of the abstract class is orchestration into the concrete user hook.

```python
ancestry_alias = List[Tuple[float, UUID]]
```

Abstract class is Stateless. Concrete subclasses are expected to include various thresholds for making decisions.

### apply_strategy

Implements the abstract apply_strategy contract from AbstractStrategy for parent selection. Orchestrates ancestry selection by dispatching to select_ancestry hook. This is declaration, not synthesis - returns ancestry structure, not a genome.

```python
apply_strategy(my_genome: Genome, population: List[Genome]) -> List[Tuple[float, UUID]]
```

Calls self.select_ancestry(my_genome, population) and returns ancestry directly. Crossbreeding strategies and orchestrators consume this ancestry to synthesize offspring and reconstruct model state. Single responsibility: decide parent contributions. 

**Why not just implement apply strategy directly in concrete classes?**

While this could just be implemented by subclasses directly, using the hook allocation schema keeps code consistent. Also gives a chance to throw if fitness is not fully set or my_genome is not in population, or return from user is not of population length.

### select_ancestry

Abstract hook that concrete strategies must implement to decide parent contribution probabilities. This is where fitness-based selection logic lives - tournament selection, fitness-weighted sampling, diversity-based filtering, etc. Fitness will be used to make this selection.

```python
select_ancestry(my_genome: Genome, population: List[Genome]) -> List[Tuple[float, UUID]]
```

Receives my_genome (genome being evolved) and population (all genomes in rank order). All genomes will have a set fitness; lower fitness corresponds to better, and validation loss is the default pattern.

Returns ancestry as `[(probability, uuid), ...]` in rank order where:
- List length equals population size
- Index corresponds to rank
- Entry `(probability, uuid)` indicates that rank's contribution
- Probability 0.0 means no contribution from that parent
- Sum of probabilities typically equals 1.0 (not enforced - interpreters decide)

**Implementation pattern:** Concrete strategies typically sort population by fitness, apply selection logic (top-k, tournament, weighted sampling), then construct ancestry list in original rank order with selected parents having non-zero probabilities. Injection of my_genome allows decisions to be made about survivorship.


### Metalearning

It is recommended, but not strictly required, for concrete subclasses to implement their 
own metalearning strategies. This would consist of, in some cases, overriding the default setup hook to inject additional metalearning alleles onto primary alleles to provide a changeable allele controlling the application of the strategy. This will then be flattened and can be retrieved by the .get with defaults paradigm.

Subclasses, when walking their alleles, should then retrieve their information using .get("name", self.default). This does not care whether metalearning was turned on for this property or not. 

Carefully think through the type and domains of any alleles so chosen.

### Contracts

- Input: my_genome and population (my_genome should be in population).
- Output: ancestry declaration (not a genome - pure selection)
- **Fitness must be set on genomes before calling** - selection logic depends on fitness values
- Ancestry list length equals population size, maintains rank order
- Probabilities indicate contribution (0.0 = excluded)
- No allele manipulation - selection only, not synthesis
- No metadata manipulation - No access to alleles means no way to do metalearning.

## AbstractCrossbreedingStrategy

Provides allele-level crossbreeding by interpreting ancestry to synthesize new allele values. While AbstractAncestryStrategy declares which parents contribute, AbstractCrossbreedingStrategy interprets how that plays out for individual alleles. Implements the abstract apply_strategy contract from AbstractStrategy.

### apply_strategy

Implements the abstract apply_strategy contract from AbstractStrategy for multi-genome crossbreeding. Orchestrates allele crossbreeding by passing self.handle_crossbreeding and ancestry into genome allele walking utilities via the kwargs dict.

```python
apply_strategy(my_genome: Genome,
              population: List[Genome],
              ancestry: List[Tuple[float, uuid]],
              ) -> Genome:
```

Returns new genome with synthesized alleles. Only processes alleles with can_crossbreed == True recursively. Delegates `my_genome.synthesize_new_alleles(population, self.handle_crossbreeding, predicate=CanCrossbreedFilter(True), kwargs={'ancestry': ancestry})`

### handle_crossbreeding

Allele-level hook that concrete strategies must implement to synthesize new allele values from parent alleles using ancestry weights.

```python
handle_crossbreeding(template: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

Receives flattened template (from my_genome with resolved metadata), flattened allele_population (from population), and ancestry parameter. Flattened means you will see the value of an allele, not the allele itself, at it's key position.

Returns new allele, typically via template.with_value(new_value). Should use ancestry weights to combine source values and read template metadata with .get(key, self.default_*) fallback pattern. Template is always built from nodes of my_genome.

### Contracts

- Input: my_genome and population (my_genome must be in population)
- Output: new genome with synthesized alleles
- Only processes alleles with can_crossbreed == True (recursively)
- Ancestry used by orchestrator for model state reconstruction
- Handler receives ancestry unpacked from kwargs dict by synthesize_new_alleles
- Must work with or without metadata; metadata.get recommended.
- Existance of correct ancestry on my_genome is not contracted at this point.

## AbstractMutationStrategy

Provides genome mutation pattern. Implements the abstract apply_strategy contract from AbstractStrategy, orchestrating mutation by filtering alleles and dispatching to problem-specific handle_mutating hook. Subclasses implement mutation logic for individual alleles.

Strategies receive population and ancestry to enable population-aware mutation strategies. Population provides access to other genomes for comparative/differential mutations. Ancestry provides parent selection information for adaptive behavior based on selection strength. Simple mutations ignore these parameters.

Concrete strategies may, and are encouraged, to provide flags that setup metalearning nodes. This is written with this premise in mind. The primary responsibility of the class is orchestration of the user hook into the alleles through delegation and adaption to utilities.

Abstract class is Stateless. Class is intended to be subclassed. Concrete classes would not be stateless.

### apply_strategy

Abstract responsibility.

Implements the abstract apply_strategy contract from AbstractStrategy for genome mutation. Orchestrates mutation by dispatching to the handle_mutating hook with can_mutate filtering. Adapts handler to inject population and ancestry as kwargs through genome.update_alleles. The primary responsibility of the class is orchestrating the injection of the user's hook into the existing walking and modification mechanisms.

```python
apply_strategy(genome: Genome, population: List[Genome], ancestry: List[Tuple[float, UUID]]) -> Genome
```

Delegates to genome.update_alleles, passing self.handle_mutating as handler, CanMutateFilter(True) as predicate, and population/ancestry via kwargs dict. Returns new genome with mutated alleles. Only processes alleles with can_mutate == True, recursively including metadata alleles.

### handle_mutating

Concrete responsibility. Only interface defined here.

Problem-specific hook that concrete strategies must implement to define mutation logic for individual alleles. Receives flattened allele plus population and ancestry context. Abstract, must be implemented by concrete classes.

```python
handle_mutating(allele: AbstractAllele, population: List[Genome], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

Receives flattened allele (metadata contains raw values where nested alleles have been replaced by their values), population, and ancestry. Returns new allele, typically constructed via allele.with_value(new_value). Simple mutations ignore population and ancestry parameters.

It is extremely important to use allele.metadata.get("name", self.name_default) to make code that can robustly handle the situation where algorithm parameters are metalearned or just left alone. This checks for a metalearning allele value first, then falls back to default values if none is available.

Even strategies without metalearning are encouraged to be implemented this way in case future extensions for metalearning are desired. 

### Contracts

- Input: genome, population, and ancestry
- Output: new genome
- Preserves genome structure (same hyperparameters)
- Only mutates alleles with can_mutate == True (recursively)
- Handler receives allele, population, ancestry unpacked from kwargs dict
- Must work with or without metadata
- Population-aware mutations may use population/ancestry; simple mutations ignore them

## StrategyOrchestrator

Coordinates the genome-level evolution cycle by composing ancestry, crossbreeding, and mutation strategies. Rather than requiring users to manually invoke three strategies in the correct order, StrategyOrchestrator packages them together and ensures proper sequencing. This is a convenience utility for testing and simple use cases; higher-level orchestration (Individual, State) handles population management, fitness computation, and model state reconstruction using the ancestry we record.

The orchestrator follows the declare-interpret-mutate-record pattern: ancestry declares parent selection, crossbreeding interprets ancestry for allele synthesis, mutation modifies offspring alleles, and finally ancestry is recorded on the result. External orchestration uses this recorded ancestry to perform model state reconstruction - we handle genome evolution only, not model evolution.

Concrete class. Stateful (holds strategy instances as dependencies), though the strategies themselves are stateless.

### __init__

Constructs orchestrator with strategy dependencies.

```python
__init__(
    ancestry_strategy: AbstractAncestryStrategy,
    crossbreeding_strategy: AbstractCrossbreedingStrategy,
    mutation_strategy: AbstractMutationStrategy
)
```

Stores the three strategies for later use during setup and evolution. Strategies are injected rather than created internally, allowing flexible composition of concrete strategy implementations.

### setup_genome

Chains setup calls through all three strategies in sequence.

```python
setup_genome(genome: Genome) -> Genome
```

Calls `ancestry_strategy.setup_genome(genome)`, then `crossbreeding_strategy.setup_genome(result)`, then `mutation_strategy.setup_genome(result)`. Returns genome with all metalearning metadata injected by the composed strategies. Each strategy gets a chance to inject its metadata alleles; they operate independently without coordination.

### __call__

Executes genome evolution cycle: ancestry selection → crossbreeding → mutation → ancestry recording.

```python
__call__(my_genome: Genome, population: List[Genome]) -> Genome
```

**Algorithm:**
1. Call `ancestry_strategy.apply_strategy(my_genome, population)` → returns ancestry
2. Call `crossbreeding_strategy.apply_strategy(my_genome, population, ancestry)` → returns offspring
3. Call `mutation_strategy.apply_strategy(offspring, population, ancestry)` → returns mutated offspring
4. Call `mutated_offspring.with_ancestry(ancestry)` → attaches ancestry to result
5. Return offspring with ancestry recorded

**Why step 4?** Mutation returns a genome with no parents — it doesn't touch ancestry. The orchestrator owns ancestry expression: it is the orchestrator's responsibility to attach the correct ancestry to the final offspring for downstream model state reconstruction.

### Contracts

- Input: my_genome and population (passed to ancestry and crossbreeding strategies)
- Output: new genome (new UUID, no fitness, parents set to ancestry from step 1)
- Fitness must be set on all genomes before calling (validated by ancestry strategy)
- All three strategies must be provided at construction
- Setup is optional - parent orchestrator decides whether to call setup_genome
- Stateful composition - holds strategy instances

## Predicates

Strategies leverage the predicate filtering system developed in allele.md to control which alleles are processed. Predicates enable fine-grained filtering without modifying handler logic - the same handler can be reused with different filtering criteria.

Allele-level strategies (mutation and crossbreeding) use predicates to filter their tree walking. Genome-level strategies (ancestry) operate on whole genomes and don't use predicate filtering.

**Usage pattern in abstract strategies:**
- AbstractMutationStrategy uses `CanMutateFilter(True)` to process only mutable alleles
- AbstractCrossbreedingStrategy uses `CanCrossbreedFilter(True)` to process only crossbreedable alleles
- Concrete strategies can override apply_strategy to use custom predicates if needed

See allele.md for predicate implementation details and available filter types.

## Subclassing

Concrete strategies extend these abstract classes to provide specific algorithms. The hook-based pattern keeps strategies lightweight and decoupled - abstract classes handle orchestration and tree traversal, concrete classes implement small decision functions. This separation enables reusing traversal infrastructure while varying decision logic.

The abstract classes handle orchestration and delegation; concrete classes provide decision logic via hooks. Strategies implement handlers operating on individual alleles or genomes, while genome and allele utilities handle tree traversal.

### Mutation Strategies

1. Subclass AbstractMutationStrategy
2. Implement handle_mutating(allele) → allele hook
3. Define default parameters as instance fields (e.g., self.default_std, self.default_mutation_chance)
4. Optionally override handle_setup(allele) to inject metadata alleles
5. Optionally define strategy-specific allele subclasses for typed parameters

**Example pattern:**
```python
class GaussianMutation(AbstractMutationStrategy):
    def __init__(self, default_std=0.1, default_mutation_chance=0.15):
        self.default_std = default_std
        self.default_mutation_chance = default_mutation_chance

    def handle_mutating(self, allele, population, ancestry):
        # Read metadata or use defaults
        std = allele.metadata.get("std", self.default_std)
        chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)

        if random.random() > chance:
            return allele

        noise = random.gauss(0, std)
        return allele.with_value(allele.value + noise)
```

### Ancestry Strategies

Implementing AbstractAncestryStrategy requires understanding fitness-based selection patterns. Specs define contracts, but working implementations bridge abstract requirements to concrete code. This section demonstrates subclassing with a tournament selection example.

```python
class TournamentSelection(AbstractAncestryStrategy):
    def __init__(self, tournament_size=3):
        self.tournament_size = tournament_size

    def select_ancestry(self, my_genome, population):
        # Tournament selection: randomly sample, pick best
        import random

        selected_parents = []
        for _ in range(2):  # Select 2 parents
            tournament = random.sample(population, self.tournament_size)
            winner = min(tournament, key=lambda g: g.fitness)  # Lower fitness is better
            selected_parents.append(winner)

        # Build ancestry: equal split for selected parents, 0.0 for others
        ancestry = []
        for genome in population:
            if genome in selected_parents:
                prob = 1.0 / len(selected_parents)
            else:
                prob = 0.0
            ancestry.append((prob, genome.uuid))

        return ancestry
```

Tournament selection randomly samples genomes, picks the fittest from each sample. This balances exploration (random sampling) with exploitation (fitness-based selection). The example selects 2 parents with equal contribution probabilities, setting all other genomes to 0.0.

**Pattern breakdown:**
1. Subclass AbstractAncestryStrategy
2. Implement select_ancestry(my_genome, population) → ancestry hook
3. Define selection parameters as instance fields (e.g., self.tournament_size)
4. Optionally override handle_setup(allele) if needed (rare - ancestry operates at genome level)

### Crossbreeding Strategies

Implementing AbstractCrossbreedingStrategy requires interpreting ancestry to synthesize allele values. Crossbreeding strategies receive pre-computed ancestry from AbstractAncestryStrategy and use it to combine parent alleles. This section shows a dominant parent implementation.

```python
class DominantParentCrossbreeding(AbstractCrossbreedingStrategy):
    def __init__(self):
        pass  # No parameters needed

    def handle_crossbreeding(self, template, allele_population, ancestry):
        # Find parent with highest probability
        max_prob = 0.0
        best_idx = 0
        for idx, (prob, _) in enumerate(ancestry):
            if prob > max_prob:
                max_prob = prob
                best_idx = idx

        # Use dominant parent's value
        return template.with_value(allele_population[best_idx].value)
```

Dominant parent selection uses the allele value from whichever parent has the highest ancestry probability. If ancestry assigns parent A probability 0.7 and parent B probability 0.3, offspring inherits parent A's allele value entirely. Simple and fast.

**Pattern breakdown:**
1. Subclass AbstractCrossbreedingStrategy
2. Implement handle_crossbreeding(template, allele_population, ancestry) → allele hook
3. Define parameters as instance fields if needed
4. Optionally override handle_setup(allele) to inject metadata alleles

### Strategy-Specific Allele Subclasses

Strategies can define custom allele types for their parameters. These subclasses provide typed parameters with appropriate domains and flags. This is commonly used for metalearning - parameters that control mutation/crossbreeding become evolvable genetic material.

**Why subclass:** Encapsulates parameter constraints (domain bounds, mutability flags) in reusable types rather than repeating them at each injection site.

**Pattern:** Extend concrete allele types (FloatAllele, IntAllele, etc.), not AbstractAllele. Set appropriate domain, can_mutate, and can_crossbreed in constructor.

**Example:**
```python
class GaussianStd(FloatAllele):
    """Mutation standard deviation (evolvable)."""
    def __init__(self, base_std, can_change=True, **kwargs):
        super().__init__(
            base_std,
            domain={"min": 0.1 * base_std, "max": 5.0 * base_std},
            can_mutate=can_change,
            can_crossbreed=can_change,
            **kwargs
        )
```

Then use in handle_setup:
```python
def handle_setup(self, allele):
    return allele.with_metadata(
        std=GaussianStd(0.1, can_change=True),
        mutation_chance=0.15  # Raw value: constant
    )
```

### Metalearning Example

Metalearning enables mutation parameters themselves to evolve alongside the values they control. This section demonstrates a complete metalearning implementation using Gaussian mutation with evolvable standard deviation.

```python
class GaussianMutation(AbstractMutationStrategy):
    def __init__(self, default_std=0.1, default_mutation_chance=0.15, use_metalearning=False):
        self.default_std = default_std
        self.default_mutation_chance = default_mutation_chance
        self.use_metalearning = use_metalearning

    def handle_setup(self, allele):
        if not self.use_metalearning:
            return allele

        # Inject evolvable std, constant mutation_chance
        return allele.with_metadata(
            std=GaussianStd(self.default_std, can_change=True),
            mutation_chance=self.default_mutation_chance
        )

    def handle_mutating(self, allele, population, ancestry):
        # Read metadata or use defaults - works with or without metalearning
        std = allele.metadata.get("std", self.default_std)
        chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)

        if random.random() > chance:
            return allele

        noise = random.gauss(0, std)
        return allele.with_value(allele.value + noise)
```

When `use_metalearning=False`, the strategy uses constant defaults. When `use_metalearning=True`, setup injects a GaussianStd allele into metadata. This allele evolves during mutation and crossbreeding - the standard deviation adapts over generations. The `.get()` pattern in handle_mutating ensures the code works regardless of metalearning configuration.

## Ownership

Strategies have abstract ownership of the entire reproduction and hyperparameter delegation pipeline across all components - they define the contracts and patterns for how reproduction works system-wide. Concretely, however, strategies have sole and complete ownership of only genome reproduction.

A genome, by virtue of its stored hyperparameters and ancestry, is *expressed* by downstream concrete logic to achieve the desired population state. This expression logic - configuring models and optimizers from genome data - is not owned by strategies or the genetics package. Strategies define the reproduction interface; external orchestration implements the model side.

**Strategies own (abstract):**
- Reproduction pipeline contracts: parent selection → allele synthesis → mutation → offspring construction
- Hyperparameter delegation pattern: genomes store hyperparameters, downstream applies them
- Ancestry recording pattern: genomes store parent contributions, downstream reconstructs model state

**Strategies own (concrete):**
- Genome reproduction implementation:
  - Parent selection logic (ancestry strategies)
  - Allele value synthesis (crossbreeding strategies)
  - Allele mutation (mutation strategies)
  - Offspring genome construction
- Default parameters (fallback values when metadata missing)
- Metadata schema (what keys and types they inject during setup)
- Handler implementations (selection/crossbreeding/mutation algorithms)
- Strategy-specific allele subclasses (typed parameters)

**Strategies do NOT own:**
- Genome expression (external orchestration applies hyperparameters to models/optimizers)
- Model state reconstruction (external orchestration interprets ancestry to crossbreed model weights)
- Fitness computation (external orchestration evaluates and assigns)
- Tree traversal (delegated to genome and allele utilities)
- UUID assignment, fitness, and parents/ancestry on output genomes — these are StrategyOrchestrator's responsibility. Individual strategies return genomes whose UUID/fitness/parents reflect whatever the underlying genome utilities produce; the orchestrator is solely responsible for ensuring the final offspring has the correct ancestry attached.

**Strategies delegate to:**
- Genome utilities: update_alleles, synthesize_new_alleles (which delegate to walk_genome_alleles, synthesize_genomes)
- Allele utilities: walk_allele_trees, synthesize_allele_trees (via genome utilities)
- Predicate filters: CanMutateFilter, CanCrossbreedFilter (for allele-level strategies)

**Composition pattern:**
- Crossbreeding strategies receive ancestry from ancestry strategies (declare-interpret separation)
- StrategyOrchestrator composes ancestry + crossbreeding + mutation for genome-level evolution
- External orchestration uses recorded ancestry for model state reconstruction
