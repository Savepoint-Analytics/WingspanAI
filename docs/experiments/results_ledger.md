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
| 2026-09-18 | **production config**: `beam_leaf` + ladder v2 at 5 s | rr_belief_opp | −0.59 | 0.63 | +0.04 | 7,577 → 1,105 | +0.09 saved | **adopted as the production configuration**; research baseline stays unbudgeted (determinism) |
| 2026-09-18 | 3p: greedy opponent model vs belief (90 paired 3p games) | rr3p_opp/belief | **+2.12** | 0.073 | +0.07 | 8.8 → 15.6 s | +0.31 | opponent modelling matters at 3p; belief kept for cost; hybrid registered |
| 2026-09-18 | 3p: oracle-type vs belief | rr3p_opp/belief | +1.36 | 0.18 | +0.03 | ≈ | — | consistent with the greedy result |
| 2026-09-19 | 3p: `belief_apply` (family from posterior, greedy pick inside it) vs belief | rr3p_opp/belief | −0.48 | 0.21 | −0.01 | ≈ | — | 76/90 games identical: the family prediction is what costs, not the pick |
| 2026-09-19 | 2p: `belief_apply` vs belief | rr_belief_opp | −0.61 | 0.26 | −0.01 | 7,577 → 4,330 | — | 63/80 identical; not adopted |
| 2026-09-19 | response-likelihood refit (`analysis/fit_response_model.py`, 53,603 archived opponent decisions, leave-one-seed-out) | hand-set profiles | log loss 1.194 → 1.183; top-1 family 0.39 → 0.41 | — | — | — | — | gate failed; 3p arm not run. Greedy model predicts archetype families *less* often (0.35–0.47) than belief (0.36–0.54): its +2.1 at 3p is responsiveness on branch states, not accuracy; `competent` model registered |
| 2026-09-20 | 3p: `competent` opponent model (argmax public value on the branch, no posterior) vs belief | rr3p_opp/belief | +0.13 | 0.91 | +0.03 | ≈ belief (own cost 60 vs 131 ms) | ≈0 | null; registered +1 to +2 failed; not adopted |
| 2026-09-20 | 2p: `competent` vs belief | rr_belief_opp | −0.72 | 0.48 | −0.04 | ≈ belief | ≈0 | null; opponent-model programme vs the roster closed at both counts |
| 2026-09-18 | beam pre-ranking `beam_leaf` (cheap score picks the beam and the six leaves to evaluate) | rr_belief_opp | −0.72 | 0.55 | +0.04 | 7,577 → 1,836 | +0.13 saved | not the unbudgeted default **(H)**; goes into the production candidate |

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

## Strong-opponent studies (self-play, `self_play_opponent_plan.md`)

| Date | Arm | Design | Headline |
|---|---|---|---|
| 2026-09-20 | A1 `mirror_2p` | 80 games, seeds 1–40 × 2 rotations, default config both seats | mean **75.3** (vs 78.4 against the roster); seat 1 **+5.1, win 0.575** (p=0.051 at n=40 seeds — rotations of identical configs duplicate); winners 36.4 birds / 15.8 goals / 14.0 eggs vs losers 32.8 / 12.0 / 11.4 |
| 2026-09-20 | A2 `mirror_2p_greedy` | position 1 on `search_opponent_model="greedy"`, 80 games paired vs `mirror_2p` | study seat **+0.46 (p=0.62)**, win −0.006; decision ×1.55. Registered +1 to +3 failed: **the 2p opponent question closes** — a planning opponent changes nothing either. Seat pooled A1+A2 (160 games, 40 decks): seat 1 **+3.9 (p=0.014), win 0.559** |
| 2026-09-20 | A2 `mirror_3p_greedy` | position 1 on `greedy`, 90 games paired vs `mirror_3p` | study seat **+1.89 (p=0.072)**, win −0.011; decision ×1.55 (+0.18 points/s). Registered +2 to +4: point estimate just under. With the roster result (+2.12, p=0.073) two independent contrasts agree: **≈+2 at 3p is real** (combined p≈0.01), a score not a win effect, and four cheap reproductions failed. Not adopted for cost; belief stays |
| 2026-09-20 | A3 `mirror_2p_denial` | position 1 with `search_denial_weight=1.0`, 80 games paired vs `mirror_2p` | study seat **−5.94 (p<0.001)**, win −0.156; cost ×0.89. Registered +1 to +3 failed: the term pays the agent to draw tray cards (draw share 24% → 33%, tray draws 371 → 657) against a refilling supply. Dropped; 3p arm stopped as answered |
| 2026-09-24 | **3p 15-deck confirmation**: placement vs heuristic goal model, both sides fresh at 15 seeds × 2 opponent pairs × 3 rotations | rr3p_goal_heur15 | **+1.12** | 0.186 | +0.06 | ≈ | — | **does not meet its registered criterion** (deck-clustered p < 0.1 at ≥ +1): the effect size replicates exactly on 15 independent decks with design effect 1.04, but p=0.195. Above the +0.5 revert line, so the adoption stands **unconfirmed**; 25 decks would settle it at the observed effect |
| 2026-09-24 | production config (`beam_leaf` + 5 s ladder) re-checked on the placement default | rr_goal_placement | −0.80 | 0.50 | −0.04 | 3,227 → 1,062 | +0.37 saved | **production config stands**: p95 by round 1.2 / 3.2 / 3.8 / 4.2 s, all under the cap |
| 2026-09-22 | four-goal opener (`v2_allgoals`) vs the round-1-only opener (`v2`) | rr_opener_v2 | −1.21 | 0.037 | −0.01 | — | — | **invalid as a goal-horizon test**: the switch changed the opening in 2/80 games, 64 games were bit-identical, and the −1.21 is the arm's standing holdouts (the 2026-09-16 baseline has none). Registered null confirmed; not adopted |
| 2026-09-22 | 3p: placement round-goal model vs the heuristic | rr3p_opp/belief | **+1.12** | 0.128 | +0.03 | ≈ (0.1 ms a state) | — | meets the registered +1 bar → **adopted (H)**; re-baseline `rr_goal_placement` (2p) / `rr3p_goal_placement` (3p). Composition differs from 2p: goals +0.46, eggs +0.97, birds only −0.27 |
| 2026-09-22 | 2p: placement round-goal model vs the reachability heuristic | rr_belief_opp | +0.41 | 0.69 | +0.04 | ≈ (load-confounded) | — | inside the registered 0 to +2 but under the +1 adoption bar. **Mechanism confirmed and paid for**: goal points +0.84 (p=0.011), birds −0.75, bonus −0.41. At 2p the goals bought cost what they pay |
| 2026-09-20 | A4 `mirror_2p_b` | 80 games, fresh decks (seeds 41–80), default config both seats | score level replicates (75.28 vs 75.25); seat 1 **+7.2, win 0.650** (p<0.001, n=40 decks). Pooled with A1 on 80 independent decks: **+6.2 (p<0.001)**, limit 4.6 — **the 2p first-player advantage in strong play is established** |
| 2026-09-20 | A1 `mirror_3p` | 90 games, seeds 1–30 × 3 rotations | mean **78.3** (higher than 74.2 against the roster); seat win 0.40 / 0.37 / 0.23, seat 1 − seat 3 +2.9 (p=0.17 at n=30 seeds) |

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

## Decks, not games (2026-09-22)

A seed is a **deck**: every game on it shares the shuffle, the round goals
and the opening hands. Games on one deck are not independent units. What
the archive's designs actually sample:

| design | decks | games a deck | ICC of paired deltas | design effect |
|---|---:|---:|---:|---:|
| 2p round robin (seeds 1–10 × 4 lineups × 2 rotations) | 10 | 8 | −0.02 | 0.86 |
| **3p round robin (seeds 1–5 × 6 lineups × 3 rotations)** | **5** | **18** | +0.06…+0.08 | **≈2.0** |
| 2p mirror (seeds 1–40 × 2 rotations) | 40 | 2 | −0.15 | 0.85 |
| 3p mirror (seeds 1–30 × 3 rotations) | 30 | 3 | −0.15 | 0.69 |

Pairing removes the deck from the delta, so in three of the four designs
the per-game test is sound or conservative — the deltas do not cluster.
The exception is the **three-player round robin**: 18 games on each of 5
decks, and even a small positive ICC at that cluster size roughly doubles
the variance. Its p-values are overstated by about √2:

| 3p row | naive p | deck-clustered p |
|---|---:|---:|
| greedy opponent model +2.12 | 0.073 | 0.239 |
| placement goal model +1.12 | 0.128 | 0.282 |
| oracle-type +1.36 | 0.18 | ~0.35 |
| `belief_apply` −0.48 | 0.21 | ~0.4 |

No conclusion reverses: the point estimates are unchanged, and the one
that mattered — the greedy opponent model at 3p — was **replicated on a
properly decked design** (the 3p mirror, 30 decks: +1.89, deck-clustered
p=0.030, *stronger* read by deck). The placement adoption was made on a
pre-registered point-estimate bar, which it still meets; its evidence is
weaker than the naive p suggested and the registry says so.

`arm_contrast.py` now prints the deck count, the deck-clustered p and the
design effect, and flags any contrast whose design effect exceeds 1.3.
**Future three-player arms should spread over more seeds** (15 seeds × 2
opponent pairs × 3 rotations = 90 games on 15 decks) rather than more
lineups on five.

## Reading a row fairly

Two conditions, both learned the hard way. **Pair by seed** (2026-09-01,
after a greedy agent ranked second and a seat-3 advantage that were both
artefacts). **Match the holdout set**: an arm carrying standing holdouts
its baseline lacks is charged for the deviation (2026-09-22, the four-goal
opener arm). Rows from 2026-09-17 to 2026-09-22 paired against
`rr_belief_opp` carry a downward bias of about 0.1–0.4 points from this,
inside their detection limits; the 2026-09-22 re-baseline removes it.

## How to add a row

Every row so far is under `core_base_game_v1`. A row under another ruleset
goes in its own table (one per ruleset); cross-ruleset rows are unpaired and
say so. Register the prediction in `PROJECT_CONTEXT.md` before launching; run the
arm from a clean worktree at a recorded commit; read it through
`arm_contrast` **and** `decision_profile_report --value-against`; add the
row here with both numbers; if the decision adopts or drops a switch, add
a `Holdout` and a row to the holdout registry.
