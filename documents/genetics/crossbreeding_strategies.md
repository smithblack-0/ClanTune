# Crossbreeding Strategies

## Overview

Crossbreeding strategies synthesize offspring genome values from parent genomes based on ancestry. This is the recombination phase of evolution - combining genetic material from selected parents to produce offspring. Crossbreeding strategies implement the interpret half of the declare-interpret paradigm: ancestry strategies declare which parents contribute, crossbreeding strategies interpret those declarations to synthesize new allele values.

The crossbreeding contract receives ancestry from the ancestry strategy and uses it to guide value synthesis. Different strategies interpret ancestry probabilities differently: weighted combinations, dominant selection, stochastic sampling, or specialized operators. The result is an offspring genome with allele values derived from parent values, ready for mutation.

Crossbreeding strategies control exploitation vs exploration at the synthesis level. Conservative strategies (WeightedAverage) blend parent values smoothly, preserving characteristics. Aggressive strategies (StochasticCrossover) sample discontinuously, enabling larger jumps. The choice determines how parent fitness translates into offspring characteristics.

### Allele-Level Synthesis

Crossbreeding operates on individual alleles via the handle_crossbreeding hook. The abstract class handles orchestration: filtering crossbreedable alleles (can_crossbreed=True), delegating to genome utilities, managing ancestry context. Concrete strategies implement handle_crossbreeding: receive template allele (from offspring genome position), source alleles (from parent genomes), and ancestry weights; return synthesized allele.

**Handler contract:**
- **template**: Allele from my_genome with resolved metadata (nested alleles already processed, flattened to raw values)
- **allele_population**: List of alleles from population (in rank order, flattened)
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

Fulfills AbstractCrossbreedingStrategy's handle_crossbreeding contract. Implements linear combination of parent values weighted by ancestry probabilities. Offspring value is weighted average of source values. Simple, smooth, preserves characteristics proportionally. Baseline crossbreeding strategy.

### Constructor

```python
WeightedAverage()
```

No parameters. Stateless strategy.

### handle_crossbreeding

Implementation of AbstractCrossbreedingStrategy's handle_crossbreeding hook. Computes weighted average of source values using ancestry probabilities as weights.

```python
handle_crossbreeding(template: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** template (allele from my_genome, flattened metadata), allele_population (alleles from population, flattened), ancestry (parent contribution probabilities).

**Returns:** New allele with value set to weighted average of source values.

**Algorithm:**

1. Initialize new_value = 0.0
2. For i in range(len(sources)):
   - prob = ancestry[i][0]
   - new_value += prob * allele_population[i].value
3. Return template.with_value(new_value)

**Type support:** Supports FloatAllele, IntAllele, LogFloatAllele (continuous types). Cannot average discrete types (BoolAllele, StringAllele).

### Contracts

- Input: template, allele_population (same length as ancestry), ancestry
- Output: new allele with averaged value
- Only parents with non-zero probability contribute (prob > 0.0)
- Probabilities act as linear weights
- Type support: continuous only (FloatAllele, IntAllele, LogFloatAllele)
- Stateless: no parameters or state

### When to Use

Use WeightedAverage when:
- Want smooth blending of parent characteristics
- Ancestry probabilities should translate directly to contribution strength
- Hyperparameters are continuous (FloatAllele, IntAllele, LogFloatAllele)
- Want predictable, stable crossbreeding (baseline behavior)

Avoid when:
- Hyperparameters discrete/categorical (use DominantParent or StochasticCrossover)
- Want to preserve exact parent values (use DominantParent)
- Need stochastic variation (use StochasticCrossover)

## DominantParent

Fulfills AbstractCrossbreedingStrategy's handle_crossbreeding contract. Implements dominant parent selection - offspring inherits value from parent with highest ancestry probability. No blending, exact value preservation. Fast, simple, deterministic. Pairs naturally with EliteBreeds (1.0 self-probability → exact self-copy).

### Constructor

```python
DominantParent()
```

No parameters. Stateless strategy.

### handle_crossbreeding

Implementation of AbstractCrossbreedingStrategy's handle_crossbreeding hook. Finds parent with maximum ancestry probability, uses that parent's value.

```python
handle_crossbreeding(template: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** template (allele from my_genome, flattened metadata), allele_population (alleles from population, flattened), ancestry (parent contribution probabilities).

**Returns:** New allele with value from dominant parent (highest probability).

**Algorithm:**

1. Find dominant index: dominant_idx = argmax([ancestry[i][0] for i in range(len(ancestry))])
2. Extract dominant value: new_value = allele_population[dominant_idx].value
3. Return template.with_value(new_value)

**Tie-breaking:** If multiple parents tie for highest probability, selects first (lowest index).

**Type support:** Supports all allele types (FloatAllele, IntAllele, LogFloatAllele, BoolAllele, StringAllele). No blending required.

### Contracts

- Input: template, allele_population (same length as ancestry), ancestry
- Output: new allele with value from dominant parent
- Selection criterion: highest ancestry probability
- Tie-breaking: first occurrence (lowest index)
- Type support: all types (no blending, just selection)
- Stateless: no parameters or state

### When to Use

Use DominantParent when:
- Want to preserve exact parent values (no blending)
- Ancestry clearly identifies dominant parent (high-probability winner)
- Pair with EliteBreeds ancestry (1.0 self-probability → exact self-copy)
- Want fast crossbreeding (no arithmetic, just selection)
- Hyperparameters are discrete (BoolAllele, StringAllele) or continuous

Avoid when:
- Want to blend characteristics from multiple parents (use WeightedAverage)
- Ancestry assigns similar probabilities to multiple parents (dominant selection arbitrary)
- Need stochastic variation (use StochasticCrossover)

## SimulatedBinaryCrossover (SBX)

Fulfills AbstractCrossbreedingStrategy's handle_crossbreeding contract. Implements simulated binary crossover mimicking single-point crossover for continuous values. Uses two parents and distribution parameter eta to generate offspring near parent values with controlled spread. Common in NSGA-II and multi-objective optimization. Good for bounded continuous values.

### Constructor

```python
SimulatedBinaryCrossover(default_eta=15, use_metalearning=False)
```

Stores crossbreeding parameter as instance field.

**Parameters:**
- **default_eta** (float, default 15): Distribution index when metalearning disabled. Controls offspring spread around parents. Typical range [2, 30]. High eta (20+) keeps offspring close (exploitation), low eta (2-5) spreads wider (exploration).
- **use_metalearning** (bool, default False): Enable metalearning. When False, uses constructor default. When True, injects evolvable eta allele.

**Validation:** If default_eta <= 0, raise ValueError("eta must be positive").

**Required pairing:** SBX requires exactly 2 non-zero entries in ancestry. Pair with `TopN(n=2, strategy=...)` to enforce this contract.

### handle_crossbreeding

Implementation of AbstractCrossbreedingStrategy's handle_crossbreeding hook. Selects two parents from ancestry, applies SBX operator to generate offspring value.

```python
handle_crossbreeding(template: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** template (allele from my_genome, flattened metadata), allele_population (alleles from population, flattened), ancestry (parent contribution probabilities).

**Returns:** New allele with SBX-generated value.

**Algorithm:**

1. Read eta = template.metadata.get("eta", self.default_eta)
2. Validate ancestry has exactly 2 non-zero entries:
   - live_indices = [i for i in range(len(ancestry)) if ancestry[i][0] > 0.0]
   - If len(live_indices) != 2: raise ValueError("SBX requires exactly 2 non-zero parents; pair with TopN(n=2, ...)")
   - parent1_idx, parent2_idx = live_indices[0], live_indices[1]
3. Extract parent values: p1 = allele_population[parent1_idx].value, p2 = allele_population[parent2_idx].value
4. Generate random u in [0, 1]
5. Compute beta from polynomial probability distribution:
   - If u <= 0.5: beta = (2 * u) ** (1 / (eta + 1))
   - Else: beta = (1 / (2 * (1 - u))) ** (1 / (eta + 1))
6. Compute offspring values:
   - c1 = 0.5 * ((1 + beta) * p1 + (1 - beta) * p2)
   - c2 = 0.5 * ((1 - beta) * p1 + (1 + beta) * p2)
7. Randomly select c1 or c2 (uniform 50/50): new_value = c1 if random() < 0.5 else c2
8. Return template.with_value(new_value)

**Type support:** Supports FloatAllele, IntAllele, LogFloatAllele (continuous types). Cannot operate on discrete types.

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor default for all alleles.

**When use_metalearning=True:** handle_setup injects evolvable eta allele enabling adaptive exploitation/exploration balance.

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["eta"] = SBXEta allele
- Returns: allele with injected metadata

**SBXEta allele type:**
- Extends: FloatAllele (continuous)
- Constructor: `SBXEta(base_eta: float, can_change: bool = True)`
- Intrinsic domain: `{"min": 2.0, "max": 30.0}`
- Flags: can_mutate=can_change, can_crossbreed=can_change
- Purpose: Evolvable offspring spread

### Contracts

- Input: template, allele_population (same length as ancestry), ancestry
- Output: new allele with SBX-generated value
- Metadata reading: uses .get(key, default) pattern (works with or without metalearning)
- Parent requirement: exactly 2 non-zero entries in ancestry (raises ValueError otherwise); enforce via TopN(n=2, ...)
- Type support: continuous only (FloatAllele, IntAllele, LogFloatAllele)
- Stochastic: random beta generation and c1/c2 selection

### When to Use

Use SimulatedBinaryCrossover when:
- Hyperparameters continuous and bounded (FloatAllele, IntAllele, LogFloatAllele)
- Want offspring near parents with controlled variation
- Using multi-objective optimization (NSGA-II heritage)
- Want established, well-studied crossover operator

Avoid when:
- Hyperparameters unbounded (SBX assumes bounds)
- Ancestry assigns probability to many parents (SBX uses only two)
- Want simple blending (use WeightedAverage)
- Hyperparameters discrete (use DominantParent or StochasticCrossover)

## StochasticCrossover

Fulfills AbstractCrossbreedingStrategy's handle_crossbreeding contract. Implements stochastic per-allele parent selection using ancestry probabilities as sampling weights. Each allele independently samples a parent, uses that parent's value. Introduces stochastic variation while respecting ancestry weights. Enables exploration via discontinuous mix-and-match inheritance. Resembles uniform crossover from genetic algorithms but weighted by fitness.

### Constructor

```python
StochasticCrossover()
```

No parameters. Stateless strategy.

### handle_crossbreeding

Implementation of AbstractCrossbreedingStrategy's handle_crossbreeding hook. Samples parent index weighted by ancestry probabilities, uses sampled parent's value.

```python
handle_crossbreeding(template: AbstractAllele, allele_population: List[AbstractAllele], ancestry: List[Tuple[float, UUID]]) -> AbstractAllele
```

**Receives:** template (allele from my_genome, flattened metadata), allele_population (alleles from population, flattened), ancestry (parent contribution probabilities).

**Returns:** New allele with value from stochastically sampled parent.

**Algorithm:**

1. Extract probabilities: probs = [ancestry[i][0] for i in range(len(ancestry))]
2. Sample parent index using probs as weights: sampled_idx = weighted_random_choice(range(len(allele_population)), weights=probs)
3. Extract sampled value: new_value = allele_population[sampled_idx].value
4. Return template.with_value(new_value)

**Type support:** Supports all allele types (FloatAllele, IntAllele, LogFloatAllele, BoolAllele, StringAllele). No blending required, just selection.

### Contracts

- Input: template, allele_population (same length as ancestry), ancestry
- Output: new allele with value from stochastically sampled parent
- Sampling: weighted by ancestry probabilities
- Stochastic: different calls can produce different parents
- Type support: all types (no blending, just selection)
- Stateless: no parameters or state

### When to Use

Use StochasticCrossover when:
- Want per-allele variation (different alleles from different parents)
- Ancestry weights should influence but not determine inheritance
- Need exploration via discontinuous combinations
- Hyperparameters have some independence (mixed inheritance makes sense)
- Hyperparameters are discrete (BoolAllele, StringAllele) or continuous

Avoid when:
- Want deterministic inheritance (use DominantParent)
- Want smooth blending (use WeightedAverage)
- Hyperparameters tightly coupled (mixed inheritance breaks dependencies)

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
- **TopN(2, Rank) + SBX + DifferentialEvolution:** Smooth selection gradient, controlled crossover, population-aware mutation. Good for continuous optimization.
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
