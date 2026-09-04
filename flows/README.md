# Flows

Prefect flows for simulation batches, tournament runs, model evaluation, and report generation.

Keep orchestration here and core simulator/rules logic in `src/wingspan_ai/`.

Current flows:

- `simulation_batch.py`: runs a labelled seeded random-vs-agent batch. Player 2 can use `random_legal`, `greedy_immediate`, `potential_points`, `net_value_response`, any `archetype_*` strategy, or `monte_carlo_rollout`. It uses Prefect decorators when Prefect is installed and falls back to plain Python functions for local smoke tests. If `data/raw/wingspan-card-list.xlsx` is absent, it uses the package sample catalog. By default it writes artifacts under `artifacts/smoke/core_random_vs_greedy/<batch_id>/`.
- `round_robin.py`: runs every agent lineup in every seat rotation, with `setup_policy_kind`
  as a crossed factor. Supports 2-5 players. Writes `round_robin_summary.json` plus a
  markdown report with standings, per-seat win rates, seat-effect magnitude, a `seat_robust`
  flag per matchup, and a setup-policy effect table.
- `human_vs_greedy.py`: runs an interactive terminal game with `HumanCliAgent` against the greedy baseline. It uses the same legal action generation as automated agents, so human play is feasible without a separate UI.


## Agent Variants

Pass `player_two_agent_kind="potential_points"` to compare random legal play against the expected-value greedy variant:

```python
run_simulation_batch(
    batch_label="potential_points_trial",
    player_two_agent_kind="potential_points",
)
```

The manifest records `player_two_agent_kinds` and `player_two_agent_ids` so baseline, archetype, Monte Carlo, and guardrailed batches can be compared cleanly.

Monte Carlo batches can be cost-capped with:

```python
run_simulation_batch(
    player_two_agent_kind="monte_carlo_rollout",
    monte_carlo_rollout_count=4,
    monte_carlo_rollout_depth=6,
    monte_carlo_max_decision_time_ms=250.0,
    monte_carlo_max_candidate_actions=4,
)
```

The default Monte Carlo setting uses `min_rollouts_per_action=0`, so a strict time budget may stop before every candidate receives a rollout. Unevaluated candidates receive a static fallback score and are marked in decision telemetry.

Net-value opponent-response batches can cap both own-action and opponent-response breadth:

```python
run_simulation_batch(
    player_two_agent_kind="net_value_response",
    net_value_max_candidate_actions=8,
    net_value_max_opponent_response_actions=5,
)
```

Compare local batch manifests with:

```bash
python analysis/simulation_batch_comparison.py \
  artifacts/smoke/greedy_immediate_comparison/<batch_id>/batch_manifest.json \
  artifacts/smoke/potential_points_comparison/<batch_id>/batch_manifest.json
```

## Round Robin

Agent-vs-random measures whether a policy beats noise. Agent-vs-agent measures whether
it beats another policy:

```python
from flows.round_robin import run_round_robin, format_round_robin_report

summary = run_round_robin(
    seeds=list(range(1, 31)),
    roster=["greedy_immediate", "potential_points", "net_value_response"],
    setup_policy_kinds=["control", "strategic"],
    player_count=2,          # 2-5 supported
    batch_label="round_robin_v1",
)
print(format_round_robin_report(summary))
```

### Guardrailed variants

A roster entry may carry a `guardrailed:` prefix, making an agent and its guardrailed
twin separate competitors:

```python
run_round_robin(
    roster=["potential_points", "guardrailed:potential_points", "greedy_immediate"],
    guardrail_config_path="configs/guardrails/base_heuristic.yaml",   # optional
)
```

The setup policy is applied to the base agent before wrapping, since
`GuardrailedAgent` delegates opening selection downward. The older seat-level
`guardrail_config_path` + `guardrail_seats` mechanism still works and will not
double-wrap a prefixed agent.

### Seat counterbalancing is mandatory

The simulator seats the first-listed agent in seat one deterministically; the first-player
token is never randomized at setup. Rather than randomize it, the round robin replays every
lineup once per seat rotation so each agent occupies each seat exactly once per seed. Turn-order
advantage then cancels within a matchup instead of averaging out. There is no parameter to
disable this. See `docs/decisions/0002-deterministic-first-player-with-seat-counterbalancing.md`.

Cost scales with player count: a lineup costs `player_count` runs rather than one.

Seat effects are measured, not discarded. Every summary carries a `seat_effect` block with
per-seat win rate, average score, and the spread between best and worst seat — the magnitude
answer to "does turn order matter, and by how much". Only matchups flagged `seat_robust`
should be quoted as strategy findings.

Re-render a stored summary without rerunning:

```bash
python flows/round_robin.py artifacts/experiment/round_robin_v1/<batch_id>/round_robin_summary.json
```

### Seed matching

`random_seed` is the sole reproducibility key (ADR 0003). Two games at the same
seed are byte-identical regardless of `game_id`, `batch_id`, or `batch_label`, so
cross-batch A/B comparison is valid by default:

```python
for label, mode in (("arm_a", "expected"), ("arm_b", "best")):
    run_simulation_batch(
        seeds=[1, 2, 3],
        batch_label=label,
        net_value_response_mode=mode,
    )
```

Before 2026-08-31 `game_id` was part of the RNG seed material, so arms in
different batches saw different mid-game birdfeeder rolls. Batches produced
before that date cannot be revalidated and were deleted.

## Content Filtering

Restrict the deck to mechanics a comparison is willing to depend on:

```python
run_simulation_batch(
    power_status_filter=["heuristic_resolution", "no_op_for_v1"],
    excluded_power_handler_keys=["predator_hunt"],
)
```

The manifest records retained/excluded counts, retention rate, allowed statuses, excluded
handler keys, and excluded bird names. A minimum-deck-size guard rejects filters that would
leave too few birds for a playable game.

## Guardrailed Batches

Pass a YAML guardrail config to wrap the selected player-two agent with `GuardrailedAgent`:

```python
run_simulation_batch(
    batch_label="guardrailed_greedy_trial",
    guardrail_config_path="configs/guardrails/base_heuristic.yaml",
)
```

The manifest records the guardrail config path and loaded config name. Decision telemetry from the
wrapped player includes guardrail allowed/excluded/candidate counts, rule hits, selected-action
modifiers, selected guardrail reasons, and the wrapped agent's decision summary over the narrowed
candidate set.


## Persistence

`simulation_batch.py` loads `.env` from the repository root. When PostgreSQL settings are
present, each run persists to:

- `simulation_runs`
- `games`
- `agents`
- `simulation_events`
- `game_scores`

Supported PostgreSQL variables:

- `SAVEPOINT_DATABASE_URL` or `DATABASE_URL`; or
- `SAVEPOINT_PG_HOST`, `SAVEPOINT_PG_PORT`, `SAVEPOINT_PG_USER`, `SAVEPOINT_PG_PWD`, and optional `SAVEPOINT_PG_DB`.

If `SAVEPOINT_PG_DB` is not set, the database name defaults to `SAVEPOINT_PG_USER`.

When MinIO/S3 settings are present and local artifacts are enabled, the artifact directory is
uploaded to object storage. Local and object-storage paths use the same workload namespace:

```text
<root-or-prefix>/<batch_kind>/<batch_label>/<batch_id>/
  batch_manifest.json
  seed_<seed>/
```

`batch_kind` must be `smoke`, `experiment`, or `production`. Every flow invocation receives a
unique `batch_id` unless one is supplied. Each game is replay-validated before artifacts,
PostgreSQL rows, or MinIO objects are written by default. The batch manifest records seeds,
outcomes, ruleset IDs, replay-validation status, scoring/power audit coverage, event counts, local
artifact paths, PostgreSQL insertion results, and uploaded object URIs. Game IDs are batch-scoped
so rerunning a seed cannot overwrite an earlier game's summary row.

Object storage is the durable copy of an artifact; the local `artifacts/` tree is a working cache
that may be pruned (ADR 0005). `run_round_robin` used to hardcode `upload_artifacts=False`, which
overrode the auto-detect above and meant round robins — nearly all of the project's data — never
uploaded. It now defaults to `None` and inherits the same behaviour as `run_simulation_batch`.
Use `scripts/backfill_artifacts_to_object_storage.py` to mirror an existing local tree; it skips
objects whose key and size already match, so an interrupted run can simply be repeated.

Every manifest records `code_provenance`: the git commit, branch, and whether the tree was dirty.
`reproducible` is false for a dirty tree, meaning the run cannot be recreated from version control
and its artifacts must be preserved rather than regenerated.

Supported variables:

- `SAVEPOINT_LOCAL_MINIO_USR`
- `SAVEPOINT_LOCAL_MINIO_PWD`
- optional `SAVEPOINT_LOCAL_MINIO_ENDPOINT` (default `http://127.0.0.1:9000`)
- optional `SAVEPOINT_LOCAL_MINIO_BUCKET` (default `wingspan-ai`)
- optional `SAVEPOINT_LOCAL_MINIO_PREFIX` (default `wingspan-ai/simulations`)

Install optional runtime dependencies before using these paths:

```bash
UV_CACHE_DIR=.uv-cache uv run --extra db --extra storage python flows/simulation_batch.py
```

For local artifact-only smoke tests, disable persistence explicitly:

```python
run_simulation_batch(persist_postgres=False, upload_artifacts=False)
```



Replay validation can be disabled only for debugging malformed traces:

```python
run_simulation_batch(require_valid_replay=False, persist_postgres=False, upload_artifacts=False)
```

Run the opt-in live persistence regression against the configured PostgreSQL and MinIO services:

```bash
RUN_DB_INTEGRATION=1 UV_CACHE_DIR=.uv-cache uv run --extra db --extra storage \
  python -m pytest tests/test_persistence_integration.py
```

The test writes one labelled smoke run to both services and verifies the database rows, four game
artifacts, and batch manifest. It is skipped during the normal unit-test suite.
