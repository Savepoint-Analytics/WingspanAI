# Belief Response Mode Ablation

Status: seed-matched ablation, 2026-08-31

> **PROVISIONAL — re-run required, 2026-08-31.** This run predates the fix in
> ADR 0004. The simulator was nondeterministic across Python processes:
> `BirdCard.habitats` is a `set[Habitat]` over a `StrEnum`, and Python randomizes
> string hashing per process, so the **order** of generated legal actions varied
> between runs. Agents that select by index or break ties by first-maximum
> therefore played different games. Each cell here ran inside a single process, so
> within-cell comparisons were internally consistent, but the results are not
> reproducible and should not be quoted until re-run on the fixed simulator.
>
> The headline (potential-points leads, seat-robust in every matchup) may well
> survive; it has not yet been re-verified. The archetype findings in section 3
> have since been acted on and fixed — see `../agents/archetype_policy_fix.md`.

## Purpose

Measure whether replacing best-response opponent prediction with a probability
distribution over action families improves calibration, and whether it changes
play.

## Setup

- Seeds: 1-3, player one `random_legal_p1`, player two `net_value_response_p2`.
- `net_value_max_candidate_actions=5`, `net_value_max_opponent_response_actions=None`.
- Catalog: `data/raw/wingspan-card-list.xlsx`, full 180-bird deck, 100% power coverage.
- Replay validation enabled and passing for all games.
- **Shared `batch_id="belief_ablation"`**, arms separated by `batch_label` only.

> **Superseded mechanism, 2026-08-31.** At the time of this run, `game_id` was
> part of the RNG seed material, so the shared `batch_id` was required to keep
> the two arms seed-matched; an earlier attempt without it was invalid. ADR 0003
> has since removed `game_id` from the seed, so `random_seed` alone now
> guarantees matching and the shared `batch_id` is no longer necessary. The
> results below remain valid — they were correctly matched — but they cannot be
> reproduced by re-running, because the seed formula changed.

```bash
python - <<'PY'
from flows.simulation_batch import run_simulation_batch
for label, mode in (("belief_expected", "expected"), ("belief_best", "best")):
    run_simulation_batch(
        seeds=[1, 2, 3], batch_kind="smoke", batch_label=label,
        batch_id="belief_ablation",
        player_two_agent_kind="net_value_response",
        net_value_max_candidate_actions=5,
        net_value_max_opponent_response_actions=None,
        net_value_response_mode=mode,
        persist_postgres=False, upload_artifacts=False,
    )
PY
```

## Results

| Metric | `best` (control) | `expected` (new) |
|---|---:|---:|
| Predictions | 78 | 78 |
| Exact action-family matches | 9 | 36 |
| Exact match rate | 0.115 | **0.462** |
| Mean log loss | n/a | 1.1658 |
| Uniform-guess log loss | n/a | 1.1856 |
| Log loss improvement vs uniform | n/a | **+0.0198** |
| Mean Brier score | n/a | 0.6701 |
| Mean probability on observed family | n/a | 0.3317 |
| Observed action in candidate set | 1.000 | 1.000 |
| Avg predicted response value | 2.571 | **1.612** |
| Avg selected net margin delta | -3.942 | -2.983 |
| Avg final P2 margin | +4.67 | +4.67 |
| P2 win rate | 0.667 | 0.667 |

The control arm reports `n/a` for the probabilistic metrics because best-response
mode emits no distribution to score.

## Interpretation

**Prediction accuracy improved four-fold.** Exact match rate went from 0.115 to
0.462. The previous model was worse than the 0.167 reported in the first
calibration probe, because that probe ran against a different (unmatched) draw
sequence; on this seed-matched deck it lands at 0.115.

**The threat overstatement is confirmed and reduced.** Average predicted opponent
response value fell from 2.571 to 1.612. Best-response mode assumed a random
opponent would find their strongest reply every turn, which inflated the
subtracted term in net margin by roughly 60%.

**But the distribution is only marginally better than chance.** Log loss
improvement over a uniform guess is +0.0198 nats. That is positive, so the
belief model does carry information, but not much of it. A well-separated model
would show a substantially larger gap. This is the honest headline: calibration
improved a lot relative to the old point estimate and only slightly relative to
guessing.

**Play did not change.** Both arms produced identical final margins (+4.67) and
win rates (0.667). Shifting every candidate's response value by a similar amount
left the argmax over net margin unchanged. So at this sample size the belief
model is a better *model* without yet being a better *policy*.

## Caveats

- Three seeds, one opponent type. This is a plumbing and calibration check, not
  strategic evidence.
- The opponent is `random_legal`, which is the easiest case to predict badly and
  the least informative to predict well.
- The `random_legal` family prior was fitted on a random opponent and is being
  evaluated against a random opponent. That is optimistic; the prior needs
  refitting per opponent kind.

## Next

- Calibrate against `greedy_immediate`, `potential_points`, and archetype
  opponents through the round-robin flow.
- Refit family priors per opponent kind rather than from the single random probe.
- Investigate why the log-loss gain over uniform is so small: likely the
  `random_legal` and `card_draw` profiles are not separable on family frequency
  alone.
- Only after those, decide whether the belief model should drive blocking
  fixtures.
