# Flows

Prefect flows for simulation batches, tournament runs, model evaluation, and report generation.

Keep orchestration here and core simulator/rules logic in `src/wingspan_ai/`.

Current flows:

- `simulation_batch.py`: runs a labelled seeded random-vs-agent batch. Player 2 can use `random_legal`, `greedy_immediate`, `potential_points`, `net_value_response`, any `archetype_*` strategy, or `monte_carlo_rollout`. It uses Prefect decorators when Prefect is installed and falls back to plain Python functions for local smoke tests. If `data/raw/wingspan-card-list.xlsx` is absent, it uses the package sample catalog. By default it writes artifacts under `artifacts/smoke/core_random_vs_greedy/<batch_id>/`.
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
