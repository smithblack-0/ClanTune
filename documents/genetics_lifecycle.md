# Genetics Lifecycle

Genetics is the reproduction library for clan training. Individual training processes call into it when a round ends and the population needs to evolve. Genetics takes genomes with fitness scores, applies selection and genetic operations, and returns offspring genomes ready for the next round. It does not train models, compute fitness, or coordinate between processes.

Genetics is abstractly responsible for all reproduction. It decides what offspring should be — both the alleles they carry and the ancestry distribution that specifies how they were derived from parents. It is concretely responsible for genome reproduction: offspring alleles are fully resolved by the genetics pipeline. Model and optimizer reconstruction use the ancestry distribution genetics produces, but the implementation of that reconstruction is downstream of genetics. The ancestry distribution is the handoff point: genetics owns the decision, downstream systems own the execution.

This is a vision document. Concrete specifications for each component live under `documents/genetics/`. This document captures the architecture, responsibility boundaries, and contracts that span components — things no individual spec can establish alone.

---

## Components

### Alleles

Alleles are the atomic unit of genetic material. Each is an immutable tree: a value, domain constraints, and a metadata dictionary. Concrete allele types divide into continuous (FloatAllele, IntAllele, LogFloatAllele) and discrete (BoolAllele, StringAllele). This distinction constrains strategy composition — continuous alleles support arithmetic operations like averaging and perturbation, discrete alleles support only selection between existing values.

Metadata field on alleles can contain other alleles, creating recursive trees. This is how metalearning works: mutation parameters like standard deviation or scale factors are themselves alleles nested in the metadata of the alleles they control. When the parent allele evolves, its metalearning parameters evolve with it.

Tree walking and synthesis utilities live at the allele level. Strategies never traverse trees themselves but delegate — alleles provide handler functions, and utilities apply them at each node. This ensures traversal logic exists once and strategies remain decoupled from tree structure.

### Genomes

A genome wraps a collection of named alleles with genome-level concerns: a UUID, fitness, ancestry, and arbitrary genome-level metadata. It is a thin coordination layer. Allele names can be anything; by convention, external systems set them to patch paths (e.g., `"optimizer/0/lr"`) indicating where the hyperparameter applies. This convention is externally imposed, not enforced by the genome.

Genomes are immutable — all modifications return new instances. Genome utilities extend allele tree operations to named collections across multiple genomes. Genomes delegate all tree work to these utilities; they never manipulate alleles directly.

### Strategies

Genetics decomposes reproduction into three independent concerns, each with an abstract base class:

- **Ancestry** — Examines the fitness of the genome population and declares a parent probability distribution. Does not touch alleles. 
- **Crossbreeding** — Receives the ancestry distribution and synthesizes offspring alleles from parent alleles. 
- **Mutation** — Perturbs offspring alleles. May use population context for population-aware algorithms.

These concerns do not coordinate with each other. Ancestry does not know how crossbreeding will use its distribution. Crossbreeding does not know what mutation will do. This independence enables composition — strategies are interchangeable by default, constrained only where a genuine requirement demands it.

All strategies extend a common AbstractStrategy root that provides optional metalearning setup infrastructure. Concrete strategies implement hooks for their specific algorithms. A **StrategyOrchestrator** composes the three concerns in sequence: select ancestry, crossbreed, mutate, attach ancestry to the offspring. The strategy orchestrator is the highest level of orchestration the genetics package itself manages.

### Ancestry

The ancestry distribution is the most consequential datastructure in the system because it is consumed outside of the genetics package in order to finish the parameters of a model. It is defined by an ancestry strategy.

* **Ancestry**; `List[Tuple[float, UUID]]` — one entry per population member, indexed by rank. Each entry is a probability and the UUID of the genome at that rank. Probabilities sum to 1.0. Zero means no contribution.

Inside the genetics package, crossbreeding strategies interpret this distribution to synthesize offspring alleles — weighted averaging, parent selection, stochastic sampling, depending on the strategy. Mutation strategies may use it to identify which population members are live for population-aware operations. Externally, orchestration uses them in determining how to crossbreed model parameters.

---

## Contracts

### Declare-Interpret Separation

Ancestry strategies declare. They produce an Ancestry then stop. Every downstream consumer interprets that distribution independently according to its own needs — crossbreeding blends alleles, mutation identifies live population members, model reconstruction samples parent tensors, and externally models have their parameters crossbreed. No interpreter coordinates with any other.

This separation is what makes strategy composition work. Changing how parents are selected requires no changes to how alleles are synthesized or how models are reconstructed. The ancestry distribution is a stable interface between decisions that would otherwise be coupled. It also necessitates designing algorithms correctly; some common algorithms such as Simulated Binary Annealing instead need to be divided into an ancestry component and a crossbreeding component.

The most common failure here is making ancestry decisions at the nonancestry component. A decision to filter down to two parents in crossbreeding and mutation will not correctly be reflected downstream in the model crossbreeding external systems as it was never reflected in ancestry. Downstream systems construct incoherent models from wrong parent tensors. Neither side can detect the other's failure. This is why ancestry is its own strategy class with explicit validation, and why such emphasis is placed on separating the responsibilities.

### Hook-Based Delegation

Strategies implement small handler functions — the decision logic for their specific concern. Abstract base classes orchestrate the machinery: walking genome trees, filtering alleles by predicate, flattening metadata, calling handlers, reconstructing results. Concrete strategies never see genome structure or tree layout. They receive individual alleles (or allele populations) and return alleles.

This keeps strategies lightweight. A mutation strategy that adds Gaussian noise implements one handler function. The abstract base class handles everything else — finding the right alleles, providing population context, reassembling the genome.

### Metalearning

Strategy parameters can become evolvable. During setup, strategies may inject alleles into metadata representing their tunable parameters — mutation magnitude, crossover spread, scale factors. During execution, handlers read these from metadata with fallback to internal defaults. The handler code path is identical whether metalearning is active or not.

This makes metalearning additive. Enabling it injects metadata alleles; disabling it removes them. No handler logic changes. Strategies can also respond to each other's injected metadata — an allele injected by a crossbreeding strategy with `can_mutate` enabled will be evolved by whatever mutation strategy is in play.

### Immutability

All genetic datastructures are immutable. Every modification returns a new instance. In a system where multiple processes hold references to shared genomes after communication, mutating a shared instance would corrupt state across processes invisibly. Immutability eliminates this class of failure entirely.

---

## Lifecycle

Clan training is distributed — each population member lives on its own process with a genome, model, and optimizer. Processes train independently during rounds, communicate genomes at round boundaries, and call into genetics to reproduce. The lifecycle below describes the full round from the external perspective first, then unpacks what genetics does internally.

### The Round

Rounds are orchestrated from outside the genetics package as part of the main clan tune processes.

**Setup** happens once at the start of training. Each process is responsible for arriving at a genome populated with alleles for its tracked hyperparameters — one allele per parameter, initially flat values. Strategy setup is called on each genome to allow strategies to inject metalearning structure into allele metadata. The process then creates a model and optimizer paired with the genome.

**Evolution Loop.**
* **Training.** Each process trains using its genome's hyperparameters through cooperative and competitive phases. At round end, validation performance is computed and assigned to the genome as fitness.
* **Communication.** Each process hands its genome to a communicator and receives back the full collection of genomes from all processes. This collected set — indexed by rank — is the population.
* **Reproduction.** The process calls the StrategyOrchestrator, passing its genome and the population. Genetics runs internally and returns an offspring genome carrying resolved alleles and an ancestry distribution. This is the genetics responsibility.
* **Expression.** The process reads the offspring's ancestry distribution and uses it to construct a new model and optimizer state from parent states — the ancestry probabilities determine which parents contribute to each parameter tensor. This is the final interpretation of the ancestry that genetics declared.  The offspring genome's hyperparameters are expressed into the new training configuration. The next round begins.


Over many rounds, genomes converge toward effective hyperparameter schedules through selection pressure. Metalearning parameters co-evolve, adjusting exploration intensity per gene as the population matures.

### Inside the Setup Pipeline

When the orchestrator is asked to setup the genome, it calls the setup method on the ancestry, crossbreeding, and mutation strategy in that order. It then returns the revised genome.

### Inside the Genetics Pipeline

When the StrategyOrchestrator is called, it runs three stages in sequence. Each stage is an independent strategy that communicates with the others only through the ancestry distribution.

**Ancestry selection.** The ancestry strategy examines fitness across the population and produces an ancestry distribution — which parents contribute to this process's offspring, and with what probability. This is a declaration: the strategy evaluates and decides, but does not act on the decision. No alleles are touched.
**Crossbreeding.** The crossbreeding strategy receives the population and the ancestry distribution. It walks the offspring genome's allele trees, and at each node, its handler synthesizes a new allele value from the parent alleles according to the ancestry. The interpretation is strategy-specific — weighted averaging, dominant parent selection, stochastic sampling, or other approaches.
**Mutation.** The mutation strategy walks the offspring allele trees and perturbs values. Handlers read metalearning parameters from allele metadata when present, falling back to the strategy's internal defaults. Population-aware strategies use the ancestry distribution to identify contributing parents and compute perturbations from population structure.

The orchestrator then attaches the ancestry distribution to the offspring genome, ensuring downstream systems can read it. The offspring is returned with fitness unset and a new UUID — ready for the next round. Expression of the new genome in terms of model and inserted hyperparameter is an orchestrator job. 