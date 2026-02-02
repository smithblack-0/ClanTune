# ClanTune: Cooperative Gradient Sharing for Hyperparameter Schedule Adaptation

ClanTune implements Clan Training, a hybrid approach combining Population Based Training (PBT) with cooperative gradient sharing. It automatically discovers near-optimal hyperparameter schedules (learning rate, weight decay, dropout, etc.) without the compute waste of traditional PBT.

## The Problem

Standard PBT explores hyperparameter schedules effectively but wastes compute: with N workers, you spend N× compute exploring but typically keep only one final checkpoint. This makes it impractical for most conventional training runs.

## The Solution

Clan Training alternates between two phases:

1. **Cooperative phase (80-90% of training):** Members share gradients via DDP while applying different optimizer hyperparameters. This maintains efficiency while allowing optimizer schedules to diverge and compete.

2. **Competitive phase (10-20% of training):** Members train independently on common data to expose differences in specialized hyperparameters (dropout, batch size) that don't express during gradient sharing.

Between rounds, aggressive selection prunes poor performers and clones strong ones. The emergent stabilizer: incompatible members (whose gradients aren't mutually intelligible) fall behind and get pruned. The population self-organizes into a "clan" where cooperation works.

## Key Features

- **Compute-efficient**: Most training uses cooperative gradient sharing
- **Automatic schedules**: Near-optimal learning rate, weight decay, dropout, and other hyperparameter schedules emerge through evolution
- **Self-adaptive mutation**: Mutation parameters themselves evolve, reducing manual tuning
- **Minimal configuration**: Only round length and duty cycle need tuning
- **Built on PyTorch DDP**: Production-ready distributed training

## Installation

```bash
pip install clan-tune
```

For development:

```bash
git clone https://github.com/smithblack-0/ClanTune.git
cd ClanTune
pip install -e .[dev]
```

## Quick Start

```python
# Example coming soon
```

## How It Works

1. **Cooperative gradient sharing** (most of training): Clan members share gradients like DDP but apply different optimizer hyperparameters. Differences in learning rate, weight decay, etc. create measurable performance advantages that compound over many steps.

2. **Competitive independent training** (short windows): Members train independently on common data, allowing specialized hyperparameters (dropout, batch size) to express and become rankable.

3. **Aggressive selection**: Poor performers are pruned, strong performers are cloned and mutated. Mutation parameters themselves evolve through metalearning.

4. **Compatibility pressure**: Members that drift into regions where shared gradients aren't helpful fall behind and get pruned. The clan self-organizes around mutually intelligible gradient directions.

## Development

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -e .[dev]
```

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
# Format code
python format_code.py

# Or manually:
black src/ tests/
ruff check src/ tests/
```

## Research Status

This is an active research project. See [proposal.md](proposal.md) for detailed design philosophy and research questions.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Citation

```bibtex
@software{clan_tune,
  title = {ClanTune: Cooperative Gradient Sharing for Hyperparameter Schedule Adaptation},
  author = {O'Quinn, Christopher},
  year = {2026},
  url = {https://github.com/smithblack-0/ClanTune}
}
```
