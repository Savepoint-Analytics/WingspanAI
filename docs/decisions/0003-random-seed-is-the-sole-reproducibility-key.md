# ADR 0003: `random_seed` is the sole reproducibility key

- Status: accepted
- Date: 2026-08-31
- Deciders: Alex Oswald

## Context

`game_id` was part of the RNG seed material in `_roll_birdfeeder_for_state`:

```python
seed = f"{state.random_seed}:{state.game_id}:{global_turn_number}:{salt}"
```

`game_id` is built as `f"{batch_id}_seed_{random_seed}"`, and `batch_id` defaults
to a timestamp plus a UUID fragment. Two batches run with identical numeric seeds
therefore diverged, because every mid-game birdfeeder roll was salted with a
different batch identifier.

Verified before the change: seed 1 with `game_id=batchA_seed_1` scored 35-43,
and the same seed with `game_id=batchB_seed_1` scored 22-45.

### Scope of the divergence

Narrower than first assumed. `game_id` entered RNG in exactly one function.
Everything seeded during `setup_base_game` uses `random.Random(random_seed)`
alone, so at a fixed seed the following were already identical across batch IDs:

- bird deck order
- opening hands and bonus cards
- bird tray
- round goals
- the initial birdfeeder roll

Only **mid-game** stochastic events diverged: birdfeeder rerolls, pink and
each-player food gains, and predator hunts — everything routed through
`_roll_birdfeeder_for_state`.

### Consequence

Any A/B comparison run as two separate batches was not seed-matched. This
affected the 10-seed baseline matrix and the first attempt at the belief-model
ablation, both of which were re-run or caveated.

## Decision

Remove `game_id` from the seed string:

```python
seed = f"{state.random_seed}:{state.round_state.global_turn_number}:{salt}"
```

`random_seed` becomes the sole reproducibility key. `game_id` returns to being
purely a storage key, used for artifact paths, database rows, and object keys.

## Alternatives considered

**Add an explicit `rng_namespace` field to `GameState`,** defaulting to `game_id`
and settable independently. Rejected: it has the *same* blast radius, because
adding a field changes `model_dump` and therefore every `state_hash`, while also
adding a concept the project would carry forever.

**Leave it and document the constraint.** Rejected: the round-robin flow already
shares one `batch_id` across cells, but that leaves a permanent footgun for
ad-hoc analysis, and it would force the seat-order study to run as one
indivisible batch rather than allowing player counts to be added incrementally.

## Blast radius

Smaller than it appears. `state_hash` hashes the full `GameState` including
`game_id`, so stored replay hashes were **never** portable across batch IDs. The
change makes previously stored traces non-revalidatable, but those are
regenerable smoke and experiment artifacts under a gitignored `artifacts/`
directory. Nothing that previously worked stops working.

No collision risk is introduced: seeds already differ per game within a batch,
`global_turn_number` separates turns, and salts carry `player_id` where two
draws could otherwise coincide.

## Consequences

- Two games at the same `random_seed` are now byte-identical regardless of
  `game_id`, batch, or label. Verified across three different game IDs.
- Cross-batch A/B comparison is valid by default. Sharing a `batch_id` is no
  longer required for seed matching, though `flows/round_robin.py` still does it
  because per-cell storage separation is useful anyway.
- Existing artifacts predating 2026-08-31 cannot be revalidated and were deleted.
- `tests/test_base_game_rules.py::SeedNamespaceTests` guards the invariant: the
  recorded seed material must not contain the game ID, identical seeds must
  produce identical stochastic draws across game IDs, and different seeds must
  still diverge.

## Revisit if

- A future feature genuinely needs per-game RNG independence at a fixed seed,
  in which case add an explicit `rng_namespace` rather than reusing `game_id`.
