# ClanTune Genetic Algorithm Toolbox - Specification

## Scope

### In Scope
This toolbox provides:
1. **Genome management:** Data structure for alleles and meta-controls
2. **Mutation operations:** Apply hierarchical mutation algorithm to genomes
3. **Population filtering:** Sort population by fitness and partition into tiers

### Out of Scope
This toolbox does NOT handle:
- Distributed coordination or process management
- File I/O or serialization formats (though Genome provides save/load methods)
- Training loop orchestration
- Fitness computation or collection
- Model state management
- When to trigger mutations (caller's responsibility)
- Generation boundaries or stopping criteria

### Integration Philosophy
This is a **toolbox**, not a framework. ClanTune's training orchestrator calls these tools when needed. The toolbox doesn't know about distributed training, cooperative phases, or gradient sharing.

---

## Design Decisions

### Genome Structure

**Meta-controls (fixed special key):**
```python
"__meta_mutation_control__": {
    "mutation_rate": 0.15,        # Probability of mutation (does NOT mutate)
    "mutation_std": 0.05,          # Std for mutating allele stds (does NOT mutate)
    "__min_std_clamp__": 0.01,     # Floor for allele stds (fixed)
    "__max_std_clamp__": 0.5       # Ceiling for allele stds (fixed)
}
```

**Alleles (user-defined keys):**
```python
"allele_name": {
    "value": <current_value>,
    "std": <mutation_std>,
    "type": "log" | "linear",
    "bounds": {"min": ..., "max": ...}  # Optional
}
```

### Mutation Algorithm

1. **Mutate allele stds:** For each allele's `std`, with probability `mutation_rate`:
   - Perturb using log mode with `mutation_std` 
   - Clamp result between `__min_std_clamp__` and `__max_std_clamp__`

2. **Mutate allele values:** For each allele's `value`, with probability `mutation_rate`:
   - Perturb using allele's `type` ("log" or "linear") and allele's `std`
   - Clamp result to allele's `bounds` (if specified)

**Note:** `mutation_rate` and `mutation_std` do NOT mutate - they are stable parameters.

### Genome API

```python
# Initialize with default meta-controls
genome = Genome()

# Add alleles with their properties
genome.add_allele(
    name="lr",
    type="log",
    starting_value=0.001,
    min=1e-5,
    max=1e-1,
    std=0.1
)
genome.add_allele(
    name="momentum", 
    type="linear",
    starting_value=0.9,
    min=0.8,
    max=0.99,
    std=0.05
)

# Set fitness (after training evaluation)
genome.set_fitness(0.85)

# Get fitness
fitness = genome.get_fitness()

# Apply mutation
genome.mutate()

# Export hyperparameters for training
hparams = genome.to_dict()  # Returns: {"lr": 0.001, "momentum": 0.9}

# Serialize to dict (format-agnostic)
data = genome.serialize()  # Returns full internal structure as dict
restored = Genome.deserialize(data)  # Reconstruct from dict

# Save/load to JSON (convenience)
genome.save("/path/to/genome.json")
loaded_genome = Genome.load("/path/to/genome.json")
```

### Population Management API

```python
# Configure manager with tier percentages
manager = CutoffPopulationManager(
    thriving_pct=0.2,   # Top 20% can be cloned
    dead_pct=0.3         # Bottom 30% must clone from thriving
)

# Load all genomes (one per rank/process)
population = {rank: Genome.load(f"{rank}") for rank in range(world_size)}

# Partition population into tiers by fitness
thriving, survivors, dead = manager.partition(
    population,
    key=lambda genome: genome.get_fitness(),
    objective_sense="min"  # "min" = lower is better, "max" = higher is better
)
# Returns three dict subsets:
#   thriving: {rank: genome, ...}  - Top 20%
#   survivors: {rank: genome, ...} - Middle 50%
#   dead: {rank: genome, ...}      - Bottom 30%
```

---

## Complete Usage Example

```python
from clantune_genetic import Genome, CutoffPopulationManager
import random

# === Initialization (done once) ===

# Create root genome
root = Genome(
    mutation_rate=0.15,
    mutation_std=0.05,
    min_std_clamp=0.01,
    max_std_clamp=0.5
)
root.add_allele("lr", "log", 0.001, min=1e-5, max=1e-1, std=0.1)
root.add_allele("momentum", "linear", 0.9, min=0.8, max=0.99, std=0.05)
root.add_allele("weight_decay", "log", 1e-4, min=0, max=1e-2, std=0.1)

# Save root genome
root.save("genomes/root.json")

# Each process loads and mutates
my_rank = get_rank()  # From distributed training framework
genome = Genome.load("genomes/root.json")
genome.mutate()  # Initial mutation
genome.save(f"genomes/{my_rank}.json")

# === Training Loop (each competitive phase) ===

# 1. Each process trains with its genome
hparams = genome.to_dict()
val_loss = train_with_hparams(hparams)  # ClanTune's training code
genome.set_fitness(val_loss)
genome.save(f"genomes/{my_rank}.json")

# 2. After training, each process loads all genomes
world_size = get_world_size()
population = {rank: Genome.load(f"genomes/{rank}.json") for rank in range(world_size)}

# 3. Sort population
manager = CutoffPopulationManager(thriving_pct=0.2, dead_pct=0.3)
thriving, survivors, dead = manager.partition(
    population,
    key=lambda g: g.get_fitness(),
    objective_sense="min"  # Lower val_loss is better
)

# 4. Each process decides its genome for next generation
if my_rank in dead:
    # Dead: clone from a random thriving genome
    parent_rank = random.choice(list(thriving.keys()))
    genome = population[parent_rank]
elif my_rank in thriving:
    # Thriving: keep own genome
    genome = population[my_rank]
else:  # my_rank in survivors
    # Survivors: keep own genome
    genome = population[my_rank]

# 5. Mutate and save for next round
genome.mutate()
genome.save(f"genomes/{my_rank}.json")

# 6. Continue to next training round...
```

---

## Implementation Details

## Implementation Details

### Genome Class

**Constructor:**
```python
Genome(
    mutation_rate=0.15,
    mutation_std=0.05,
    min_std_clamp=0.01,
    max_std_clamp=0.5
)
```

**Internal Structure:**
```python
{
    "__meta_mutation_control__": {
        "mutation_rate": 0.15,
        "mutation_std": 0.05,
        "__min_std_clamp__": 0.01,
        "__max_std_clamp__": 0.5
    },
    "lr": {
        "value": 0.001,
        "std": 0.1,
        "type": "log",
        "bounds": {"min": 1e-5, "max": 1e-1}
    },
    "momentum": {
        "value": 0.9,
        "std": 0.05,
        "type": "linear",
        "bounds": {"min": 0.8, "max": 0.99}
    },
    "__fitness__": 0.85  # Set via set_fitness()
}
```

**Methods:**
- `add_allele(name, type, starting_value, min=None, max=None, std=0.1)` - Add an allele
  - For `type="log"`: `min` must be provided and must be > 0
  - For `type="linear"`: `min` and `max` are optional (can be None for unbounded)
- `mutate()` - Apply mutation algorithm (uses Python's `random` module)
- `set_fitness(value)` - Store fitness value
- `get_fitness()` - Retrieve fitness value
- `to_dict()` - Export `{name: value}` for hyperparameters
- `serialize()` - Return full internal structure as dict (format-agnostic)
- `deserialize(data)` (classmethod) - Reconstruct Genome from dict
- `save(path)` - Serialize to JSON file
- `load(path)` (classmethod) - Deserialize from JSON file

**Mutation Implementation Notes:**
- Log mode: `new_value = value * exp(N(0, std))`
- Linear mode: `new_value = value + N(0, std)`
- Clamping: `new_value = clip(new_value, bounds.min, bounds.max)`
- Probability: Use `random.random() < mutation_rate` for each mutation decision

### AbstractPopulationManager Base Class

```python
class AbstractPopulationManager:
    def partition(self, population, key, objective_sense="min"):
        """
        Partition population into categorized subsets.
        
        Args:
            population: Dict of {rank: genome, ...}
            key: Function to extract sortable value from genome
            objective_sense: "min" (lower is better) or "max" (higher is better)
        
        Returns:
            Implementation-specific partition structure
        """
        raise NotImplementedError
```

### CutoffPopulationManager Class

**Constructor:**
```python
CutoffPopulationManager(
    thriving_pct=0.2,  # Top 20%
    dead_pct=0.3        # Bottom 30%
)
```

**Methods:**
- `partition(population_dict, key, objective_sense="min")` - Returns `(thriving, survivors, dead)` as dict subsets

**Partitioning Logic:**
1. Apply key function to get sortable values from each genome
2. Sort by fitness according to `objective_sense`:
   - `"min"`: lower values are better (e.g., loss)
   - `"max"`: higher values are better (e.g., accuracy)
3. Partition into three tiers based on percentages:
   - Thriving: Top `thriving_pct` of population (best performers)
   - Dead: Bottom `dead_pct` of population (worst performers)
   - Survivors: Middle `1.0 - thriving_pct - dead_pct` of population
4. Return three dicts with same keys as input, partitioned by tier

**Edge Cases:**
- If percentages don't sum to 1.0, survivors get the remainder
- If population size doesn't divide evenly, round tier sizes appropriately
- Empty tiers are valid (return empty dicts)

---

## Testing Strategy

### Genome Tests
- Initialization with default and custom meta-controls
- Adding alleles with various configurations (log/linear, bounded/unbounded)
- Log alleles require min > 0, reject invalid configurations
- Mutation produces values within bounds
- Mutation respects probability (statistical test)
- Log vs linear mutation modes work correctly
- `serialize()`/`deserialize()` roundtrip preserves structure
- `save()`/`load()` roundtrip works with JSON
- `to_dict()` exports only allele values
- Uses Python's `random` module (document seed control externally)

### PopulationManager Tests
- Partitioning with various population sizes and percentages
- `objective_sense="min"` sorts correctly (lower is better)
- `objective_sense="max"` sorts correctly (higher is better)
- Percentage calculations handle edge cases (rounding, empty tiers)
- Key function applied correctly
- Dict subsets contain correct ranks
- Works with custom key functions (not just fitness)
- AbstractPopulationManager interface enforced

---

## Future Extensions (Out of Scope for V1)

- Multiple population managers (e.g., TournamentPopulationManager, ElitistManager)
- Crossover operations between genomes
- Diversity metrics and niching
- Adaptive meta-controls (mutation_rate/mutation_std that evolve)
- Visualization of genome evolution
- History tracking and lineage trees