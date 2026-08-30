# Analysis

Reusable Python, SQL, and R analysis assets for simulation outputs.

This folder should hold analysis scripts, query files, and report-generation code. Exploratory notebooks belong in `notebooks/`; logic that the simulator depends on belongs in `src/`.

Current helpers:

- `simulation_summary.py`: flattens simulation outcomes and summarizes event/action frequency for early notebooks and smoke tests.
- `simulation_batch_comparison.py`: compares batch manifests, player-two win rates, score margins, score-category mix, by-round action mix, and timing/potential/guardrail decision telemetry from local artifacts.
- `apply_action_profile.py`: profiles legal-action generation, `GameState.model_copy(deep=True)`, safe `apply_action`, and isolated `apply_action_in_place` cost for lookahead-heavy agents.
- `net_value_calibration.py`: pairs net-value public-belief response predictions with the opponent's next observed action for calibration reports.
