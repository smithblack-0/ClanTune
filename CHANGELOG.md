# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- AbstractAllele base class with registry-based serialization dispatch
- Comprehensive test suite for AbstractAllele (40 black-box tests)
- Tree walking stubs (walk_tree, update_tree) for future implementation

### Changed
- Updated CLAUDE.md with session bootup checklist (documentation check, release check with analysis and reasoning)
- Updated CLAUDE.md with versioning workflow (Unreleased pattern, semantic versioning rules)
- Release proposals now include analysis and reasoning instead of just asking "should I release?"
- Added git history check to catch commits not reflected in CHANGELOG during release proposals

## [0.1.0] - 2026-02-02

### Added
- Initial project structure
- Core genetics system (alleles, genome, expression)
- Clan infrastructure (individual, state, tree utilities, communication)
- Project documentation and specifications
- Development tooling (black, ruff, pytest)
