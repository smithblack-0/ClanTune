# Crossbreeding Strategies

## Overview

Crossbreeding strategies synthesize offspring genome values from parent genomes based on ancestry. This is the recombination phase of evolution - combining genetic material from selected parents to produce offspring. Crossbreeding strategies implement the interpret half of the declare-interpret paradigm: ancestry strategies declare which parents contribute, crossbreeding strategies interpret those declarations to synthesize new allele values.

The crossbreeding contract receives ancestry from the ancestry strategy and uses it to guide value synthesis. Different strategies interpret ancestry probabilities differently: weighted combinations, dominant selection, stochastic sampling, or specialized operators. The result is an offspring genome with allele values derived from parent values, ready for mutation.

Crossbreeding strategies control exploitation vs exploration at the synthesis level. Conservative strategies (WeightedAverage) blend parent values smoothly, preserving characteristics. Aggressive strategies (StochasticCrossover) sample discontinuously, enabling larger jumps. The choice determines how parent fitness translates into offspring characteristics.

### Allele-Level Synthesis

Crossbreeding operates on individual alleles via the handle_crossbreeding hook. The abstract class handles orchestration: filtering crossbreedable alleles (can_crossbreed=True), delegating to genome utilities, managing ancestry context. Concrete strategies implement handle_crossbreeding: receive template allele (from offspring genome position), source alleles (from parent genomes), and ancestry weights; return synthesized allele.

**Handler contract:**
- **template**: Allele from my_genome with resolved metadata (nested alleles already processed, flattened to raw values)
- **sources**: List of alleles from population (in rank order, flattened)
- **ancestry**: `List[Tuple[float, UUID]]` declaring parent contribution probabilities
- **Returns**: New allele via `template.with_value(new_value)`

Template provides structure and defaults (domain, flags, metadata schema). Sources provide values to combine. Ancestry provides weights for combination. Handler uses ancestry to decide how to synthesize new value from source values.

### Ancestry Interpretation Patterns

Different strategies interpret ancestry differently:

- **Weighted combination (WeightedAverage):** Use probabilities as linear weights: `new_value = sum(prob_i * source_i.value)`
- **Dominant selection (DominantParent):** Pick parent with highest probability, use its value exclusively
- **Pairwise operator (SBX):** Use two parents (typically two highest probabilities), apply crossover operator
- **Stochastic sampling (StochasticCrossover):** Sample parent per allele using probabilities as sampling weights

All strategies respect the 0.0 = excluded constraint: parents with zero probability don't contribute. Non-zero probability interpretation is strategy-specific.

### Exploitation vs Exploration

Crossbreeding strategies vary in how much they preserve vs disrupt parent characteristics:

- **High exploitation (WeightedAverage, DominantParent):** Smooth blending or exact copying. Offspring close to parents. Preserves good solutions.
- **Moderate (SBX):** Controlled randomness. Offspring near parents but with variation. Balances preservation and exploration.
- **High exploration (StochasticCrossover):** Discontinuous sampling. Offspring can be far from parents. Enables novel combinations.

This complements mutation's exploration. Mutation perturbs values locally. Crossbreeding combines values globally. Together they span the search space.

### Type Support

Crossbreeding strategies must specify which allele types they support. Type compatibility determines whether strategies can blend values (averaging) or must select values (sampling).

**Type support by strategy:**

**WeightedAverage** - continuous types only (FloatAllele, IntAllele, LogFloatAllele). Computes weighted average of source values. Cannot average discrete types (BoolAllele, StringAllele).

**DominantParent** - all types. Selects value from single parent, no blending required.

**SBX (Simulated Binary Crossover)** - continuous types only (FloatAllele, IntAllele, LogFloatAllele). Assumes numeric bounds and arithmetic operations. Cannot operate on discrete types.

**StochasticCrossover** - all types. Samples parent per allele, no blending required.

**Contract:** Strategies operating on unsupported types with can_crossbreed=True should skip those alleles silently (filtering typically handled by predicate or strategy logic). For mixed genomes (continuous + discrete hyperparameters), use DominantParent or StochasticCrossover which support all types.

## WeightedAverage

Linear combination of parent values weighted by ancestry probabilities. Offspring value is weighted average of source values. Simple, smooth, preserves characteristics proportionally. Baseline crossbreeding strategy.

### Algorithm

For each crossbreedable allele:
1. Extract ancestry probabilities from ancestry list
2. Compute weighted average: `new_value = sum(prob_i * source_i.value for each parent)`
3. Return `template.with_value(new_value)`

Only parents with non-zero probability contribute. Probabilities act as linear weights.

**Behavior (ancestry = [(0.6, uuid_0), (0.4, uuid_1), (0.0, uuid_2)], source values [10.0, 20.0, 30.0]):**
```
new_value = 0.6 * 10.0 + 0.4 * 20.0 + 0.0 * 30.0
         = 6.0 + 8.0 + 0.0
         = 14.0
```

Offspring value is 60% of parent_0, 40% of parent_1, 0% of parent_2.

### When to Use

Use WeightedAverage when:
- Want smooth blending of parent characteristics
- Ancestry probabilities should directly translate to contribution strength
- Hyperparameters are continuous and averaging makes sense
- Want predictable, stable crossbreeding (baseline behavior)

Avoid when:
- Hyperparameters are discrete/categorical (averaging doesn't make sense)
- Want to preserve exact parent values (use DominantParent)
- Need stochastic variation (use StochasticCrossover)

## DominantParent

Select value from parent with highest ancestry probability. No blending - offspring inherits dominant parent's value exactly. Fast, simple, preserves existing values.

### Algorithm

For each crossbreedable allele:
1. Find parent with maximum ancestry probability
2. Use that parent's value: `new_value = sources[dominant_idx].value`
3. Return `template.with_value(new_value)`

If multiple parents tie for highest probability, selects first (lowest index).

**Behavior (ancestry = [(0.1, uuid_0), (0.7, uuid_1), (0.2, uuid_2)], source values [10.0, 20.0, 30.0]):**
```
max_prob = 0.7 at index 1
new_value = sources[1].value = 20.0
```

Offspring inherits parent_1's value exactly.

### When to Use

Use DominantParent when:
- Want to preserve exact parent values (no blending)
- Ancestry clearly identifies single best parent (high-probability winner)
- Crossbreeding with EliteBreeds (1.0 self-probability means exact self-copy)
- Want fast crossbreeding (no arithmetic, just selection)

Avoid when:
- Want to blend characteristics from multiple parents (use WeightedAverage)
- Ancestry assigns similar probabilities to multiple parents (dominant selection arbitrary)
- Need randomness or exploration (use StochasticCrossover)

### Interaction with EliteBreeds

DominantParent pairs naturally with EliteBreeds ancestry:
- **Thrive/survive tiers:** ancestry = [(1.0, self.uuid), (0.0, others)] → DominantParent selects self.value → exact self-reproduction
- **Die tier:** ancestry distributes among thrive tier (e.g., [(0.5, uuid_0), (0.5, uuid_1), ...]) → DominantParent picks uuid_0 or uuid_1 deterministically

This preserves elite genomes exactly while replacing die tier with thrive tier offspring.

## SimulatedBinaryCrossover (SBX)

Mimics single-point crossover for continuous values. Uses two parents and a distribution parameter (eta) to generate offspring near parent values with controlled spread. Common in NSGA-II and other evolutionary algorithms. Good for bounded continuous values.

### Algorithm

For each crossbreedable allele:
1. Select two parents from ancestry (typically two highest probabilities)
2. Apply SBX operator to parent values p1 and p2:
   - Generate random beta from distribution controlled by eta
   - Compute: `c1 = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)`
   - Compute: `c2 = 0.5 * ((1 - beta) * p1 + (1 + beta) * p2)`
   - Randomly select c1 or c2 as new_value
3. Return `template.with_value(new_value)`

**Distribution parameter eta:** Controls spread of offspring values around parents.
- High eta (e.g., 20): Offspring close to parents (exploitation)
- Low eta (e.g., 2): Offspring spread wider (exploration)
- Standard value: eta=15

**Parent selection:** Use two parents with highest non-zero probabilities. If fewer than two parents have non-zero probability, raise ValueError("SBX requires at least two parents with non-zero probability").

### Constructor

```python
SimulatedBinaryCrossover(default_eta=15, use_metalearning=False)
```

**Parameters:**
- **default_eta** (float, default 15): Distribution index used when metalearning disabled. Controls offspring spread. Typical range: [2, 30].
- **use_metalearning** (bool, default False): Enable metalearning for eta parameter.

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor default.

**When use_metalearning=True:** handle_setup injects evolvable eta allele, enabling adaptive exploitation/exploration balance.

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["eta"] = SBXEta allele (see below)
- Returns: allele with injected metadata

**SBXEta allele type:**
- Extends: FloatAllele
- Constructor: `SBXEta(base_eta: float, can_change: bool = True)`
- Intrinsic domain: `{"min": 2.0, "max": 30.0}` (standard SBX range)
- Flags: can_mutate=can_change, can_crossbreed=can_change
- Purpose: Evolvable offspring spread (low = exploration, high = exploitation)

### When to Use

Use SBX when:
- Hyperparameters are continuous and bounded
- Want offspring near parents but with controlled variation
- Using multi-objective optimization (NSGA-II heritage)
- Want established, well-studied crossover operator

Avoid when:
- Hyperparameters are unbounded (SBX assumes bounds)
- Ancestry assigns probability to many parents (SBX uses two)
- Want simple blending (use WeightedAverage)

## StochasticCrossover

Random per-allele parent selection using ancestry probabilities as sampling weights. Each allele independently samples a parent, uses that parent's value. Introduces stochastic variation while respecting ancestry weights. Enables exploration via discontinuous inheritance.

### Algorithm

For each crossbreedable allele:
1. Sample parent index from ancestry probabilities (weighted random choice)
2. Use sampled parent's value: `new_value = sources[sampled_idx].value`
3. Return `template.with_value(new_value)`

Parents with higher probabilities are more likely to be selected, but sampling is stochastic. Each allele gets an independent sample, so offspring can inherit from different parents at different loci.

**Behavior (ancestry = [(0.2, uuid_0), (0.5, uuid_1), (0.3, uuid_2)], three alleles):**
```
Allele "lr": sample using [0.2, 0.5, 0.3] → select index 1 → use parent_1's lr value
Allele "momentum": sample using [0.2, 0.5, 0.3] → select index 2 → use parent_2's momentum value
Allele "weight_decay": sample using [0.2, 0.5, 0.3] → select index 1 → use parent_1's weight_decay value
```

Offspring inherits lr from parent_1, momentum from parent_2, weight_decay from parent_1. Mix-and-match inheritance.

### When to Use

Use Stochastic when:
- Want per-allele variation (different alleles from different parents)
- Ancestry weights should influence but not determine inheritance
- Need exploration via discontinuous combinations
- Hyperparameters have some independence (mixed inheritance makes sense)

Avoid when:
- Want deterministic inheritance (use DominantParent)
- Want smooth blending (use WeightedAverage)
- Hyperparameters are tightly coupled (mixed inheritance breaks dependencies)

### Relationship to Genetic Algorithms

StochasticCrossover resembles uniform crossover from classical genetic algorithms: each gene (allele) independently chooses a parent. The difference: classical uniform crossover samples uniformly (50/50), StochasticCrossover samples weighted by ancestry (respects fitness-based selection).

This enables fitness-guided stochastic recombination: better parents more likely to contribute, but randomness enables exploration.

## Guidelines

### Choosing Strategies

**Default recommendation:** Start with WeightedAverage. Smooth blending, predictable, works for continuous hyperparameters.

**For elite preservation:** Use DominantParent with EliteBreeds ancestry. Preserves best genomes exactly.

**For controlled exploration:** Use SBX. Offspring near parents but with variation.

**For maximum recombination:** Use StochasticCrossover. Mix-and-match per-allele inheritance.

### Combining with Ancestry and Mutation

Crossbreeding strategies compose with all ancestry and mutation strategies. Some combinations are particularly effective:

- **Tournament + WeightedAverage + Gaussian:** Balanced composition. Moderate selection, smooth blending, local mutation. General-purpose.
- **EliteBreeds + DominantParent + Cauchy:** Elite preservation. Thrive tier reproduced exactly, die tier gets exploratory mutation. Stable top, exploratory bottom.
- **Rank + SBX + DifferentialEvolution:** Smooth selection gradient, controlled crossover, population-aware mutation. Good for continuous optimization.
- **Boltzmann + StochasticCrossover + Uniform:** Adaptive pressure, stochastic recombination, aggressive mutation. High exploration, anneals over time.

No combination is invalid. Effectiveness depends on problem characteristics.

### Discrete vs Continuous Hyperparameters

**For continuous hyperparameters:**
- WeightedAverage: natural (averaging makes sense)
- SBX: natural (designed for continuous values)
- DominantParent: works (selects one value)
- StochasticCrossover: works (samples one value)

**For discrete/categorical hyperparameters:**
- WeightedAverage: problematic (averaging "adam" and "sgd" is meaningless)
- SBX: problematic (assumes numeric values and bounds)
- DominantParent: natural (selects one category)
- StochasticCrossover: natural (samples one category)

For mixed populations (continuous + discrete hyperparameters), consider using DominantParent or StochasticCrossover as they handle both naturally. Alternatively, use WeightedAverage with domain validation to skip non-numeric types.

### Exploitation vs Exploration Tuning

**High exploitation (preserve parent characteristics):**
- WeightedAverage (smooth blending)
- DominantParent (exact copying)
- SBX with high eta (offspring close to parents)

**High exploration (enable novel combinations):**
- StochasticCrossover (discontinuous sampling)
- SBX with low eta (offspring spread wider)

**Balancing:** Crossbreeding controls global recombination, mutation controls local perturbation. Use exploitative crossbreeding + exploratory mutation for stable search with local variation. Use exploratory crossbreeding + conservative mutation for global search with controlled steps.

### Parameter Tuning

**SBX eta:** Start at 15. Increase to 20-30 for more exploitation (offspring closer to parents). Decrease to 5-10 for more exploration (wider spread).

**StochasticCrossover:** No parameters to tune. Exploration controlled by ancestry probabilities (sharper distribution = less randomness, flatter distribution = more randomness).

**WeightedAverage / DominantParent:** No parameters to tune. Behavior fully determined by ancestry.

Tune based on observed behavior: if offspring too similar to parents (insufficient variation) → increase exploration (SBX lower eta, or switch to Stochastic). If offspring too different from parents (losing good characteristics) → increase exploitation (SBX higher eta, or switch to Weighted/Dominant).
