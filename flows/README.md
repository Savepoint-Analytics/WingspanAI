# Flows

Prefect flows for simulation batches, tournament runs, model evaluation, and report generation.

Keep orchestration here and core simulator/rules logic in `src/wingspan_ai/`.

Current flows:

- `simulation_batch.py`: runs a labelled seeded random-vs-greedy batch. It uses Prefect decorators when Prefect is installed and falls back to plain Python functions for local smoke tests. If `data/raw/wingspan-card-list.xlsx` is absent, it uses the package sample catalog. By default it writes artifacts under `artifacts/smoke/core_random_vs_greedy/<batch_id>/`.
- `human_vs_greedy.py`: runs an interactive terminal game with `HumanCliAgent` against the greedy baseline. It uses the same legal action generation as automated agents, so human play is feasible without a separate UI.


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
unique `batch_id` unless one is supplied. The batch manifest records seeds, outcomes, ruleset IDs,
event counts, local artifact paths, PostgreSQL insertion results, and uploaded object URIs. Game
IDs are batch-scoped so rerunning a seed cannot overwrite an earlier game's summary row.

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


Run the opt-in live persistence regression against the configured PostgreSQL and MinIO services:

```bash
RUN_DB_INTEGRATION=1 UV_CACHE_DIR=.uv-cache uv run --extra db --extra storage \
  python -m pytest tests/test_persistence_integration.py
```

The test writes one labelled smoke run to both services and verifies the database rows, four game
artifacts, and batch manifest. It is skipped during the normal unit-test suite.
