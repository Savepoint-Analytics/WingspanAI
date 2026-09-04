# Analysis

Reusable Python, SQL, and R analysis assets for simulation outputs.

This folder should hold analysis scripts, query files, and report-generation code. Exploratory notebooks belong in `notebooks/`; logic that the simulator depends on belongs in `src/`.

Current helpers:

- `simulation_summary.py`: flattens simulation outcomes and summarizes event/action frequency for early notebooks and smoke tests.
- `simulation_batch_comparison.py`: compares batch manifests, player-two win rates, score margins, score-category mix, by-round action mix, and timing/potential/guardrail decision telemetry from local artifacts.
- `apply_action_profile.py`: profiles legal-action generation, `GameState.model_copy(deep=True)`, safe `apply_action`, and isolated `apply_action_in_place` cost for lookahead-heavy agents.
- `round_robin_aggregate.py`: pools chunked round-robin runs into one summary from artifacts.
- `seat_effect_paired.py`: paired within-agent seat contrasts over counterbalanced round-robin artifacts.
  Every report carries an automatic leave-one-block-out stability check; pooled effects that depend on a
  single seed block are labelled FRAGILE and must not be reported as findings.
- `net_value_calibration.py`: pairs net-value response predictions with the opponent's next observed action. Reports exact-match rate plus log loss, Brier score, and improvement over a uniform guess.

## SQL Analysis Views

`sql/analysis_views.sql` is the reproducible metric layer between raw telemetry and
Python/R analysis. Raw tables stay append-only; every derived definition lives in the
SQL file so a metric has exactly one definition.

```bash
python analysis/apply_sql_views.py --list    # view names, no database needed
python analysis/apply_sql_views.py           # create or replace the views
python analysis/apply_sql_views.py --check   # probe each view for queryability
```

| View | Grain |
|---|---|
| `v_simulation_runs` | one row per run, with batch/agent/setup factors flattened |
| `v_game_player_scores` | one row per game per player, with score breakdown |
| `v_action_events` | one row per resolved action |
| `v_agent_decisions` | one row per agent decision, union of all agent families |
| `v_setup_selections` | one row per player per game setup (private information) |
| `v_agent_action_mix` | one row per game/agent/action_type |
| `v_agent_performance` | one row per agent per run-factor combination |
| `v_head_to_head_games` | one row per ordered agent pair per game |
| `v_head_to_head_summary` | one row per matchup per setup level, seat-aware |
| `v_decision_cost` | one row per agent per run, decision timing |
| `v_setup_policy_outcomes` | one row per setup policy per agent |
| `v_run_quality` | one row per run, with a `claim_grade` gate |
| `v_seat_effect` | one row per seat index per player count |
| `v_seat_effect_magnitude` | one row per player count: seat spread, the "by how much" |

Seat one always acts first (the first-player token is deterministic, ADR 0002), so
`v_seat_effect` compares each seat's win rate against its fair share of `1 / player_count`
and `v_seat_effect_magnitude` collapses that into a single spread per configuration.

Query `v_run_quality` before interpreting any batch. `v_agent_performance` and
`v_head_to_head_summary` already exclude replay-invalid games.
