# Public-Belief Calibration

Status: first calibration harness, 2026-08-29

> **Superseded 2026-08-31.** The best-response estimator described here has been
> replaced by a Bayesian opponent-type belief model. See
> `../agents/opponent_response_belief_model.md` and
> `belief_response_mode_ablation.md` for the seed-matched comparison.

## Purpose

`NetValueOpponentResponseAgent` now uses `public_observation_belief_v0` instead of full-state opponent scoring. The next strongest move is to measure that belief model before adding carefully designed blocking fixtures.

The first calibration helper lives in `analysis/net_value_calibration.py`. It pairs each net-value decision summary with the predicted next opponent response and the opponent's next observed `action_selected` event.

## Workflow

Run a small net-value response batch:

```bash
UV_CACHE_DIR=.uv-cache uv run python - <<'PY'
from flows.simulation_batch import run_simulation_batch

run_simulation_batch(
    workbook_path="missing-workbook.xlsx",
    seeds=[1, 2, 3],
    artifact_root="artifacts",
    persist_postgres=False,
    upload_artifacts=False,
    batch_kind="smoke",
    batch_label="public_belief_calibration",
    batch_id="public_belief_calibration",
    player_two_agent_kind="net_value_response",
    net_value_max_candidate_actions=5,
    net_value_max_opponent_response_actions=None,
)
PY
```

Then score predictions against observed next actions:

```bash
UV_CACHE_DIR=.uv-cache uv run python analysis/net_value_calibration.py \
  artifacts/smoke/public_belief_calibration/public_belief_calibration/batch_manifest.json
```

## First Smoke Result

Probe settings:

- Seeds: 1-3.
- Opponent: `random_legal_p1`.
- Player two: `net_value_response`.
- `net_value_max_candidate_actions=5`.
- `net_value_max_opponent_response_actions=None`.

Summary:

| Metric | Value |
|---|---:|
| Predictions | 78 |
| Matched observations | 78 |
| Exact action-family matches | 13 |
| Exact match rate | 0.167 |
| Observed action in public candidate set | 1.000 |
| Avg observed candidate rank | 2.90 |
| Avg predicted response value | 2.514 |
| Avg selected net margin delta | -3.207 |
| Avg selected denial value | 0.249 |
| Avg final P2 margin | 32.33 |
| P2 win rate | 1.000 |

Action-family mix:

| Kind | Draw | Food | Eggs | Play |
|---|---:|---:|---:|---:|
| Predicted | 0 | 0 | 39 | 39 |
| Observed | 35 | 18 | 8 | 17 |

## Interpretation

This is a calibration harness check, not strategic evidence. The observed opponent is random legal, so exact next-action accuracy is not expected to be high for a best-response model.

Useful signals:

- The public candidate set covers the observed random action when uncapped, so the public action-family template is broad enough.
- The top response estimate is badly biased toward play-bird and lay-eggs for this opponent mix.
- Draw-card and gain-food responses need higher probability or value mass when calibrating against stochastic or low-skill opponents.
- Final margin remains strong in this tiny smoke sample, but that should not be interpreted until compared against potential-points and non-random opponents over larger fixed seeds.

## Next Calibration Questions

- Should `public_observation_belief_v0` represent a best rational response, an expected response under an opponent archetype, or a mixture over opponent types?
- Should response predictions be calibrated against action-family probabilities rather than exact top action?
- How much should random/legal opponent behaviour influence a model intended to block competent opponents?
- Which features best predict draw-card and gain-food turns: hand count, food deficit prior, visible tray quality, habitat board shape, action cubes, or round phase?

## Fixture Position

Controlled blocking fixtures should wait. Before implementing them, define:

- The strategic hypothesis.
- The public signal the agent is allowed to use.
- The expected action-family direction.
- The required simulator rule/power support.
- The batch or replay evidence needed to treat the fixture as meaningful.
