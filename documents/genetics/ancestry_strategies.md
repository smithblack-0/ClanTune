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

Fulfills AbstractAncestryStrategy's select_ancestry contract. Implements tournament selection: randomly sample small subsets of the population (tournaments), select the fittest from each subset, repeat to build parent set. Configurable selection pressure through tournament size - larger tournaments favor fitter genomes (exploitation), smaller tournaments preserve diversity (exploration).

### Constructor

```python
TournamentSelection(tournament_size=3, num_tournaments=7)
```

Stores tournament selection parameters as instance fields.

**Parameters:**
- **tournament_size** (int, default 3): Number of genomes sampled per tournament. Controls selection pressure.
- **num_tournaments** (int, default 7): Number of tournament rounds to run. Sampling occurs with replacement — same genome can win multiple rounds. Determines ancestry probability denominators (prob = win_count / num_tournaments).

**Validation:** If tournament_size < 2, raise ValueError("Tournament size must be at least 2").

### select_ancestry

Implementation of AbstractAncestryStrategy's select_ancestry hook. Executes repeated tournaments, builds ancestry declaring parent contributions based on win frequencies.

```python
select_ancestry(my_genome: Genome, population: List[Genome]) -> List[Tuple[float, UUID]]
```

**Receives:** my_genome (genome being evolved, must be in population), population (all genomes in rank order with fitness set, lower fitness is better).

**Returns:** Ancestry as `[(probability, uuid), ...]` in rank order where:
- List length equals population size
- Index i corresponds to population[i]
- UUID at index i equals population[i].uuid
- Probability = (win_count / num_tournaments) for that genome
- Probabilities sum to 1.0

**Algorithm:**

1. Initialize win_counts dict mapping genome.uuid → 0 for all genomes
2. For each of self.num_tournaments rounds:
   - Sample self.tournament_size genome indices uniformly from range(population_size) with replacement
   - Extract tournament = [population[i] for i in sampled_indices]
   - Select winner = min(tournament, key=lambda g: g.fitness)
   - Increment win_counts[winner.uuid]
3. Build ancestry list in rank order:
   - For each genome in population:
     - prob = win_counts[genome.uuid] / self.num_tournaments
     - Append (prob, genome.uuid)
4. Return ancestry list

**Edge case:** Same genome can be selected multiple times (sampling with replacement). If genome wins all num_tournaments rounds, receives probability 1.0.

### Contracts

- Input: my_genome in population, all genomes have fitness set (lower is better)
- Output: ancestry with length = population size, index i corresponds to population[i]
- Probabilities sum to 1.0, reflect win frequencies (win_count / num_tournaments)
- Sampling: with replacement (genome can win multiple rounds)
- Constraint: tournament_size >= 2 (validated in constructor)

### When to Use

Use TournamentSelection when:
- Want configurable selection pressure via tournament size tuning
- Need stochastic selection preventing premature convergence
- Population size varies (tournament adapts naturally)
- Want simple, well-understood mechanism

Avoid when:
- Want deterministic elite preservation (use EliteBreeds)
- Need smooth fitness-proportionate selection (use RankSelection)
- Want adaptive pressure over time (use BoltzmannSelection)

## EliteBreeds

Fulfills AbstractAncestryStrategy's select_ancestry contract. Implements three-tier deterministic selection where top performers self-reproduce, middle tier self-reproduces, bottom tier replaced by offspring from top tier. Configurable exploitation through tier sizes - larger thrive tier preserves more elites, larger die tier culls more aggressively.

### Constructor

```python
EliteBreeds(thrive_count=2, die_count=2)
```

Stores tier size parameters as instance fields.

**Parameters:**
- **thrive_count** (int, default 2): Number of top-fitness genomes receiving 1.0 self-probability. These elite genomes self-reproduce and also serve as exclusive parents for die tier replacement.
- **die_count** (int, default 2): Number of bottom-fitness genomes replaced by thrive offspring. Receive ancestry distributing equal probability among thrive tier.

**Validation:** Constraint `thrive_count + die_count < population_size` ensures survive tier exists. Validated at runtime when population size known. If violated, raise ValueError("thrive_count + die_count must be less than population_size").

### select_ancestry

Implementation of AbstractAncestryStrategy's select_ancestry hook. Sorts population to identify tiers, builds ancestry declaring self-reproduction for thrive/survive and thrive-sourced replacement for die tier.

```python
select_ancestry(my_genome: Genome, population: List[Genome]) -> List[Tuple[float, UUID]]
```

**Receives:** my_genome (genome being evolved, must be in population), population (all genomes in rank order with fitness set, lower fitness is better).

**Returns:** Ancestry as `[(probability, uuid), ...]` in rank order where:
- List length equals population size
- Index i corresponds to population[i]
- Entry (probability, uuid) where probability indicates population[i]'s contribution to my_genome's offspring
- If my_genome in thrive/survive: 1.0 probability for self, 0.0 for all others
- If my_genome in die: (1.0 / thrive_count) for each thrive member, 0.0 for others
- Probabilities sum to 1.0

**Algorithm:**

1. Validate: if self.thrive_count + self.die_count >= len(population), raise ValueError
2. Sort population by fitness: sorted_pop = sorted(population, key=lambda g: g.fitness)
3. Build tier membership sets:
   - thrive_set = set(sorted_pop[0 : self.thrive_count])
   - die_set = set(sorted_pop[-self.die_count :]) if self.die_count > 0 else set()
4. Build ancestry in original rank order:
   - Initialize ancestry = []
   - For each genome in population (original order, not sorted):
     - If my_genome in thrive_set or (my_genome not in thrive_set and my_genome not in die_set):
       - If genome == my_genome: prob = 1.0
       - Else: prob = 0.0
     - Else (my_genome in die_set):
       - If genome in thrive_set: prob = 1.0 / self.thrive_count
       - Else: prob = 0.0
     - Append (prob, genome.uuid) to ancestry
5. Return ancestry

### Contracts

- Input: my_genome in population, all genomes have fitness set (lower is better)
- Output: ancestry with length = population size, index i corresponds to population[i]
- Tier constraint: thrive_count + die_count < population_size (validated at runtime)
- Thrive/survive: 1.0 self-probability (deterministic self-reproduction)
- Die: equal probability distributed among thrive tier (sum = 1.0)
- Tier assignment by fitness after sorting

### When to Use

Use EliteBreeds when:
- Want guaranteed elite preservation (best genomes self-reproduce)
- Need aggressive culling (worst genomes replaced by thrive offspring)
- Population has clear fitness stratification
- Pair with DominantParent crossbreeding (1.0 probability → exact copy)

Avoid when:
- Population small (< 5 members, tiers too constrained)
- Fitness differences minimal (tier boundaries arbitrary)
- Need gradual selection pressure (use TournamentSelection or RankSelection)

## RankSelection

Fulfills AbstractAncestryStrategy's select_ancestry contract. Implements rank-based probability assignment where contribution probabilities depend on fitness rank, not raw fitness values. Sorts population by fitness, assigns probabilities using power curve on rank position across all genomes. Provides stable selection gradient when fitness scale varies. Pair with TopN to restrict participation to the top N contributors.

### Constructor

```python
RankSelection(selection_pressure=1.0)
```

Stores selection parameter as instance field.

**Parameters:**
- **selection_pressure** (float, default 1.0): Exponent controlling rank-to-probability curve steepness. Pressure 1.0 is linear, > 1.0 favors top ranks more strongly, < 1.0 provides gentler gradient.

**Validation:** If selection_pressure <= 0, raise ValueError("Selection pressure must be positive").

### select_ancestry

Implementation of AbstractAncestryStrategy's select_ancestry hook. Sorts population by fitness to determine ranks, computes rank-based weights, filters to top num_parents, normalizes, returns probabilities in original rank order.

```python
select_ancestry(my_genome: Genome, population: List[Genome]) -> List[Tuple[float, UUID]]
```

**Receives:** my_genome (genome being evolved, must be in population), population (all genomes in rank order with fitness set, lower fitness is better).

**Returns:** Ancestry as `[(probability, uuid), ...]` in rank order where:
- List length equals population size
- Index i corresponds to population[i]
- UUID at index i equals population[i].uuid
- All genomes receive non-zero probabilities based on rank weights
- Probabilities sum to 1.0

**Algorithm:**

1. Sort population by fitness: sorted_pop = sorted(population, key=lambda g: g.fitness)
2. Compute rank weights for all genomes:
   - For genome at rank i in sorted_pop: weight[i] = (len(population) - i) ** self.selection_pressure
3. Normalize weights:
   - total_weight = sum(all weights)
   - For each weight: prob = weight / total_weight
4. Build rank_probs dict mapping genome.uuid → probability
5. Build ancestry in original rank order:
   - For each genome in population (original order):
     - Append (rank_probs[genome.uuid], genome.uuid)
6. Return ancestry

### Contracts

- Input: my_genome in population, all genomes have fitness set (lower is better)
- Output: ancestry with length = population size, index i corresponds to population[i]
- All genomes receive non-zero probability; probabilities sum to 1.0
- Deterministic: same ancestry for all genomes (doesn't depend on my_genome)
- Constraint: selection_pressure > 0 (validated in constructor)
- Rank-based: probabilities invariant to fitness scale, depend only on ordering

### When to Use

Use RankSelection when:
- Fitness scale varies over time (rank normalizes scale)
- Want smooth probability gradient across all population members
- Population has clear ordering but noisy fitness values

Pair with TopN to restrict participation to the top N contributors.

Avoid when:
- Want stochastic selection (use TournamentSelection)
- Want discrete elite preservation (use EliteBreeds)
- Fitness scale is stable and meaningful (use BoltzmannSelection)

## BoltzmannSelection

Fulfills AbstractAncestryStrategy's select_ancestry contract. Implements temperature-based selection using Boltzmann distribution: probabilities proportional to exp(-fitness/temperature) across all genomes. Temperature controls selection pressure — high temperature gives nearly uniform probabilities (low pressure), low temperature exponentially concentrates probability on best genomes (high pressure). Supports annealing schedules where pressure increases over time. Pair with TopN to restrict participation to the top N contributors.

### Constructor

```python
BoltzmannSelection(temperature=1.0)
```

Stores temperature as instance field.

**Parameters:**
- **temperature** (float, default 1.0): Controls selection pressure via Boltzmann distribution. High temperature (T >> fitness_range) gives nearly uniform probabilities (low pressure). Low temperature (T << fitness_range) exponentially favors best genomes (high pressure). Can be annealed via external schedule.

**Validation:** If temperature <= 0, raise ValueError("Temperature must be positive").

### select_ancestry

Implementation of AbstractAncestryStrategy's select_ancestry hook. Computes Boltzmann weights for all genomes, filters to top num_parents by weight, normalizes, returns probabilities in original rank order.

```python
select_ancestry(my_genome: Genome, population: List[Genome]) -> List[Tuple[float, UUID]]
```

**Receives:** my_genome (genome being evolved, must be in population), population (all genomes in rank order with fitness set, lower fitness is better).

**Returns:** Ancestry as `[(probability, uuid), ...]` in rank order where:
- List length equals population size
- Index i corresponds to population[i]
- UUID at index i equals population[i].uuid
- All genomes receive non-zero probabilities proportional to Boltzmann weights
- Probabilities sum to 1.0

**Algorithm:**

1. Compute Boltzmann weights for all genomes:
   - For each genome: weight = exp(-genome.fitness / self.temperature)
   - Lower fitness → higher weight (better genomes more likely)
2. Normalize weights:
   - total_weight = sum(all weights)
   - For each genome: prob = weight / total_weight
3. Build boltzmann_probs dict mapping genome.uuid → probability
4. Build ancestry in original rank order:
   - For each genome in population (original order):
     - Append (boltzmann_probs[genome.uuid], genome.uuid)
5. Return ancestry

### Contracts

- Input: my_genome in population, all genomes have fitness set (lower is better)
- Output: ancestry with length = population size, index i corresponds to population[i]
- All genomes receive non-zero probability; probabilities sum to 1.0
- Deterministic: same ancestry for all genomes (doesn't depend on my_genome)
- Constraint: temperature > 0 (validated in constructor)
- Fitness-proportionate: probabilities reflect exp(-fitness/temperature)

### When to Use

Use BoltzmannSelection when:
- Want adaptive pressure over time (anneal temperature externally)
- Need fitness-proportionate selection with temperature control
- Evolving over many generations (annealing schedule matters)
- Want principled temperature-based pressure tuning

Pair with TopN to restrict participation to the top N contributors.

Avoid when:
- Short evolution runs (annealing doesn't have time to work)
- Don't want to tune temperature schedule (use TournamentSelection or RankSelection)
- Need simplicity (use TournamentSelection)

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

## TopN

Fulfills AbstractAncestryStrategy's select_ancestry contract as a composable wrapper. Runs a wrapped strategy then restricts participation to the top N contributors: zeroes all but the top N probabilities and renormalizes. Required pairing for crossbreeding strategies with strict parent count contracts — SBX requires exactly 2 non-zero entries.

### Constructor

```python
TopN(n: int, strategy: AbstractAncestryStrategy)
```

Stores both parameters as instance fields.

**Parameters:**
- **n** (int): Number of parents to preserve with non-zero probability.
- **strategy** (AbstractAncestryStrategy): Wrapped ancestry strategy whose output is clipped to top N.

**Validation:** If n < 1, raise ValueError("n must be at least 1").

### select_ancestry

Implementation of AbstractAncestryStrategy's select_ancestry hook. Delegates to wrapped strategy, clips to top N, renormalizes.

```python
select_ancestry(my_genome: Genome, population: List[Genome]) -> List[Tuple[float, UUID]]
```

**Receives:** my_genome and population forwarded unchanged to wrapped strategy.

**Returns:** Ancestry as `[(probability, uuid), ...]` in rank order where:
- List length equals population size
- Exactly N entries have non-zero probability (or fewer if population size < N)
- Probabilities sum to 1.0

**Algorithm:**

1. Delegate: ancestry = self.strategy.select_ancestry(my_genome, population)
2. Find top N indices by probability descending; tie-breaking by index order (lower index wins)
3. Zero all probabilities outside top N
4. Renormalize: divide each top N probability by their sum
5. Return clipped ancestry

### Contracts

- Input: forwarded to wrapped strategy unchanged
- Output: ancestry with length = population size, exactly N non-zero probabilities
- Renormalization: top N probabilities sum to 1.0
- Tie-breaking at boundary: lower index wins
- Constraint: n >= 1 (validated in constructor)

### When to Use

Use TopN when pairing any ancestry strategy with a crossbreeding strategy that requires a fixed number of non-zero parents. Required for SimulatedBinaryCrossover: `TopN(n=2, strategy=...)`.

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
- **TopN(2, Boltzmann) + SBX + DifferentialEvolution:** Adaptive pressure with population-aware operators. Temperature anneals, TopN ensures SBX receives exactly 2 parents, DE uses population structure.
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

**Rank pressure:** Start at 1.0 (linear). Increase to 1.5-2.0 for more pressure. Pair with TopN to limit contributing parents.

**Boltzmann temperature:** Start at T = fitness_range / 2. Anneal to T = fitness_range / 10 over evolution.

Tune based on observed convergence: too fast (premature) → decrease pressure, too slow → increase pressure.
