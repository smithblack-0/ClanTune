# Clan Training User API Specification

## Overview
Clan Training provides population-based hyperparameter schedule adaptation with minimal user intervention. The API is designed to integrate cleanly with existing PyTorch training loops and frameworks like PyTorch Lightning.

## Core API

### Initialization
```python
clan = Clan(
    genome_config={...},  # Dict of hyperparameter genes to evolve
    round_length=1000,     # Steps per round
    duty_cycle=0.15,       # Fraction of round in competitive phase
    population_size=8,     # Number of clan members
)
```

### Data Loading
```python
# Clan loader handles phase-appropriate data distribution
loader = clan.loader(train_dataset, batch_size=32)
```

The clan loader automatically:
- Provides sharded data during cooperative phases
- Provides common data windows during competitive phases

### Training Loop (Pure PyTorch, optimizer changes only)

```python
# Setup
model = MyModel()
optimizer = AdamW(model.parameters(), lr=1e-5, weight_decay=0.01)
loader = clan_loader(train_dataset, batch_size=32, ...)

clan = Clan(
    model=model,  # Model reference for sync control
    optimizer=optimizer,  # Optimizer reference for hyperparameter application
    round_length=1000,  # Steps per round
    duty_cycle=0.15,  # Fraction of round in competitive phase
    autobind=["adamw"]  # Automatically bind all AdamW hyperparameters
)

# Autobind creates genes for: lr, weight_decay, betas/0, betas/1, eps
# Equivalent to manually calling:
# clan.add_genome(name="lr", type="optimizer")
# clan.add_genome(name="weight_decay", type="optimizer")
# clan.add_genome(name="betas/0", type="optimizer")
# clan.add_genome(name="betas/1", type="optimizer")

# Start a round, get this rank's member
member = clan.round()

# Training loop
for batch, labels in loader:
    logits = member.model(batch)
    loss = cross_entropy(logits, labels)

    # Wrap only the backward pass for gradient sync control
    with member.sync_context():
        loss.backward()

    member.optimizer.step()
    member.optimizer.zero_grad()
    member.step()
    9
    if member.done:
        validation_loss = get_validation_loss(member.model, val_loader)
        clan.step(validation_loss)
        member = clan.round()  # Start next round, get new member
```

### Training Loop (Pure PyTorch, gradient accumulation evolution)

```python
# Setup
model = MyModel()
optimizer = AdamW(model.parameters(), lr=1e-5, weight_decay=0.01)
loader = clan_loader(train_dataset, batch_size=32, ...)

clan = Clan(
    model=model,
    optimizer=optimizer,
    round_length=1000,
    duty_cycle=0.15,
    autobind=["adamw", "gradient_accumulation"]  # Bind optimizer + grad accum
)

# Autobind creates:
# - AdamW genes: lr, weight_decay, betas/0, betas/1, eps
# - Gradient accumulation gene: num_grad_accum (specialized type)

# Start a round, get this rank's member
member = clan.round()

# Training loop with gradient accumulation
accum_steps = 0
for batch, labels in loader:
    logits = member.model(batch)
    loss = cross_entropy(logits, labels)

    # Get current accumulation count from genome
    num_grad_accum = member.get_gene("num_grad_accum")
    loss = loss / num_grad_accum

    with member.sync_context():
        loss.backward()

    accum_steps += 1
    if accum_steps >= num_grad_accum:
        member.optimizer.step()
        member.optimizer.zero_grad()
        accum_steps = 0

    member.step()

    if member.done:
        validation_loss = get_validation_loss(member.model, val_loader)
        clan.step(validation_loss)
        member = clan.round()
```

### Lightning Integration

```python
class ClanLightningModule(LightningModule):
    def __init__(self):
        super().__init__()
        self.model = MyModel()
        self.clan = Clan(
            model=self.model,
            optimizer=self.configure_optimizers(),
            autobind=["adamw"]
        )
        self.member = self.clan.round()

    def backward(self, loss, *args, **kwargs):
        # Override backward hook to wrap with clan sync
        with self.member.sync_context():
            super().backward(loss, *args, **kwargs)

    def on_train_batch_end(self, outputs, batch, batch_idx):
        self.member.step()

        if self.member.done:
            # Trigger validation and selection
            val_loss = self.trainer.validate(self)[0]['val_loss']
            self.clan.step(val_loss)
            self.member = self.clan.round()
```

## API Components

### `Clan`
Main orchestrator for population management and selection.

### `Member`
Represents this rank's clan member (model + genome pairing) for the current round.

## Framework Decomposition

The API is designed to decompose cleanly:

1. **Pure PyTorch**: User controls the full loop, explicitly uses `round.sync(model)` around `backward()`
2. **PyTorch Lightning**: User overrides `backward()` hook to inject `round.sync()`
3. **Other frameworks**: Similar pattern - find the backward hook and wrap it

Key insight: Only the backward pass needs wrapping, not the entire training step. This makes integration straightforward across frameworks.

## Design Principles

- **Minimal intervention**: User keeps control of training loop structure
- **Explicit over implicit**: Clear what's happening at each step
- **Framework agnostic**: Core API works everywhere, integration via standard hooks
- **Progressive disclosure**: Simple cases are simple, complexity only when needed