# Clan Training: PBT-Style Schedule Adaptation with Cooperative Gradient Sharing

## Motivation

Population-Based Training (PBT) is a strong tool for exploration, but in “conventional training” it often feels compute-wasteful: with N workers you spend ~N× compute exploring, but at the end you typically keep only one checkpoint. The niche I want is: **automatic hyperparameter schedules** (learning rate, weight decay, dropout, etc.) **without paying full PBT cost**, i.e., without running fully independent trajectories for the whole run. We need an exploitation-focused version of PBT that is economical to run. This is intended to be complementary to traditional HBO: Your initial search finds a working starting basin, and Clan Training ruthlessly and greedily follows the basin to near-optimal hyperparameters regardless of how many you have.

The goal is “engineering solved” generalized schedules: for most conventional training runs, start from any sane default that trains, and the system should automatically adapts schedules (weight_decay, learning rate, anything float, continous, and responsive) toward near-optimal over long pretraining, with minimal user tuning (ideally only round length and duty cycle). The technical definition of full success is "90% of scheduling problems are solved to within 90% of full optimizer step performance."
## Core Idea

Maintain a *population* of models (a “clan”), each with its own genome encoding schedulable hyperparameters. Training proceeds in a "round", which usually overlaps directly with a "validation" period. Poorly performing members are pruned between rounds, and well-performing members are cloned. There is a cooperative phase, and a competitive phase. Training alternates between:

1. **Cooperative phase (most of the time):** clan members share *gradients* using the DDP update paradigm so training remains efficient. Notably, clan members are *not identical* and possess different hyperparameters. Certain hyperparameters are averaged across devices. Only hyperparameters that affect how gradients are turned into updates express themselves here (optimizer hyperparameters)
2. **Competitive phase (short window):** members train independently from their ending cooperative state. They desync (no gradient synchronization) on a common dataset window so “washed-out” differences (e.g., dropout, batch_size) become rankable. Averaged parameters are instead re-expressed.
3. **Selection / repopulation:** prune poor performers and repopulate via cloning + mutation from strong performers.

The *emergent stabilizer* is that clan fitness implicitly includes “are gradients mutually intelligible?” Members that drift into regions where shared directions are no longer helpful fall behind and get pruned. Over time, the population self-organizes into a compatibility manifold where cooperation works. This gives rise to the name "clan training" rather than "population training" since an implicit pressure is to still be useful to the clan.

This is not “DDP with a bit of PBT.” It is a designed ecology: a clan that **usually cooperates** but **sometimes competes**, with ongoing interchangeability and repopulation.

## Terminology

- **Genome:** vector of schedulable parameters (and schedules), plus per-gene mutation magnitudes.
- **Express**: To allow a genome to influence training downstream. A allele that is expressed influences training (expresses phenotype); to be nonexpressed technically means to be set to the average of the clan's genomes.
- **Member**: A discrete pairing of a genome and a set of parameters that exist, have been produced by, or are evolving under this genome.
- **Round:** one cycle consisting of cooperative steps + competitive steps + evaluation + pruning + reproduction.
- **Duty cycle:** fraction of steps in a round spent in the competitive (no-sync) phase.
- **Optimizer Hyperparameter**: Anything that shows up as an effect even with shared gradients, such as weight decay or learning rate
- **Specialized Hyperparameter**: Anything that does not show up in the above or is incompatible during sharing of gradients, such as dropout rate or batch size.
- 

## Training Loop (High-Level)

Let population size = P. Each member i has parameters θᵢ, optimizer state Oᵢ, and genome gᵢ We presume mutation is taken care of elsewhere.

For each round:

### 1) Cooperative phase (≈ 80–90% of round)
- Train with distributed data (normal sharding).
- Specialized hyperparameters are not expressed. This means we average specialized hyperparameters across the group; select same one shared everywhere. 
- Use DDP-style gradient sharing (torch DDP semantics: average gradients across a group).
- Members are a distinct population and will continue to diverge due to hyperparameter differences; Do not think DDP sharing of gradients means the models are identical.
  - LR schedules, WD schedules, betas/momentum, clip thresholds, accumulation strategy, etc.
- The communicated object is the shared gradient (or step direction), but each member may apply it differently via its own optimizer state/hyperparameters.

This phase provides efficiency and amplifies small advantages: once a better set of optimizer hyperparameters starts winning, cooperative training compounds its advantage over many steps and even many rounds until it emerges. Most of training is spent in this mode, retaining efficiency advantages. It should be kept in mind optimizer hyperparameters train very rapidly as a result. Since optimizer hyperparameters are both the trickiest and most important to schedule directly, this is more a pro than a con.

### 2) Competitive phase (≈ 10–20% of round)

- Switch to **common data** across the clan.
- Turn on `no_sync` so members train independently (no gradient sharing). This now allows freewheeling as separate models. 
- Express individual specialized genome choices; note we still keep optimizer allales expressed too. 
- Purpose: expose differences that are either impossible to train when shared, or averaged away as composite gradients, and allow them to be expressed:
  - dropout rates
  - stochastic regularizers
  - control thresholds or values for gradient accumulation steps.

This exists to handle hyperparameters that are not optimizer based. It should be kept in mind these tends to train much more slowly due to the lower period. However, when optimizer hyperparameters are near ideal, these will begin to train effectively. Most of the compute in this step can be considered 'lost'; however, unlike PBT, only a small part of training is spent in this mode. 

### 3) Evaluation (once per round)
- Compute a single fitness value per member: typically validation loss / target metric, evaluated at the end of the competitive phase.
- Apply fitness mechanism based on fitness. This involves
  - Pruning unfit models and their genomes
  - Reproducing really fit models and their genomes

### Mutation and Meta-Mutation

Each genome g contains:
- the current schedule values (or schedule parameters) for each controllable hyperparameter
- **per-gene mutation magnitudes** (std-dev / step size) that can evolve.

Order matters:
1) mutate the mutation magnitudes first
2) mutate the hyperparameter genes using the newly mutated magnitudes

This supports self-tuning exploration:
- if a gene is near-optimal, selection favors shrinking its mutation std
- if adaptation is needed, selection can favor increasing mutation std

## What “Schedules” Means Here

Focus is on **time-varying scalar controls** (schedules), not discrete algorithm swaps:
- learning rate
- weight decay
- dropout
- clip thresholds
- effective batch size via gradient accumulation factor (see below)
- other scalar training-control knobs

This is not trying to solve “hyperparameters in general” (eg., optimizer family, architecture decisions). This tries to guarentee near-optimiality once you choose a general schedule.

## Handling Parameters That Must Be Shared During Cooperative Phase

Some controls cannot safely differ during the cooperative gradient-sharing phase (e.g., microbatch size / shapes), especially under standard DDP constraints. These are called Specialized Hyperparameters. 

- Classify each gene as:
  - **Optimizer Hyperparameter (allowed to differ)** during cooperative phase
  - **Specialized Hyperparameter (must be shared)** during cooperative phase

If a gene is Specialized:
- during competitive phase: allow members to differ (so selection can learn)
- during cooperative phase: apply a **consensus aggregation** across the clan, e.g. mean/median → then round/clip to feasible domain

The Competitive phase of training is worth it's trouble to train this kind of hyperparameter. This allows training things like batch accumulation sizes as we go as well. Note that specialized hyperparameter typically only train heavily when the optimizer hyperparameters are near optimum, due to the amount of expression optimizer parameters have in comparison.

## Why This Should Work (Engineering Sense)

### When this should work

Clan training is best at handling optimizer genes such as learning rate that affect how gradients are applied, and can train other alleles if the model parameters remain compatible when mutations happen. Under no circumstance can it handle mutations that change the layout of the parameter tree, as this does not preserve a common direction that is resolvable with DDP. Likewise, mutations that repurpose parameters for different jobs between rounds are unsuitab

### How this should work

This is a greedy basin following algorithm. The clan as a whole is greedy, but individual members are always exploring for advantage. 

- Cooperative gradient sharing reduces compute waste vs fully independent PBT.
- Competitive windows expose otherwise-hidden schedule effects (dropout etc.) while keeping the waste to a tolerable roar.
- Aggressive selection enforces compatibility; incompatibility is self-pruned.
- Population statistics reduce luck dominating selection: it’s less likely “many members get lucky” than “one run gets lucky.”
- Over long pretraining horizons, repeated rounds allow schedules to drift toward near-optimal while keeping training stable.

“Solving schedules” is meant in the engineering sense: for most conventional training runs, this should land within a large fraction of the best achievable result without ad-hoc tuning.

### When this will not work.

This will not work when you cannot guarentee you are starting from a valid training configuration. Tweak your defaults manually or use start-phase HPO to get something that roughly trains. Evolution will take care of the rest.

## User-Tunable Knobs (Preferred Minimal Set)

- Round length (e.g., validation every ~1000 batches)
- Duty cycle (e.g., 10–20% competitive)
Everything else should have conservative defaults and/or self-adapt (mutation rates).



## Open Empirical Questions

- How short can the competitive window be while still producing rankable signal?
- What duty cycle best preserves mutual intelligibility while allowing schedule discovery?
- How aggressive can churn be before selection becomes too noisy?
- Scaling with genome dimensionality: at what point does sparse mutation become necessary?

## Summary

Clan Training is a hybrid of cooperative gradient sharing and PBT-style selection designed for conventional training:
- *mostly cooperate* to keep efficiency high
- *sometimes compete* to reveal hyperparameter schedule effects
- *aggressively select* to maintain a coherent clan
- *self-adapt mutation rates* to avoid per-gene tuning

Target outcome: drop-in automatic schedules for common training knobs, with only round length and duty cycle as routine tuning parameters.
