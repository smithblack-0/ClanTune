# Mutation Strategies

## Overview

Mutation strategies modify genome alleles to introduce variation, driving exploration of the hyperparameter space. Mutations occur after crossbreeding in the evolution cycle, perturbing offspring values to escape local optima and discover novel configurations. The mutation contract balances exploitation (preserving good solutions) with exploration (discovering better ones).

Mutation strategies implement AbstractMutationStrategy's hook-based pattern. The abstract class handles orchestration (filtering mutable alleles, delegating to genome utilities), while concrete strategies provide decision logic via handle_mutating. Strategies receive population and ancestry context to support population-aware algorithms, though simple mutations ignore these parameters.

**Implementation note:** Handlers receive flattened alleles where metadata contains raw values, not nested alleles. When reading `allele.metadata.get("std", default)`, if std was injected as a GaussianStd allele during setup, metadata returns its value (a float), not the allele object. Tree utilities handle flattening/unflattening; handlers work with raw values.

### Exploration vs Exploitation

The fundamental mutation tradeoff: too much perturbation destroys good solutions, too little perturbation stagnates in local optima. Different strategies offer different balances:

- **Gaussian/Cauchy** - Local search via noise. Gaussian favors small steps (exploitation), Cauchy allows large jumps (exploration).
- **Differential Evolution** - Population-aware search using differences between members. Balances both by scaling relative distances.
- **Uniform** - Unbiased perturbation across entire range. Maximum exploration, minimal exploitation.

Mutation chance parameters control how frequently mutations occur, providing an additional exploration/exploitation lever independent of perturbation magnitude.

### Population and Ancestry Interpretation

Mutation strategies receive population and ancestry from the orchestrator. Simple mutations ignore these; population-aware mutations interpret them.

**Population parameter:** All genomes in rank order. Enables comparative mutations (Differential Evolution samples difference vectors from population).

**Ancestry parameter:** `List[Tuple[float, UUID]]` in rank order declaring parent contributions. Enables adaptive mutations based on selection strength. Hard constraint: don't use dead (0.0 probability) members. Flexible interpretation: how to use non-zero probabilities is strategy-specific.

Population-aware strategies must respect upstream ancestry decisions. Ancestry selected parents; mutation uses that information but doesn't re-select. This separation maintains responsibility boundaries.

## GaussianMutation

Baseline mutation strategy adding Gaussian noise to allele values. Simple, well-understood, effective for local search. Noise follows normal distribution N(0, std), producing small perturbations around current values.

### Algorithm

For each mutable allele:
1. Read std and mutation_chance from metadata (fall back to defaults)
2. With probability `mutation_chance`, add noise: `new_value = value + N(0, std)`
3. Return allele.with_value(new_value) (domain clamping handled by constructor)

### Parameters

- **std** (float, default 0.1): Standard deviation of Gaussian noise. Controls perturbation magnitude. Larger std increases exploration, smaller increases exploitation.
- **mutation_chance** (float, default 0.15): Probability of mutating each allele. Independent control over mutation frequency.

### Metalearning

The std parameter can evolve. Strategies using metalearning inject a GaussianStd allele into metadata during setup. This allele participates in mutation and crossbreeding, adapting std over generations. Mutation chance is typically constant (not evolvable) to maintain stable mutation rates.

**Example setup:**
```python
def handle_setup(self, allele):
    return allele.with_metadata(
        std=GaussianStd(self.default_std, can_change=True),
        mutation_chance=self.default_mutation_chance
    )
```

The GaussianStd subclass extends FloatAllele with appropriate domain (e.g., 0.1×base to 5.0×base) and can_mutate/can_crossbreed flags enabled.

### When to Use

Use Gaussian when:
- Hyperparameters are continuous and smooth
- Local search is desired (refining good solutions)
- Population has converged and needs gentle perturbation
- You want well-understood baseline behavior

Avoid when:
- Stuck in local optima (Cauchy's heavy tails may help)
- Discrete or categorical parameters (use Uniform)
- Need population-aware adaptation (use Differential Evolution)

## CauchyMutation

Heavy-tailed mutation using Cauchy distribution. Similar to Gaussian but with fatter tails, producing occasional large jumps that escape local optima. Effective when population has converged prematurely.

### Algorithm

Identical to Gaussian except noise distribution: `new_value = value + Cauchy(0, scale)`.

Cauchy distribution has infinite variance - rare but large perturbations occur. Most mutations are small (like Gaussian), but outliers enable exploration.

### Parameters

- **scale** (float, default 0.1): Scale parameter of Cauchy distribution. Analogous to Gaussian std but produces heavier tails.
- **mutation_chance** (float, default 0.15): Probability of mutating each allele.

### Metalearning

Scale can be evolvable, similar to Gaussian std. Define CauchyScale subclass with appropriate domain bounds.

### When to Use

Use Cauchy when:
- Population has converged to local optimum
- Need occasional large jumps to escape plateaus
- Hyperparameters have multiple local optima

Avoid when:
- Training is unstable (large jumps can be destructive)
- Gaussian is working well (simpler is better)
- Early in evolution (population needs time to converge first)

## DifferentialEvolution

Population-aware mutation using differences between population members. Instead of random noise, perturbations are scaled differences from other genomes. Efficient and effective for continuous optimization - typically 2-5x fewer evaluations than Gaussian on continuous problems.

### Architectural Adaptation

Standard Differential Evolution (DE/rand/1) randomly selects base vector and difference vectors from the entire population, controlling selection. Our architecture separates selection (ancestry) from mutation. DifferentialEvolution receives population from ancestry strategy and respects it.

**Key adaptation:** Only use live population members. Ancestry marks dead members with 0.0 probability. Differential Evolution samples from non-zero members only, respecting upstream selection while implementing the DE algorithm.

### Algorithm

For each mutable allele (received via handle_mutating hook):
1. Read F (scale factor) and sampling_mode from metadata (fall back to defaults)
2. Identify live genomes: those where ancestry probability > 0.0
3. Extract corresponding alleles from live genomes
4. Sample base allele and two difference alleles from live alleles (respecting sampling_mode)
5. Compute: `new_value = base.value + F * (allele1.value - allele2.value)`
6. Return allele.with_value(new_value)

The handler operates on alleles but receives the full population (genomes) and ancestry. Filtering to live members means: only use alleles from genomes where the corresponding ancestry entry has probability > 0.0.

### Sampling Modes

**random** (default): Sample uniformly from live population. Ignores ancestry probabilities beyond the 0.0 = dead constraint.

**weighted**: Sample weighted by ancestry probabilities. Parents with higher contribution probabilities are more likely to be selected for difference vectors.

Sampling mode trades exploration (random) for exploitation (weighted). Random explores broadly across live population. Weighted focuses on high-fitness parents.

### Population and Ancestry Interpretation

DifferentialEvolution demonstrates the ancestry interpretation pattern:

- **Hard constraint:** `ancestry[i][0] == 0.0` means genome i is dead, don't use it
- **Flexible interpretation:** Among live members, how to sample is strategy choice
  - Can sample uniformly (treats all live equally)
  - Can sample weighted (uses selection strength)
  - Implementation can support both modes

This respects responsibility boundaries: ancestry selects parents, mutation decides how to use them for perturbations.

### Parameters

- **F** (float, default 0.8): Scale factor for difference vectors. Controls perturbation magnitude. F ∈ [0.5, 1.0] is typical. Larger F increases exploration.
- **sampling_mode** (str, default "random"): How to sample from live population. Options: "random" (uniform) or "weighted" (by ancestry probabilities).

### Metalearning

F can be evolvable. Define DifferentialEvolutionF subclass extending FloatAllele with domain like {"min": 0.5, "max": 2.0}.

Sampling mode is typically constant (discrete choice, not continuous parameter).

### When to Use

Use Differential Evolution when:
- Hyperparameters are continuous
- Population size is adequate (need enough live members to sample from)
- Want sample-efficient optimization (fewer evaluations than Gaussian)
- Population provides useful gradient information (differences encode search directions)

Avoid when:
- Population is very small (< 4 members may not have enough diversity)
- Hyperparameters are discrete (difference operations don't make sense)
- In initial generations before population diversifies

### Implementation Note

Concrete implementations must handle edge cases:
- If live population has < 3 members, fall back to simpler mutation (or skip)
- Ensure base and difference alleles are distinct (don't sample same member twice)
- Handle out-of-bounds values via domain clamping (allele constructor handles this)

## UniformMutation

Simplest mutation: replace value with random sample from domain. Unbiased, maximum exploration, no exploitation. Useful for categorical parameters or breaking out of convergence.

### Algorithm

For each mutable allele:
1. Read mutation_chance from metadata
2. With probability `mutation_chance`, sample new value uniformly from allele.domain
3. Return allele.with_value(new_value)

For continuous domains (FloatAllele), samples uniformly from [min, max]. For discrete domains (StringAllele), samples uniformly from set.

### Parameters

- **mutation_chance** (float, default 0.1): Probability of mutating each allele. Lower default than Gaussian since uniform perturbations are more disruptive.

No magnitude parameter - entire domain is reachable with equal probability.

### Metalearning

Mutation chance can be evolvable, though typically constant. No magnitude parameter to evolve (uniform is parameter-free).

### When to Use

Use Uniform when:
- Hyperparameters are discrete/categorical (StringAllele)
- Need to break out of total convergence
- Want maximum diversity injection
- Exploring early in evolution

Avoid when:
- Hyperparameters are continuous and smooth (Gaussian is gentler)
- Population has not converged yet (disruption without benefit)
- Training is unstable (large random jumps can be destructive)

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
