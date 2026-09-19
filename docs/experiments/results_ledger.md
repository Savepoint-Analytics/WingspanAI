# Results Ledger

One row per registered arm, ablation or study, in the order they ran. The
paired-arm design (`analysis/arm_contrast.py`, `analysis/keep_policy_eval.py`,
`analysis/forced_play_contrast.py`) is the unit: 80 `potential_points` games
seed-matched against the baseline of the day unless a row says otherwise.
Latency is mean `potential_points` decision time from
`analysis/decision_profile_report.py`; **points / s** is the paired score
delta per extra second of decision latency, the production yardstick
(`docs/architecture/decision_profiling.md`). Dashes mean the arm did not
change the search and latency was not the question.

Every adopt/drop decision in the "Decision" column with a **(H)** keeps its
losing side alive at 5% (`docs/experiments/standing_holdouts.md`).

## Agent strength and cost

| Date | Arm | Baseline | Δ score | p | Δ win | decision ms | points / s | Decision |
|---|---|---|---:|---:|---:|---:|---:|---|
| 2026-09-05 | search depth 3 on every turn vs depth 1 (K=4) | rr_v5 | **+10.43** | <0.001 | +0.09 | 121 → 9,366 | +1.13 | adopted; the one result that matters |
| 2026-09-05 | depth 3 endgame-only vs depth 1 | rr_v5 | +0.3 | 0.74 | — | — | — | every-turn search instead |
| 2026-09-05 | depth 4 vs 3 | rr_v5 | +2.4 | 0.018 | — | ×4 latency | ≈ +0.1 | not adopted at this cost |
| 2026-09-06 | determinized hidden info (K=4) vs peeking | search | −2.42 for peeking | 0.008 | — | — | — | determinize; the gain is planning, not peeking |
| 2026-09-06 | reroll resolved at apply time (chance node) | search | −0.31 | 0.69 | — | — | — | null; keep the simpler rule |
| 2026-09-07 | game horizon vs round horizon | search | **−12.00** | <0.001 | −0.28 | — | — | round horizon is load-bearing |
| 2026-09-07 | gain-food pruning (6 candidates) vs none | rr_reroll_fix | −0.99 | 0.074 | −0.04 | 21,202 → 17,466 | +0.26 saved | kept for cost; the −1 is the price |
| 2026-09-07 | feeder odds valuation off | rr_reroll_fix | +0.49 | 0.47 | −0.01 | — | — | null (third null on feeder odds) |
| 2026-09-16 | belief posterior as search opponent model vs greedy | rr_prune | +0.31 | 0.73 | +0.01 | 17,466 → 7,577 | ≈0 | **adopted (H)**, for cost not strength |
| 2026-09-16 | `expected_points` opener (v2) as default | rr_belief_opp | **−3.00** | 0.022 | 0.00 | 7,577 → 5,668 | — | dropped; bird/food selection is the defect |
| 2026-09-17 | engine-potential (mechanic-pair) term, hand included | rr_belief_opp | **−4.51** | 0.001 | — | 7,577 → 10,066 | −1.81 | dropped |
| 2026-09-17 | board-only synergy term, halved | rr_belief_opp | +1.31 | 0.17 | +0.01 | 7,577 → 8,419 | +1.56 | not adopted **(H)** |
| 2026-09-17 | fast search-child expansion (trusted apply + lean copy) | rr_belief_opp | 0.00 (bit-identical, 104/104 decisions) | — | 0 | 5,187 → 2,588 (probe) | ∞ | **adopted (H)** |
| 2026-09-18 | measured opener `potential_points_setup_v3_keep3` (K=4 play values pick the three kept birds) | rr_belief_opp | −1.90 | 0.13 | +0.06 | — | — | not adopted **(H)**; play value ≠ keep value |
| 2026-09-18 | oracle-type opponent model (converged posterior known from turn one) | rr_belief_opp | +0.24 | 0.83 | +0.03 | ≈ belief | ≈0 | null; opponent-model family closed at 2p |
| 2026-09-18 | `max_decision_time_ms=5000` (anytime ladder: K, then depth, then one-ply) | rr_belief_opp | **−2.01** | 0.047 | −0.04 | 7,577 → 2,727 | +0.41 saved | not production yet; ladder spent the cap on samples not depth; v2 registered |
| 2026-09-18 | K=1 vs K=4 (depth 3) | rr_belief_opp | −1.99 | 0.080 | −0.01 | 7,577 → 1,521 | +0.33 saved | priced: a sample doubling ≈ 1 point; K=4 stays |
| 2026-09-18 | `max_decision_time_ms=5000`, ladder v2 (depth before samples, deadline abort) | rr_belief_opp | −1.46 | 0.12 | −0.04 | 7,577 → 2,359 | +0.28 saved | cap binds (45% cut); production candidate is pre-ranking + v2 |

Earlier nulls on the pre-search agent (2026-09-01 to 09-04), all inside a
±1.9-point detection limit at n=200: seat-3 advantage at 3p did not
replicate; six-face die re-run +0.17; opponent-aware denial and pink power
valuation −0.01; feeder odds −0.10. The standing conclusion from that
block: heuristic agents are not limited by rule fidelity or valuation
detail, and the depth-3 search was the first change large enough to see.

## Round robins (five agents, seat-counterbalanced)

| Date | Design | Headline |
|---|---|---|
| 2026-08-31 | v1, 10 seeds | `potential_points` 0.756 win rate; greedy looked second (wrong: pursuit confound) |
| 2026-09-01 | v2, corrected simulator | `potential_points` 0.756 / 66.8; **greedy last at 0.275** (p=0.0001) |
| 2026-09-01 | v3, guardrails | guardrails rescue greedy (+10.4 points, p=0.025) and do nothing for `potential_points` |
| 2026-09-02 | 3p seat order | seat 3 +3.6 (p=0.0009), seat 1 −2.5; **did not replicate** on 2026-09-03 |
| 2026-09-04 | v5, six-face die | standings unchanged; power analysis: 2 points needs 179 paired units |

## Card and play studies

| Date | Study | Headline | Instrument |
|---|---|---|---|
| 2026-09-16 | bonus-card keep (forced keep, 322 deals) | choice worth **6.4 points**; per-bird cards +3.25 (p=0.009); the historic opener picked the better side 50% of the time; `expected_points` picks it 61% (+0.85, p=0.011) | `bonus_card_keep_contrast.py`, `keep_policy_eval.py` |
| 2026-09-16 | bird-value layer 2 (scorecards, 320 games) | bird main effects dominate; per-bird resolution ±7 points | `bird_value_regression.py` |
| 2026-09-17 | layer A rules bench (rich / scarce / capped) | egg synergies collapse when the egg cap binds; tuck and cache chains survive | `card_synergy_bench.py` |
| 2026-09-17 | layer B counterfactual play attribution, K=0 → K=4 | K=4 cuts within-bird SD 36%; the K=0 pair table was mostly noise (ρ=0.31 with K=4) | `play_counterfactuals.py`, lme4 |
| 2026-09-17 | layer C forced keep-and-play, cheap pursuer (240 seeds × 3 pairs) | P2 Canvasback + Anhinga **+3.48 (p=0.021)**; P1 null; P3 **−3.38 (p=0.005)** reverses the bench | `forced_play.py`, `forced_play_contrast.py` |
| 2026-09-17 | layer C P2 on the searching pursuer (240 games) | −1.67 (p=0.35): the pair does not transfer to the searching agent | same |

Standing conclusion of the synergy programme: pair synergy is small next to
card main effects, pursuer-dependent and capacity-dependent; the evaluator
is not where combination evidence pays; card-choice decisions (opener, draw)
are the next place to spend it.

## Where the default agent's time goes (2026-09-17)

Before the fast expansion: `expand_children` 73%, `terminal_value` 17%,
opponent model 3%, 5.2 s mean decision. After: 53% / 33%, 2.6 s. Latency by
round in the archive: 1.8 → 5.9 → 10.5 → 15.7 s mean; a production budget
has to be per decision.

## How to add a row

Register the prediction in `PROJECT_CONTEXT.md` before launching; run the
arm from a clean worktree at a recorded commit; read it through
`arm_contrast` **and** `decision_profile_report --value-against`; add the
row here with both numbers; if the decision adopts or drops a switch, add
a `Holdout` and a row to the holdout registry.
