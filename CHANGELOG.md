# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Fixed
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
