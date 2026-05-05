# Flows

Prefect flows for simulation batches, tournament runs, model evaluation, and report generation.

Keep orchestration here and core simulator/rules logic in `src/wingspan_ai/`.

Current flows:

- `simulation_batch.py`: runs a small seeded random-vs-greedy batch. It uses Prefect decorators when Prefect is installed and falls back to plain Python functions for local smoke tests. If `data/raw/wingspan-card-list.xlsx` is absent, it uses the package sample catalog.
