# Ancestry Strategies

## Overview

Ancestry strategies decide which genomes become parents and their contribution probabilities. This is the selection phase of evolution - determining which members reproduce based on fitness. Ancestry strategies implement the declare half of the declare-interpret paradigm: they produce ancestry declarations that downstream strategies (crossbreeding, mutation) and orchestrators (model state reconstruction) interpret.

The ancestry contract is simple: receive genomes with fitness, return `List[Tuple[float, UUID]]` declaring parent contributions in rank order. Probability 0.0 means excluded. Non-zero probabilities declare contribution strength - how downstream interprets these is their choice. Ancestry doesn't synthesize allele values or reconstruct model state; it only declares which parents matter.

Ancestry strategies control selection pressure - how strongly evolution favors high-fitness genomes. High pressure converges quickly but risks premature convergence. Low pressure explores broadly but converges slowly. Different strategies offer different pressure characteristics and adaptation mechanisms.

### Declare-Interpret Separation

Ancestry strategies declare parent selection; they don't implement it. The declaration is an ancestry list: `[(probability, uuid), ...]` in rank order. Downstream systems interpret:

- **Crossbreeding strategies** use probabilities as weights for combining allele values (WeightedAverage) or selection criteria (DominantParent picks highest probability parent)
- **Mutation strategies** use ancestry to identify live population (0.0 = dead, don't sample from it) and optionally adapt behavior based on selection strength
- **Orchestrators** use ancestry for model weight reconstruction, interpreting parent contributions to initialize offspring model state

This separation enables composability: any ancestry strategy works with any crossbreeding or mutation strategy. Ancestry just declares "these parents with these weights"; each consumer interprets that declaration for their purpose.

### Selection Pressure

Selection pressure determines how strongly fitness influences reproduction. The fundamental tradeoff:

- **High pressure** - Only best genomes reproduce. Fast convergence, sample-efficient, but risks premature convergence to local optima.
- **Low pressure** - Many genomes reproduce, including mediocre ones. Broad exploration, robust to local optima, but slow convergence and inefficient.

Different strategies provide different pressure mechanisms:
- **Tournament** - Adjustable via tournament size (small = low pressure, large = high pressure)
- **EliteBreeds** - Explicit tiers with fixed pressure (elite always reproduce, bad always die)
- **Rank** - Adjustable via selection_pressure parameter (nonlinear rank-to-probability mapping)
- **Boltzmann** - Adaptive pressure via temperature (high temp = low pressure, low temp = high pressure, can anneal)

## TournamentSelection

Randomly sample k genomes (tournament), select the fittest. Repeat to select multiple parents. Simple, effective, widely used. Selection pressure adjusts via tournament size: k=2 is gentle, k=10 is aggressive.

### Algorithm

For each of num_parents parent slots:
1. Randomly sample `tournament_size` genomes from population
2. Select genome with best (minimum) fitness
3. Record selected genome

After selecting all parents, build ancestry:
- Selected parents get equal probabilities (sum to 1.0)
- Non-selected genomes get 0.0
- If same genome selected multiple times, it receives correspondingly higher probability

**Algorithm demonstration (tournament_size=3, num_parents=2, population=5):**
- Round 1: sample [genome_0, genome_2, genome_4], select best (say genome_2)
- Round 2: sample [genome_1, genome_2, genome_3], select best (say genome_2 again)
- Result ancestry: [(0.0, uuid_0), (0.0, uuid_1), (1.0, uuid_2), (0.0, uuid_3), (0.0, uuid_4)]

Note: Same genome can be selected multiple times (weighted probability). If genome_2 selected twice, it gets probability 1.0 (all contribution).

### Constructor

```python
TournamentSelection(default_tournament_size=3, num_parents=2, use_metalearning=False)
```

**Parameters:**
- **default_tournament_size** (int, default 3): Tournament size used when metalearning disabled. Controls selection pressure.
- **num_parents** (int, default 2): Number of parents to select. Remains constant (structural parameter).
- **use_metalearning** (bool, default False): Enable metalearning for tournament_size parameter.

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor defaults.

**When use_metalearning=True:** handle_setup injects evolvable tournament_size allele. num_parents remains constant (structural parameter).

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["tournament_size"] = TournamentSize allele (see below)
- Injects: metadata["num_parents"] = raw int (constant)
- Returns: allele with injected metadata

**TournamentSize allele type:**
- Extends: IntAllele
- Constructor: `TournamentSize(base_size: int, population_size: int, can_change: bool = True)`
- Intrinsic domain: `{"min": 2, "max": min(10, population_size)}` (adaptive to population)
- Flags: can_mutate=can_change, can_crossbreed=can_change
- Purpose: Evolvable selection pressure via tournament size

**Note on IntAllele evolution:** IntAllele stores float internally, exposes rounded int. Mutation works with raw_value to enable smooth adaptation (tournament_size evolves 3.0 → 3.3 → 3.7 → 4).

### When to Use

Use Tournament when:
- Want simple, well-understood selection
- Need adjustable selection pressure
- Population size varies (tournament adapts naturally)
- Want stochastic selection (randomness prevents premature convergence)

Avoid when:
- Need explicit elite preservation (use EliteBreeds)
- Want deterministic tiers (use EliteBreeds)
- Need rank-based stability (use RankSelection)

## EliteBreeds

Three-tier selection with explicit reproduction rules. Top tier (thrive) always reproduces. Middle tier (survive) reproduces with itself. Bottom tier (die) is replaced by top tier offspring. Provides elite preservation, stable middle class, and aggressive culling simultaneously.

### Algorithm

1. Sort population by fitness (lower is better)
2. Divide into three tiers:
   - **Thrive:** Top `thrive_count` genomes
   - **Survive:** Middle genomes (population_size - thrive_count - die_count)
   - **Die:** Bottom `die_count` genomes

3. Build ancestry for each tier:
   - **Thrive genome:** `[(1.0, self.uuid), (0.0, all others)]` - pure self-reproduction
   - **Survive genome:** `[(1.0, self.uuid), (0.0, all others)]` - pure self-reproduction
   - **Die genome:** Equal probability distributed among thrive tier

**Downstream interpretation:**
- Thrive/survive alleles unchanged by crossbreeding (1.0 self-probability → select own values)
- Die alleles synthesized from thrive population (probabilities weight thrive members)
- Mutation still applies to all tiers

**Behavior (thrive=2, die=2, population=5):**
```
Sorted: [genome_0 (best), genome_1, genome_2, genome_3, genome_4 (worst)]
Tiers: Thrive=[0,1], Survive=[2], Die=[3,4]

Ancestry:
genome_0: [(1.0, uuid_0), (0.0, uuid_1), (0.0, uuid_2), (0.0, uuid_3), (0.0, uuid_4)]
genome_1: [(0.0, uuid_0), (1.0, uuid_1), (0.0, uuid_2), (0.0, uuid_3), (0.0, uuid_4)]
genome_2: [(0.0, uuid_0), (0.0, uuid_1), (1.0, uuid_2), (0.0, uuid_3), (0.0, uuid_4)]
genome_3: [(0.5, uuid_0), (0.5, uuid_1), (0.0, uuid_2), (0.0, uuid_3), (0.0, uuid_4)]
genome_4: [(0.5, uuid_0), (0.5, uuid_1), (0.0, uuid_2), (0.0, uuid_3), (0.0, uuid_4)]
```

Die tier gets equal split of thrive tier (0.5 each if 2 thrive members).

### Constructor

```python
EliteBreeds(thrive_count=2, die_count=2)
```

**Parameters:**
- **thrive_count** (int, default 2): Size of top tier (elite). These always reproduce and replace die tier.
- **die_count** (int, default 2): Size of bottom tier (culled). These are replaced by thrive offspring.

**Constraint:** `thrive_count + die_count < population_size` (must have survive tier). Constructor must validate this constraint and raise ValueError if violated.

### Metalearning

thrive_count and die_count remain constant (not evolvable). Tier sizes define population structure and should not change during evolution - shifting tiers mid-evolution would destabilize genetic continuity.

### When to Use

Use EliteBreeds when:
- Want elite preservation (best genomes always propagate)
- Need aggressive culling of poor performers
- Population has clear fitness tiers
- Want deterministic reproduction rules

Avoid when:
- Population is small (< 5 members, tiers too small)
- Fitness differences are small (tiers arbitrary)
- Want more gradual selection (use Tournament or Rank)

### Relationship to Mutation

EliteBreeds produces different offspring depending on tier. Crossbreeding synthesizes die tier offspring from thrive tier genomes (parents with high fitness), then mutation applies:

- **Thrive tier offspring:** Self-reproduction (1.0 self-probability), mutation perturbs elite values
- **Survive tier offspring:** Self-reproduction (1.0 self-probability), mutation perturbs stable values
- **Die tier offspring:** Synthesized from thrive tier, then mutated

This tier structure interacts naturally with mutation strategies. With Cauchy or Differential Evolution, all tiers benefit from exploration while thrive tier's elite basis provides stability.

## RankSelection

Selection based on genome rank, not raw fitness values. Genomes are sorted, and selection probabilities are assigned by rank using a parameterized curve. More stable than fitness-proportionate selection when fitness scale varies.

### Algorithm

1. Sort population by fitness (rank 0 = best, rank N-1 = worst)
2. Assign selection probability to each rank using pressure formula:
   - Linear: `p(rank) ∝ (population_size - rank)^selection_pressure`
   - Normalized to sum to 1.0
3. Sample parents using rank probabilities
4. Build ancestry with sampled probabilities

**Selection pressure effect:**
- pressure=1.0: Linear (rank 0 twice as likely as rank population_size/2)
- pressure=2.0: Quadratic (rank 0 four times as likely)
- pressure=0.5: Sub-linear (gentler than linear)

**Behavior (population=5, pressure=1.0, num_parents=2):**
```
Ranks: [0 (best), 1, 2, 3, 4 (worst)]
Weights: [5, 4, 3, 2, 1]  (population_size - rank)
Probabilities: [5/15, 4/15, 3/15, 2/15, 1/15] = [0.33, 0.27, 0.20, 0.13, 0.07]
```

Sample 2 parents using these probabilities, build ancestry list.

### Constructor

```python
RankSelection(default_selection_pressure=1.0, num_parents=2, use_metalearning=False)
```

**Parameters:**
- **default_selection_pressure** (float, default 1.0): Pressure used when metalearning disabled. Controls rank-to-probability mapping.
- **num_parents** (int, default 2): Number of parents to sample. Remains constant (structural parameter).
- **use_metalearning** (bool, default False): Enable metalearning for selection_pressure parameter.

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor defaults.

**When use_metalearning=True:** handle_setup injects evolvable selection_pressure allele. num_parents remains constant.

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["selection_pressure"] = SelectionPressure allele (see below)
- Injects: metadata["num_parents"] = raw int (constant)
- Returns: allele with injected metadata

**SelectionPressure allele type:**
- Extends: FloatAllele
- Constructor: `SelectionPressure(base_pressure: float, can_change: bool = True)`
- Intrinsic domain: `{"min": 0.5, "max": 3.0}` (sub-linear to super-linear range)
- Flags: can_mutate=can_change, can_crossbreed=can_change
- Purpose: Evolvable selection pressure adapting over time

### When to Use

Use Rank when:
- Fitness scale varies over time (rank is invariant to scale)
- Fitness differences are very large or very small (rank normalizes)
- Want smooth probability gradient (not discrete tiers)
- Population has clear ordering but noisy fitness values

Avoid when:
- Fitness scale is stable and meaningful (Boltzmann handles this well)
- Want explicit tiers (use EliteBreeds)
- Need simplicity (use Tournament)

## BoltzmannSelection

Temperature-based selection inspired by simulated annealing. Selection probability uses Boltzmann distribution: `p ∝ exp(-fitness/temperature)`. Temperature controls pressure: high temperature (early evolution) = low pressure, low temperature (late evolution) = high pressure. Enables annealing schedules where pressure increases over time.

### Algorithm

1. Compute Boltzmann weights for each genome:
   - `weight_i = exp(-fitness_i / temperature)`
   - Lower fitness → higher weight (better genomes more likely)
2. Normalize weights to probabilities: `p_i = weight_i / sum(weights)`
3. Sample parents using Boltzmann probabilities
4. Build ancestry with sampled probabilities

**Temperature effect:**
- High temp (T >> fitness_range): Weights nearly equal, low pressure, uniform sampling
- Low temp (T << fitness_range): Weights exponentially favor best, high pressure
- Decreasing temp over generations: annealing schedule (explore early, exploit late)

**Behavior (population=3, fitness=[1.0, 2.0, 3.0], temperature=1.0, num_parents=2):**
```
Weights: [exp(-1/1), exp(-2/1), exp(-3/1)] = [0.368, 0.135, 0.050]
Probabilities: [0.368, 0.135, 0.050] / 0.553 = [0.67, 0.24, 0.09]
```

Best genome (fitness=1.0) gets 67% probability.

### Constructor

```python
BoltzmannSelection(default_temperature=1.0, num_parents=2, use_metalearning=False)
```

**Parameters:**
- **default_temperature** (float, default 1.0): Temperature used when metalearning disabled. Controls selection pressure.
- **num_parents** (int, default 2): Number of parents to sample. Remains constant (structural parameter).
- **use_metalearning** (bool, default False): Enable metalearning for temperature parameter. When enabled, temperature evolves instead of following external annealing schedule.

### Metalearning

**When use_metalearning=False:** handle_setup returns allele unchanged. Strategy uses constructor defaults. Temperature can be manually annealed via external schedule.

**When use_metalearning=True:** handle_setup injects evolvable temperature allele. Temperature evolves under selection pressure, enabling adaptive pressure without external annealing. Evolvable temperature can complement or replace manual annealing. num_parents remains constant.

**handle_setup contract (when use_metalearning=True):**
- Receives: allele (AbstractAllele)
- Injects: metadata["temperature"] = Temperature allele (see below)
- Injects: metadata["num_parents"] = raw int (constant)
- Returns: allele with injected metadata

**Temperature allele type:**
- Extends: FloatAllele
- Constructor: `Temperature(base_temperature: float, can_change: bool = True)`
- Intrinsic domain: `{"min": 0.1, "max": 10.0}` (high to low pressure range)
- Flags: can_mutate=can_change, can_crossbreed=can_change
- Purpose: Evolvable selection pressure, alternative to manual annealing

### When to Use

Use Boltzmann when:
- Want adaptive pressure over time (annealing)
- Need fitness-proportionate selection with controlled pressure
- Evolving over many generations (schedule matters)
- Want principled temperature-based control

Avoid when:
- Short evolution runs (annealing doesn't have time to work)
- Don't want to tune temperature schedule
- Need simple, static pressure (use Tournament or Rank)

### Annealing Schedule

Common pattern: start with exploration, increase pressure over time.

**Linear annealing:**
```python
temperature = T_initial * (1 - generation / max_generations)
```

**Exponential annealing:**
```python
temperature = T_initial * (decay_rate ** generation)
```

Typical values: `T_initial=5.0`, `T_final=0.5`, tune based on fitness range.

## Guidelines

### Choosing Strategies

**Default recommendation:** Start with Tournament (tournament_size=3). Simple, effective, well-understood.

**For elite preservation:** Use EliteBreeds. Guarantees best genomes propagate.

**For fitness scale robustness:** Use Rank. Invariant to fitness scaling.

**For adaptive pressure:** Use Boltzmann with annealing. Explore early, exploit late.

### Combining with Crossbreeding and Mutation

Ancestry strategies compose with any crossbreeding/mutation strategies. Some combinations are particularly effective:

- **Tournament + WeightedAverage + Gaussian:** Balanced composition. Moderate pressure, smooth blending, local search.
- **EliteBreeds + DominantParent + Cauchy:** Elite preservation with exploration. Thrive tier preserved exactly (DominantParent selects 1.0 self-probability), die tier gets Cauchy exploration.
- **Boltzmann + SBX + DifferentialEvolution:** Adaptive pressure with population-aware operators. Temperature anneals, DE uses population structure.
- **Rank + StochasticCrossover + Uniform:** Robust exploration. Rank normalizes fitness, stochastic sampling, uniform mutation.

No combination is invalid. Effectiveness depends on problem characteristics.

### Selection Pressure Guidelines

**Low pressure (explore broadly):**
- Tournament with small size (k=2)
- Rank with low pressure (<1.0)
- Boltzmann with high temperature (T=5.0+)
- Good for: Early evolution, multimodal landscapes, large populations

**High pressure (exploit best):**
- Tournament with large size (k=10+)
- EliteBreeds with large thrive/die counts
- Rank with high pressure (>1.5)
- Boltzmann with low temperature (T<0.5)
- Good for: Late evolution, fine-tuning, when best region is known

**Adaptive pressure:**
- Boltzmann with annealing schedule
- Manual strategy switching (Tournament early → EliteBreeds late)

### Population Size Considerations

- **Small populations (< 5):** Use Tournament (adapts naturally). Avoid EliteBreeds (tiers too small).
- **Medium populations (5-20):** All strategies work. EliteBreeds effective with appropriate tier sizes.
- **Large populations (20+):** Tournament and Rank scale well. Boltzmann computation can be expensive.

### Tuning Parameters

**Tournament size:** Start at 3. Increase if converging too slowly, decrease if premature convergence.

**EliteBreeds tiers:** Rule of thumb: thrive=10-20% of population, die=10-20% of population. Adjust based on convergence speed.

**Rank pressure:** Start at 1.0 (linear). Increase to 1.5-2.0 for more pressure.

**Boltzmann temperature:** Start at T = fitness_range / 2. Anneal to T = fitness_range / 10 over evolution.

Tune based on observed convergence: too fast (premature) → decrease pressure, too slow → increase pressure.
