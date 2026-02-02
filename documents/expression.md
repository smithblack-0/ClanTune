# GenomeExpression Spec

## Overview

Stateless, registry-based dispatch system for genome expression. Sits between Genome and Member — Genome doesn't know about expression, Member doesn't know about mode-dependent resolution.

Owns nothing. Receives Genome and communicator as needed.

Same pattern as TreeNodeHandler: a base class that owns the registry and dispatches, concrete subclasses handle the mode-specific work.

## Metadata

Allele keys in Genome are JSON strings carrying expression metadata:

- `path`: The patch target path in the State object tree
- `is_cooperative`: Whether this allele is expressed during cooperative phase
- `is_competitive`: Whether this allele is expressed during competitive phase
- `is_patchable`: Whether this allele is a valid patch target

## Base Class: GenomeExpression

```
_registry: list                          # auto-populated via __init_subclass__
__init_subclass__                        # registers each concrete subclass

set_allele(genome, path, is_cooperative, is_competitive, is_patchable, **genome_kwargs) -> None
    # Owns the metadata schema. path, is_cooperative, is_competitive,
    # is_patchable are required — this is where valid schema entries are defined.
    # Constructs the JSON key from the metadata fields, passes **genome_kwargs
    # through to Genome for allele creation. Uniform for all types —
    # no dispatch needed here.

express(genome, communicator, mode) -> (patch_dict, cache_dict)
    # Draws alleles via genome.to_dict(). Deserializes each JSON key to
    # extract metadata. Filters to is_patchable == True. For each remaining
    # allele, finds the first handler whose _predicate matches mode and
    # calls _express with the parsed metadata. Assembles patch_dict and
    # cache_dict from the per-allele results.
```

## Subclass Contract

```
_predicate(mode) -> bool
    # Does this handler own this mode?

_express(value, path, is_cooperative, is_competitive, communicator) -> (patch_entry, cache_entry)
    # Given a single allele's value and parsed metadata, resolve it for the
    # current mode. Returns one entry for each dict. Responsible for
    # gathering/averaging if needed (e.g. specialized alleles in cooperative mode).
```

## Concrete Handlers (at time of writing)

**CooperativeExpression** — matches `mode == "cooperative"`. Alleles with `is_cooperative == True` are expressed directly. Alleles with only `is_competitive == True` are gathered via communicator and averaged across the clan.

**CompetitiveExpression** — matches `mode == "competitive"`. Alleles with `is_competitive == True` are expressed directly. Alleles with only `is_cooperative == True` are gathered via communicator and averaged across the clan.

**AllExpression** — matches `mode == "all"`. All alleles expressed directly. No gathering needed.