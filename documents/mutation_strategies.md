# Mutation Strategies

## Overview

Mutation strategies modify genome alleles to introduce variation, driving exploration of the hyperparameter space. Mutations occur after crossbreeding in the evolution cycle, perturbing offspring values to escape local optima and discover novel configurations. The mutation contract balances exploitation (preserving good solutions) with exploration (discovering better ones).

Mutation strategies implement AbstractMutationStrategy's hook-based pattern. The abstract class handles orchestration (filtering mutable alleles, delegating to genome utilities), while concrete strategies provide decision logic via handle_mutating. Strategies receive population and ancestry context to support population-aware algorithms, though simple mutations ignore these parameters.

**Implementation note:** Handlers receive flattened alleles where metadata contains raw values, not nested alleles. When reading `allele.metadata.get("std", default)`, if std was injected as a GaussianStd allele during setup, metadata returns its value (a float), not the allele object. Tree utilities handle flattening/unflattening; handlers work with raw values.

### Type-Specific Mutation Handling

Mutation strategies must specify how they handle each concrete allele type. Type-specific behavior ensures correct semantics (linear vs log-space, discrete vs continuous).

**Supported types (continuous):**

**FloatAllele** - linear space mutation. Add noise directly to value:
```python
new_value = allele.value + noise
return allele.with_value(new_value)
```

**IntAllele** - integer with float backing. Mutate the underlying float (raw_value), not the rounded integer:
```python
new_raw = allele.raw_value + noise
return allele.with_value(new_raw)  # Rounds internally
```
IntAllele maintains a float internally and exposes a rounded integer via `.value`. Mutation must work with `.raw_value` to enable smooth continuous exploration (3.0 → 3.2 → 3.4 → 3.6 → 4). If you mutated the integer directly, fractional accumulation would be lost. For similar reasons, it is highly recommended to keep perturbing high enough to encourage exploring other rounded states.

**LogFloatAllele** - log-space semantics. Apply multiplicative changes (noise in log space):
```python
new_value = allele.value * exp(noise)
return allele.with_value(new_value)
```
This produces proportional perturbations appropriate for log-scale parameters like learning rates.

**Unsupported types (discrete - not handled by mutation strategies for now):**

**BoolAllele, StringAllele** - discrete types. Mutation strategies skip these (expected to have can_mutate=False). Future extensions may add discrete mutation support.

**Contract:** Each mutation strategy must specify which types it supports and how it mutates each. Strategies receiving unsupported types must raise TypeError. The can_mutate flag is the expected defense against this, but if an unsupported type reaches the handler, it indicates misconfiguration — crash, never silently corrupt.

### Exploration vs Exploitation

The fundamental mutation tradeoff: too much perturbation destroys good solutions, too little perturbation stagnates in local optima. Different strategies offer different balances:

- **Gaussian/Cauchy** - Local search via noise. Gaussian favors small steps (exploitation), Cauchy allows large jumps (exploration).
- **Differential Evolution** - Population-aware search using differences between members. Balances both by scaling relative distances.
- **Uniform** - Unbiased perturbation across entire range. Maximum exploration, minimal exploitation.

Mutation chance parameters control how frequently mutations occur, providing an additional exploration/exploitation lever independent of perturbation magnitude.

### Population and Ancestry Interpretation

Mutation strategies receive population and ancestry from the orchestrator. Simple mutations ignore these; population-aware mutations interpret them.

**Population parameter:** Alleles at the current tree position, one per genome in rank order. Enables comparative mutations (Differential Evolution samples difference vectors from population allele values directly).

**Ancestry parameter:** `List[Tuple[float, UUID]]` in rank order declaring parent contributions. Enables adaptive mutations based on selection strength. Hard constraint: don't use dead (0.0 probability) members. Flexible interpretation: how to use non-zero probabilities is strategy-specific.

Population-aware strategies must respect upstream ancestry decisions. Ancestry selected parents; mutation uses that information but doesn't re-select. This separation maintains responsibility boundaries.

## GaussianMutation

Fulfills AbstractMutationStrategy's handle_mutating contract. Implements Gaussian noise-based mutation adding normally distributed perturbations to allele values. Noise follows N(0, std) producing small steps around current values. Configurable via std (perturbation magnitude) and mutation_chance (frequency). Effective for local search and refining solutions.

### Constructor

```python
GaussianMutation(default_std=0.1, default_mutation_chance=0.15, use_metalearning=False)
```

Stores mutation parameters as instance fields.

**Parameters:**
- **default_std** (float, default 0.1): Standard deviation for Gaussian noise when metalearning disabled. Controls perturbation magnitude.
- **default_mutation_chance** (float, default 0.15): Probability of mutating each allele when metalearning disabled.
- **use_metalearning** (bool, default False): Enable metalearning. When False, uses constructor defaults. When True, injects evolvable metadata alleles for std and mutation_chance.

**Validation:** If default_std <= 0, raise ValueError("std must be positive"). If default_mutation_chance < 0 or default_mutation_chance > 1, raise ValueError("mutation_chance must be in [0, 1]").

### handle_mutating

Implementation of AbstractMutationStrategy's handle_mutating hook. Reads std and mutation_chance from metadata (with fallback to defaults), applies Gaussian noise with specified probability.

```python
handle_mutating(allele: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** allele (flattened, metadata contains raw values). Ignores allele_population and ancestry.

**Returns:** New allele with Gaussian noise applied (if mutation triggered), or unchanged allele (if not triggered).

**Algorithm:**

1. Read std = allele.metadata.get("std", self.default_std)
2. Read mutation_chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)
3. Generate random uniform value r in [0, 1]
4. If r > mutation_chance:
   - Return allele unchanged
5. Generate Gaussian noise: noise = N(0, std)
6. Compute new_value = allele.value + noise
7. Return allele.with_value(new_value)

**Type-specific handling:**
- FloatAllele: new_value = value + noise (linear space)
- IntAllele: new_value = raw_value + noise (mutate underlying float, not rounded int)
- LogFloatAllele: new_value = value * exp(noise) (multiplicative in log space)

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor defaults for all alleles.

**When use_metalearning=True:** handle_setup injects evolvable metadata alleles. Both std and mutation_chance become continuous evolvable parameters adapting under selection pressure.

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["std"] = GaussianStd allele
- Injects: metadata["mutation_chance"] = GaussianMutationChance allele
- Returns: allele with injected metadata

**GaussianStd allele type:**
- Extends: FloatAllele (continuous)
- Constructor: `GaussianStd(base_std: float)`
- Intrinsic domain: `{"min": 0.01 * base_std, "max": 10.0 * base_std}` — fixed at init, preserved through with_overrides
- Flags: can_mutate=True, can_crossbreed=True
- Purpose: Evolvable standard deviation

**GaussianMutationChance allele type:**
- Extends: FloatAllele (continuous)
- Constructor: `GaussianMutationChance(value: float)`
- Intrinsic domain: `{"min": 0.1, "max": 0.5}`
- Flags: can_mutate=True, can_crossbreed=True
- Purpose: Evolvable mutation frequency

### Contracts

- Input: allele with metadata (flattened), population, ancestry
- Output: new allele (mutated or unchanged)
- Metadata reading: uses .get(key, default) pattern (works with or without metalearning)
- Supports FloatAllele, IntAllele, LogFloatAllele (continuous types)
- Population and ancestry parameters ignored (simple local mutation)
- Mutation stochastic: controlled by mutation_chance parameter

### When to Use

Use GaussianMutation when:
- Hyperparameters are continuous (FloatAllele, IntAllele, LogFloatAllele)
- Want local search (small perturbations refining solutions)
- Population has converged and needs gentle exploration
- Want simple, well-understood baseline behavior

Avoid when:
- Stuck in local optima (use CauchyMutation for occasional large jumps)
- Hyperparameters are discrete (use UniformMutation)
- Need population-aware adaptation (use DifferentialEvolution)

## CauchyMutation

Fulfills AbstractMutationStrategy's handle_mutating contract. Implements heavy-tailed Cauchy noise-based mutation adding perturbations with occasional large jumps. Similar to Gaussian but with infinite variance - most mutations are small, rare outliers enable exploration. Effective for escaping local optima when population has converged prematurely.

### Constructor

```python
CauchyMutation(default_scale=0.1, default_mutation_chance=0.15, use_metalearning=False)
```

Stores mutation parameters as instance fields.

**Parameters:**
- **default_scale** (float, default 0.1): Scale parameter for Cauchy distribution when metalearning disabled. Controls perturbation magnitude.
- **default_mutation_chance** (float, default 0.15): Probability of mutating each allele when metalearning disabled.
- **use_metalearning** (bool, default False): Enable metalearning. When False, uses constructor defaults. When True, injects evolvable metadata alleles for scale and mutation_chance.

**Validation:** If default_scale <= 0, raise ValueError("scale must be positive"). If default_mutation_chance < 0 or default_mutation_chance > 1, raise ValueError("mutation_chance must be in [0, 1]").

### handle_mutating

Implementation of AbstractMutationStrategy's handle_mutating hook. Reads scale and mutation_chance from metadata (with fallback to defaults), applies Cauchy noise with specified probability.

```python
handle_mutating(allele: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** allele (flattened, metadata contains raw values). Ignores allele_population and ancestry.

**Returns:** New allele with Cauchy noise applied (if mutation triggered), or unchanged allele.

**Algorithm:**

1. Read scale = allele.metadata.get("scale", self.default_scale)
2. Read mutation_chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)
3. Generate random uniform value r in [0, 1]
4. If r > mutation_chance:
   - Return allele unchanged
5. Generate Cauchy noise: noise = Cauchy(0, scale)
6. Compute new_value = allele.value + noise
7. Return allele.with_value(new_value)

**Type-specific handling:**
- FloatAllele: new_value = value + noise (linear space)
- IntAllele: new_value = raw_value + noise (mutate underlying float)
- LogFloatAllele: new_value = value * exp(noise) (multiplicative in log space)

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor defaults for all alleles.

**When use_metalearning=True:** handle_setup injects evolvable metadata alleles. Both scale and mutation_chance become continuous evolvable parameters.

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["scale"] = CauchyScale allele
- Injects: metadata["mutation_chance"] = CauchyMutationChance allele
- Returns: allele with injected metadata

**CauchyScale allele type:**
- Extends: FloatAllele (continuous)
- Constructor: `CauchyScale(base_scale: float)`
- Intrinsic domain: `{"min": 0.01 * base_scale, "max": 10.0 * base_scale}` — fixed at init, preserved through with_overrides
- Flags: can_mutate=True, can_crossbreed=True
- Purpose: Evolvable scale parameter

**CauchyMutationChance allele type:**
- Extends: FloatAllele (continuous)
- Constructor: `CauchyMutationChance(value: float)`
- Intrinsic domain: `{"min": 0.1, "max": 0.5}`
- Flags: can_mutate=True, can_crossbreed=True
- Purpose: Evolvable mutation frequency

### Contracts

- Input: allele with metadata (flattened), population, ancestry
- Output: new allele (mutated or unchanged)
- Metadata reading: uses .get(key, default) pattern (works with or without metalearning)
- Supports FloatAllele, IntAllele, LogFloatAllele (continuous types)
- Population and ancestry parameters ignored (simple local mutation)
- Mutation stochastic: controlled by mutation_chance parameter
- Heavy tails: occasional large jumps enable exploration

### When to Use

Use CauchyMutation when:
- Population has converged to local optimum (need escape mechanism)
- Want occasional large jumps to explore distant regions
- Hyperparameters have multiple local optima
- Gaussian mutation stagnating

Avoid when:
- Training is unstable (large jumps can be destructive)
- GaussianMutation working well (simpler is better)
- Population maintaining sufficient diversity (Gaussian's gentler exploration is adequate)

## DifferentialEvolution

Fulfills AbstractMutationStrategy's handle_mutating contract. Implements population-aware mutation using scaled differences between population members. Instead of random noise, perturbations are computed from other genomes' values. Efficient for continuous optimization - typically 2-5x fewer evaluations than Gaussian. Architectural adaptation: respects ancestry by filtering to live members (ancestry probability > 0.0); the current allele serves as the base, and only two difference vectors are sampled from live population.

### Constructor

```python
DifferentialEvolution(default_F=0.8, default_sampling_mode="random", use_metalearning=False)
```

Stores mutation parameters as instance fields.

**Parameters:**
- **default_F** (float, default 0.8): Scale factor for difference vectors when metalearning disabled. Typical range [0.5, 1.0].
- **default_sampling_mode** (str, default "random"): Sampling mode for selecting difference vectors. Options: "random" (uniform from live population) or "weighted" (weighted by ancestry probabilities). Remains constant (not evolvable).
- **use_metalearning** (bool, default False): Enable metalearning. When False, uses constructor defaults. When True, injects evolvable F allele. sampling_mode remains constant (discrete parameter).

**Validation:** If default_F <= 0, raise ValueError("F must be positive"). If default_sampling_mode not in ["random", "weighted"], raise ValueError("sampling_mode must be 'random' or 'weighted'").

### handle_mutating

Implementation of AbstractMutationStrategy's handle_mutating hook. Identifies live population members from ancestry, samples base and difference vectors, computes perturbation from scaled difference.

```python
handle_mutating(allele: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** allele (flattened, metadata contains raw values). Uses allele_population and ancestry.

**Returns:** New allele with differential evolution perturbation applied.

**Algorithm:**

1. Read F = allele.metadata.get("F", self.default_F)
2. Read sampling_mode = allele.metadata.get("sampling_mode", self.default_sampling_mode)
3. Identify live indices: live_indices = [i for i, (prob, _) in enumerate(ancestry) if prob > 0.0]
4. If len(live_indices) < 3:
   - Raise ValueError("DifferentialEvolution requires at least 3 live population members")
5. Extract live_values from allele_population at live_indices (IntAllele uses raw_value; others use value)
6. Sample (val1, val2) from live_values without replacement:
   - If sampling_mode == "random": _choose_two(live_values) → (val1, val2)
   - If sampling_mode == "weighted": _weighted_choose_two(live_values, live_weights) → (val1, val2)
7. Compute new_value = allele.value + F * (val1 - val2)
8. Return allele.with_value(new_value)

**Type-specific handling:**
- FloatAllele: new_value = allele.value + F * (val1 - val2) (linear space)
- IntAllele: new_value = allele.raw_value + F * (val1 - val2) (live_values uses raw_value)
- LogFloatAllele: new_value = allele.value * (val1 / val2) ** F (multiplicative in log space)

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor defaults for all alleles.

**When use_metalearning=True:** handle_setup injects evolvable F allele. sampling_mode remains constant (discrete choice not suitable for evolution).

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["F"] = DifferentialEvolutionF allele
- Returns: allele with injected metadata

**DifferentialEvolutionF allele type:**
- Extends: FloatAllele (continuous)
- Constructor: `DifferentialEvolutionF(base_F: float)`
- Intrinsic domain: `{"min": 0.5, "max": 2.0}`
- Flags: can_mutate=True, can_crossbreed=True
- Purpose: Evolvable scale factor

### Contracts

- Input: allele with metadata (flattened), population, ancestry
- Output: new allele with DE perturbation
- Metadata reading: uses .get(key, default) pattern (works with or without metalearning)
- Supports FloatAllele, IntAllele, LogFloatAllele (continuous types)
- Population-aware: uses ancestry to identify live members (probability > 0.0)
- Constraint: requires >= 3 live population members (raises ValueError otherwise)
- Sampling without replacement: diff1, diff2 sampled without replacement from live values

### When to Use

Use DifferentialEvolution when:
- Hyperparameters are continuous (FloatAllele, IntAllele, LogFloatAllele)
- Population size adequate (>= 4 members, preferably more for diversity)
- Want sample-efficient optimization (fewer evaluations than Gaussian)
- Population provides useful gradient information (differences encode search directions)

Avoid when:
- Population very small (< 4 members, insufficient diversity)
- Hyperparameters discrete (difference operations meaningless)
- Initial generations (population needs time to diversify first)

## UniformMutation

Fulfills AbstractMutationStrategy's handle_mutating contract. Implements uniform sampling mutation replacing allele values with random samples from domain. Unbiased maximum exploration with no exploitation. Entire domain reachable with equal probability. Useful for discrete/categorical parameters or breaking out of convergence.

### Constructor

```python
UniformMutation(default_mutation_chance=0.1, use_metalearning=False)
```

Stores mutation parameter as instance field.

**Parameters:**
- **default_mutation_chance** (float, default 0.1): Probability of mutating each allele when metalearning disabled. Lower than Gaussian (0.15) since uniform perturbations are more disruptive.
- **use_metalearning** (bool, default False): Enable metalearning. When False, uses constructor default. When True, injects evolvable mutation_chance allele.

**Validation:** If default_mutation_chance < 0 or default_mutation_chance > 1, raise ValueError("mutation_chance must be in [0, 1]").

### handle_mutating

Implementation of AbstractMutationStrategy's handle_mutating hook. Reads mutation_chance from metadata (with fallback to default), samples uniformly from allele domain with specified probability.

```python
handle_mutating(allele: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** allele (flattened, metadata contains raw values). Ignores allele_population and ancestry.

**Returns:** New allele with uniformly sampled value (if mutation triggered), or unchanged allele.

**Algorithm:**

1. Read mutation_chance = allele.metadata.get("mutation_chance", self.default_mutation_chance)
2. Generate random uniform value r in [0, 1]
3. If r > mutation_chance:
   - Return allele unchanged
4. Sample new_value uniformly from allele.domain:
   - FloatAllele: uniform in [domain["min"], domain["max"]]
   - IntAllele: uniform in [domain["min"], domain["max"]], rounded
   - LogFloatAllele: uniform in log space [log(domain["min"]), log(domain["max"])], then exp
   - BoolAllele: uniform from {True, False}
   - StringAllele: uniform from domain set
5. Return allele.with_value(new_value)

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor default for all alleles.

**When use_metalearning=True:** handle_setup injects evolvable mutation_chance allele. No magnitude parameter (uniform samples entire domain).

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["mutation_chance"] = UniformMutationChance allele
- Returns: allele with injected metadata

**UniformMutationChance allele type:**
- Extends: FloatAllele (continuous)
- Constructor: `UniformMutationChance(value: float)`
- Intrinsic domain: `{"min": 0.01, "max": 0.3}`
- Flags: can_mutate=True, can_crossbreed=True
- Purpose: Evolvable mutation frequency

### Contracts

- Input: allele with metadata (flattened), population, ancestry
- Output: new allele (uniformly sampled or unchanged)
- Metadata reading: uses .get(key, default) pattern (works with or without metalearning)
- Supports all allele types (FloatAllele, IntAllele, LogFloatAllele, BoolAllele, StringAllele)
- Population and ancestry parameters ignored (simple local mutation)
- Mutation stochastic: controlled by mutation_chance parameter
- Maximum exploration: entire domain reachable with equal probability

### When to Use

Use UniformMutation when:
- Hyperparameters are discrete/categorical (BoolAllele, StringAllele)
- Need to break out of total convergence (inject maximum diversity)
- Want unbiased exploration across entire domain
- Exploring early in evolution

Avoid when:
- Hyperparameters continuous and smooth (GaussianMutation gentler)
- Population hasn't converged yet (disruption without benefit)
- Training unstable (large random jumps destructive)

## Guidelines

### Choosing Strategies

**Default recommendation:** Start with Gaussian. It's well-understood, effective for continuous hyperparameters, and provides good exploitation/exploration balance.

**When population converges:** Switch to Cauchy (occasional large jumps) or Differential Evolution (population-aware perturbations).

**For sample efficiency:** Use Differential Evolution. It typically requires 2-5x fewer evaluations on continuous problems.

**For categorical/discrete:** Use Uniform. It's the only strategy that handles discrete domains naturally.

### Combining Strategies

The strategy system supports full composability - any ancestry + any crossbreeding + any mutation. Some combinations are more effective:

- **Gaussian + weak selection pressure** (small tournament size): Population converges slowly, Gaussian refines gradually. Good for stable training.
- **Differential Evolution + strong selection pressure** (large tournament size): Population converges quickly, DE uses population gradient. Sample-efficient but can converge prematurely.
- **Cauchy + EliteBreeds**: Elite tier maintains best solutions, Cauchy enables diverse tier to explore aggressively.

No combination is invalid - all work together. Effectiveness depends on problem characteristics.

### Metalearning Recommendations

Enable metalearning when:
- Evolution runs for many generations (> 50-100 rounds)
- Hyperparameter schedules are important (std should vary over time)
- Computational budget allows (metalearning adds overhead)

Disable metalearning when:
- Short evolution runs (< 20 rounds, not enough time to adapt)
- Hyperparameters are known to be stable
- Debugging (fewer moving parts, simpler behavior)

### Parameter Tuning

**Mutation chance:** Controls frequency. Start at 0.15 (Gaussian/Cauchy) or 0.1 (Uniform). Increase if population stagnates, decrease if training is unstable.

**Magnitude (std/scale/F):** Controls perturbation size. Start at 0.1 (Gaussian/Cauchy) or 0.8 (DE). Increase for more exploration, decrease for more exploitation.

**Sampling mode (DE only):** Start with "random". Use "weighted" if ancestry provides strong signal and you want exploitation.

Tune based on observed behavior: if population converges too quickly (premature convergence), increase exploration (higher magnitude, higher mutation chance, or switch to Cauchy/Uniform). If population doesn't converge (too much noise), increase exploitation (lower magnitude, lower mutation chance, or switch to Gaussian).
