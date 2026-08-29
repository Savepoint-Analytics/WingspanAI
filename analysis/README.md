# Analysis

Reusable Python, SQL, and R analysis assets for simulation outputs.

This folder should hold analysis scripts, query files, and report-generation code. Exploratory notebooks belong in `notebooks/`; logic that the simulator depends on belongs in `src/`.

Current helpers:

- `simulation_summary.py`: flattens simulation outcomes and summarizes event/action frequency for early notebooks and smoke tests.
- `simulation_batch_comparison.py`: compares batch manifests, player-two win rates, score margins, score-category mix, by-round action mix, and timing/potential/guardrail decision telemetry from local artifacts.
- `apply_action_profile.py`: profiles legal-action generation, `GameState.model_copy(deep=True)`, and full `apply_action` cost for lookahead-heavy agents.
