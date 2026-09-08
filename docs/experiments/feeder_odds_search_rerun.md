# Feeder Odds, Re-Run on the Searching Agent

Status: complete, 2026-09-07. **Still a null. The 2026-09-04 result was not an
artefact of the dead search.**
Code: `4506bdf` (clean tree; every manifest records it)
Artifacts: `artifacts/rr_feeder_odds_off/`, baseline `artifacts/rr_food_cand6/`

## Why this experiment

Three valuation improvements measured as nulls
([mat_scaling_ablation.md](mat_scaling_ablation.md),
[round_robin_v5_feeder_odds.md](round_robin_v5_feeder_odds.md),
[resource_spending_ablation.md](resource_spending_ablation.md)). Then
`search_depth` turned out to be a dead parameter: every one of those nulls was
measured on an agent whose "endgame search" stopped after one ply
([search_depth_experiment.md](search_depth_experiment.md)). That reopened the
question. A valuation term that cannot change a one-ply decision might still
change which of a thousand three-ply continuations looks best, so the nulls were
downgraded from settled results to open questions.

This re-runs the cheapest of the three on today's agent: depth 3, searching
every turn, four determinization samples.

## What is different from the 2026-09-04 run

The original ablation flipped `feeder_odds.VALUE_FEEDER_ODDS`, a module global
consumed by the whole roster. Every agent's food valuation changed at once, so
"off" was a different tournament, not a different `potential_points`.

This run adds a `potential_points`-local `VALUE_FEEDER_ODDS`, alongside the
existing `VALUE_HABITAT_YIELD` switch. It guards exactly one term: the
die-availability multiplier applied to feeder-drawing bird powers in
`_registered_food_power_value`. With it off, such a power is worth 0.85 (food
the hand needs) or 0.25 (food it does not), with no weighting by how likely the
birdfeeder is to show that die. Opponents are untouched, and so is the greedy
opponent model inside the search — so the contrast isolates what the term
contributes to *this agent's planning*.

The corrected six-face die stays active in both arms. It is a rules fix, not a
variable.

Module-level switches never reach the manifest, so `agent_decision_summary` now
carries an `ablation_flags` payload. Every one of the 2,080 decisions in this
arm records `value_feeder_odds: false`, and every one of the baseline's records
`true`; that is what proves which arm a game belongs to.

## Design

Reduced paired design, 80 games: the four two-agent lineups containing
`potential_points`, both rotations, seeds 1-10, paired by (lineup, rotation,
seed) with `analysis/arm_contrast.py`.

The baseline is `rr_food_cand6`, not `rr_reroll_fix`, so that both arms share
`search_food_candidates=6`
([search_food_candidates.md](search_food_candidates.md)). Both arms ran
concurrently from the same worktree at `4506bdf`; all manifests are clean.

## Result: null, again

| Metric | on (baseline) | off | Δ | p |
|---|---:|---:|---:|---:|
| Avg score | 78.10 | 78.59 | +0.49 | 0.470 |
| Win rate | 0.863 | 0.850 | -0.013 | 0.656 |

Identical outcomes: 48 of 80. By opponent: `net_value_response` +1.60,
`archetype_engine_builder` +0.55, `greedy_immediate` +0.05,
`archetype_bonus_card_focus` -0.25; none significant at n=20.

Score composition moves within noise — bird -0.79, egg +0.60, tucked +0.35,
cached food +0.32 — and the action mix is flat (`gain_food` 20.6% in both arms).
Deleting the term is, if anything, marginally *better*, which is the signature
of a term that is adding variance rather than information.

## What this settles

The feeder-odds null is **not** conditional on the dead search. The term did
nothing to a one-ply agent and it does nothing to a three-ply determinized agent
that searches every turn and changes 40% of its game outcomes when its planning
is perturbed. Two of the three nulls' reinterpretation can now be narrowed: for
this term, "measured on a broken agent" is no longer an available explanation.

The standing reading holds and gets stronger. What moved this agent was
**planning** — depth, coverage, horizon, +10.4 leak-free — and the horizon
result showed the evaluator's *structure* matters a great deal (-12.0 for the
wrong horizon). What has never moved it is **refining the numbers inside** that
evaluator. Fidelity of food valuation is not the constraint; what the agent does
with a valuation is.

`VALUE_FEEDER_ODDS` stays `True` in both modules, on the same grounds as 2026-09-04:
the term is more faithful than what it replaced and costs nothing. Nothing
downstream should describe it as an improvement.

## Caveats

- n=80, one roster, two players. A +0.49 with p=0.47 excludes a large effect,
  not a small one; the design detects roughly ±2 points.
- Only the `_registered_food_power_value` multiplier is ablated. Other
  feeder-aware behaviour — the chance-node expectation over rerolls, the
  legal-action generator — is unchanged and is arguably where feeder odds
  actually pay.
- The other two valuation nulls (mat scaling, resource spending) have not been
  re-run on the searching agent. This result makes it likelier that they hold,
  but does not test them.

## Next

- Nothing further on this term. If the valuation question is reopened, spend the
  compute on the two untested nulls, or better, on what the horizon result
  suggests: evaluator structure, not evaluator coefficients.
