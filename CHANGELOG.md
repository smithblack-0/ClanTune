# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Concrete mutation strategies (src/clan_tune/genetics/mutation_strategies.py): GaussianMutation, CauchyMutation, DifferentialEvolution, UniformMutation with metalearning allele types (GaussianStd, GaussianMutationChance, CauchyScale, CauchyMutationChance, DifferentialEvolutionF, UniformMutationChance)
- Test suite for concrete mutation strategies (59 tests)
- AbstractMutationStrategy refactored: handle_mutating now receives allele_population (List[AbstractAllele], parallel alleles at current tree position) instead of population (List[Genome])
- Concrete crossbreeding strategies (src/clan_tune/genetics/crossbreeding_strategies.py): WeightedAverage, DominantParent, SimulatedBinaryCrossover, StochasticCrossover
- SBXEta allele subclass (extends FloatAllele, domain [2.0, 30.0]) for SBX metalearning support
- Test suite for concrete crossbreeding strategies (38 tests)
- TopN ancestry wrapper strategy: delegates to any ancestry strategy, clips to top N by probability (tie-break by index), renormalizes — required pairing for SBX
- Test suite for TopN (10 tests)

### Changed
- Fixed crossbreeding_strategies.md to use allele_population parameter name (was incorrectly using sources, inconsistent with the v0.4.0 rename)
- Reorganized strategy tests into abstract/ and concrete/ subdirectories under tests/genetics/strategies/
- TournamentSelection parameter renamed num_parents → num_tournaments (semantically distinct: counts tournament rounds, not parents)
- RankSelection: removed num_parents parameter; now assigns non-zero probability to all genomes (use TopN wrapper to restrict count)
- BoltzmannSelection: removed num_parents parameter; now assigns non-zero probability to all genomes (use TopN wrapper to restrict count)
- SimulatedBinaryCrossover: validation changed from "at least 2" to "exactly 2 non-zero parents"; removed internal top-2 selection logic (caller must supply exactly 2 via TopN)
- ancestry_strategies.md and crossbreeding_strategies.md updated to reflect declare-interpret separation: ancestry declares full distribution, crossbreeding interprets it

### Removed

### Fixed
- Ancestry probabilities now enforced to sum to 1.0 in AbstractAncestryStrategy.apply_strategy (spec said "not enforced", should have been required)
- GaussianMutation/CauchyMutation now raise TypeError on unsupported allele types (was silently returning allele unchanged)
- GaussianStd/CauchyScale with_overrides now preserve original domain bounds (was rescaling domain to new value, causing positive feedback loop)
- abstract_strategies.md: removed stale update_alleles reference from delegation section, fixed ancestry normalization language
- mutation_strategies.md: "skip silently" → "raise TypeError" for unsupported types, domain descriptions clarified as static after init
- AbstractMutationStrategy.handle_mutating parameter renamed population → allele_population for consistency with spec and concrete classes
- _DeterministicGaussian/_DeterministicCauchy test subclasses now override _random() for deterministic mutation_chance path testing

## [0.4.0] - 2026-02-10

### Added
- Abstract strategy classes (src/clan_tune/genetics/abstract_strategies.py) providing hook-based evolution framework
- AbstractStrategy base class with setup_genome and handle_setup infrastructure for metalearning; uses ABC/abstractmethod for enforcement
- AbstractAncestryStrategy with parent selection orchestration and validation
- AbstractCrossbreedingStrategy with allele synthesis delegation to genome utilities
- AbstractMutationStrategy with population/ancestry context injection via closures
- StrategyOrchestrator for composing ancestry, crossbreeding, and mutation strategies; owns UUID/fitness/parents on final offspring
- Test suite for abstract strategies (50 tests across 5 test files)
- Concrete strategy specifications (documents/mutation_strategies.md): GaussianMutation, CauchyMutation, DifferentialEvolution, UniformMutation
- Concrete strategy specifications (documents/ancestry_strategies.md): TournamentSelection, EliteBreeds, RankSelection, BoltzmannSelection
- Concrete strategy specifications (documents/crossbreeding_strategies.md): WeightedAverage, DominantParent, SimulatedBinaryCrossover, StochasticCrossover
- Documentation for each strategy includes algorithm descriptions, parameter guidance, metalearning support, usage recommendations, and strategy combination advice

### Changed
- Updated CLAUDE.md reference directory to include new strategy specification documents
- Added WalkHandler, SynthesizeHandler, UpdateHandler Protocol classes to genome.py to properly express required positional args and **kwargs in handler type contracts
- Updated all four handler type hints in genome.py to use Protocols (walk_genome_alleles, synthesize_genomes, update_alleles, synthesize_new_alleles)
- Renamed parameter sources → allele_population throughout genome.py, abstract_strategies.py, and all test doubles to enforce the invariant that List[AbstractAllele] is always called allele_population
- Fixed genome.md handler description examples to consistently use allele_population for List[AbstractAllele] parameters
- Concrete strategy specifications revised for correctness: added type-specific mutation contracts, unambiguous throw behaviors, Constructor sections, metalearning specifications, and type support matrix for crossbreeding
- abstract_strategies.md: removed with_ancestry() from crossbreeding contract, removed parents-preservation from mutation contract, removed UUID common-patterns note — UUID/fitness/parents are documented as StrategyOrchestrator-only responsibilities
- abstract_strategies.py: removed with_ancestry() from AbstractCrossbreedingStrategy.apply_strategy and parents-preservation block from AbstractMutationStrategy.apply_strategy to match corrected spec ownership
- Tests cleaned to only assert responsibilities contracted by the class under test: removed UUID, fitness, and ancestry assertions from individual strategy tests (these belong in orchestrator tests only)

### Fixed
- **Methodology failure and recovery:** An LLM implementing genome blindly fixed breaking tests in abstract_strategies rather than stopping at the module boundary. This corrupted both genome spec consistency and abstract_strategies simultaneously. Recovery required redoing genome correctly (spec→code→tests→audit→commit as a single unit), then abstract_strategies as a separate unit — approximately 3x the work that correct discipline would have required. Root cause: touching files outside the current unit of work before that unit was finished and committed. The correct discipline is one module at a time — spec first, then code and tests in alignment, audit, commit — accepting that other modules break in the meantime rather than reaching out to fix them prematurely.

### Fixed

## [0.3.0] - 2026-02-08

### Added
- Genetics lifecycle vision document (documents/genetics_lifecycle.md) describing system architecture, component responsibilities, and evolution flow
- AbstractAllele.synthesize_trees() method as thin wrapper for synthesize_allele_trees utility
- CanMutateFilter and CanCrossbreedFilter callable predicate classes for tree filtration
- Test suites for CanMutateFilter and CanCrossbreedFilter (14 tests)
- Genome class foundation (src/clan_tune/genetics/genome.py) with string-based type dispatch
- Genome orchestrator methods: add_hyperparameter, as_hyperparameters, set_fitness, get_fitness
- Genome core methods: with_overrides for rebuilding with preserved fields
- Genome serialization/deserialization with recursive allele handling
- Genome module utilities: walk_genome_alleles and synthesize_genomes with handler adaptation
- Genome strategy support methods: with_alleles, with_ancestry, update_alleles, synthesize_new_alleles
- Test suite for Genome construction and orchestrator methods (32 tests)
- Test suite for Genome serialization (15 tests)
- Test suite for Genome module utilities (23 tests)
- Test suite for Genome strategy support methods (26 tests)
- Test suite for Genome integration tests (14 tests covering multi-hyperparameter, nested alleles, error handling, workflows)

### Changed
- Migrated tree walking utilities from boolean flags to predicate-based filtration
- walk_allele_trees and synthesize_allele_trees now accept predicate parameter instead of include_can_mutate/include_can_crossbreed

### Removed
- _should_include_node helper function (replaced by filter classes)
- Boolean flag parameters from tree walking utilities

## [0.2.0] - 2026-02-05

### Added
- AbstractAllele base class with registry-based serialization dispatch
- Comprehensive test suite for AbstractAllele (38 black-box tests)
- Tree walking utilities (walk_allele_trees, synthesize_allele_trees)
- Helper functions for tree walking: _validate_parallel_types, _flatten_metadata, _should_include_node, _collect_metadata_keys
- Comprehensive test suite for tree walking (22 integration tests, 24 helper tests)
- Organized test directory structure (tests/genetics/alleles/)
- Five concrete allele types:
  - FloatAllele: linear float with min/max clamping, type-narrowed value property
  - IntAllele: float-backed integer with Union[int, float] API, exposes rounded int via value property and underlying float via raw_value property
  - LogFloatAllele: log-space float with min > 0 validation and clamping
  - BoolAllele: boolean flags with hardcoded {True, False} domain
  - StringAllele: discrete string choices with required domain set
- Comprehensive black-box test suite for all concrete allele types (54 tests, focusing on type-specific behavior only)
- AbstractAllele.flatten() and unflatten() methods for metadata flattening/restoration
- Test suite for flatten/unflatten methods (20 black-box tests)

### Removed
- Private helper _flatten_metadata() (replaced by public AbstractAllele.flatten() method)

### Fixed
- Rebuilt synthesize_allele_trees to match specification (Allele.md lines 89-118)
  - Added template_tree parameter, handler signature now (template, sources) → Allele
  - Added schema validation, uses flatten/unflatten for metadata handling
  - Added _validate_schemas_match helper function with test suite (5 tests)
  - Updated walk_allele_trees to use flatten() method
  - Updated 12 tests to match new contracts
- Rebuilt walk_tree and update_tree instance methods to match specification (Allele.md lines 121-136)
  - walk_tree handler now receives single allele (was: list of alleles)
  - update_tree handler now receives single allele, returns allele (was: list → value)
  - Both methods adapt user handler to underlying utility API
  - Re-added _walker and _updater test injection parameters
  - Updated 7 tests to match new handler signatures (4 in test_tree_walking.py, 3 in test_abstract_allele.py)
- Removed obsolete TestFlattenMetadata test class (6 tests for deleted _flatten_metadata helper)
- Removed black-box testing violations (schema coupling in serialization tests)
- Test fixtures now use public properties instead of private fields
- Replaced registry inspection tests with behavior-based round-trip tests
- Serialization tests validate contracts via round-trip preservation, not schema structure
- FloatAllele domain normalization (always has "min" and "max" keys, None for unbounded)
- IntAllele float backing implementation (stores float in superclass, exposes rounded int via property)

### Changed
- Updated CLAUDE.md with session bootup checklist (documentation check, release check with analysis and reasoning)
- Updated CLAUDE.md with versioning workflow (Unreleased pattern, semantic versioning rules)
- Release proposals now include analysis and reasoning instead of just asking "should I release?"
- Added git history check to catch commits not reflected in CHANGELOG during release proposals
- Rewrote CLAUDE.md testing guide with black box testing philosophy (design forcing function)
- Added encapsulation pattern for rare controlled violations of black box rules (stateless only)
- Clarified private field/method rules and requirements for testing internal utilities via behavior
- IntAllele constructor and with_value now accept Union[int, float] for cleaner API
- BoolAllele domain hardcoded to {True, False} (removed unnecessary parameter)

## [0.1.0] - 2026-02-02

### Added
- Initial project structure
- Core genetics system (alleles, genome, expression)
- Clan infrastructure (individual, state, tree utilities, communication)
- Project documentation and specifications
- Development tooling (black, ruff, pytest)
