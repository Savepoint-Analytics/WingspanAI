# ADR 0004: Canonical ordering for sets that influence action order

- Status: accepted
- Date: 2026-08-31
- Deciders: Alex Oswald

## Context

The project's foundational premise is deterministic, seeded, replayable
simulation. It was not holding across processes.

Running the identical seed in three separate Python processes produced three
different games:

```
run: {'player_1': 41, 'player_2':  9}
run: {'player_1': 23, 'player_2': 19}
run: {'player_1': 50, 'player_2': 17}
```

### Root cause

`BirdCard.habitats` is typed `set[Habitat]`, and `Habitat` is a `StrEnum`, so it
inherits `str.__hash__`. Python randomizes string hashing per process unless
`PYTHONHASHSEED` is fixed. Set iteration order therefore varies between
processes.

`_legal_play_bird_actions` iterated `for habitat in card.habitats` to build the
legal action list. The resulting **order** of legal actions varied per process.
Any agent whose choice depends on action order — `RandomLegalAgent` selecting an
index, or any agent breaking a score tie by taking the first maximum — then
played a different game.

Setting `PYTHONHASHSEED=0` produced identical results across processes,
confirming the diagnosis.

### Why it went unnoticed

Within a single process the hash seed is fixed, so the simulator *is*
deterministic. An earlier determinism check looped three times inside one process
and passed. The bug only appears across process boundaries — precisely the
condition under which batches are actually run.

### Impact

Every experiment run before this fix is reproducible only within the process that
produced it. Cross-run comparison of any batch executed at a different time was
unsound. This is a strictly larger problem than the `game_id` seeding issue in
ADR 0003, which affected only mid-game birdfeeder rolls; this affected the legal
action list itself.

## Decision

Sets must never determine ordering. Where a set can influence action order or any
sequence the simulator or an agent consumes, iterate it through a canonical
ordering helper.

Added `ordered_habitats(habitats) -> list[Habitat]` in `rules/base_game.py`,
which returns habitats in `Habitat` enum declaration order (forest, grassland,
wetland). Applied at every site that builds an ordered structure from
`card.habitats`:

- `rules/base_game.py::_legal_play_bird_actions` (the critical one)
- `agents/potential_points.py` open-habitat enumeration
- `agents/setup.py` habitat iteration

Set operations that are inherently order-independent — `in`, `&`, `len`,
`Counter`, `any`, `all` — were left alone.

## Alternatives considered

**Pin `PYTHONHASHSEED=0` in the environment.** Rejected: it makes correctness
depend on an environment variable that is easy to lose in CI, a notebook, a
Prefect worker, or a colleague's shell. The failure mode is silent.

**Change `habitats` to a `tuple` or ordered collection.** Reasonable and arguably
cleaner, but it changes the content schema and every construction site, and set
semantics (`&`, `in`) are genuinely wanted elsewhere. The ordering helper is a
smaller change with the same guarantee at the points that matter.

## Consequences

- Verified: four separate processes now produce identical results for a seed.
- Every artifact produced before this fix was deleted; those runs cannot be
  reproduced.
- `tests/test_base_game_rules.py::CrossProcessDeterminismTests` runs the same
  seed in two subprocesses under different `PYTHONHASHSEED` values and asserts
  identical outcomes. This is the only form of the test that can catch the bug,
  since an in-process test cannot.
- Any future field typed as a `set` of `StrEnum` or `str` must go through a
  canonical ordering helper before influencing sequence.

## Revisit if

- A profiling pass shows the ordering helper is hot; it can be precomputed on the
  content model at load time.
