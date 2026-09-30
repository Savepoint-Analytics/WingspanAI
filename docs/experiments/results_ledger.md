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
| 2026-09-24 | **3p 15-deck confirmation**: placement vs heuristic goal model, both sides fresh at 15 seeds × 2 opponent pairs × 3 rotations | rr3p_goal_heur15 | **+1.12** | 0.186 | +0.06 | ≈ | — | at 15 decks this **did not** meet its registered criterion (deck p=0.195 against a p<0.1 bar). Superseded by the 25-deck pool below, which does — read the two together, not this row alone |
| 2026-09-30 | **`reroll_penalty=2.0`** (flat penalty on root actions that reroll the birdfeeder, when a non-reroll option is legal), both sides fresh | rr_reroll_base | **−0.388** | 0.553 | −0.013 | ≈ | — | **middle zone — not adopted, not refuted.** Registered ≥+1.5 adopts / ≤−1.5 drops / between = untested at this budget. CI [−1.66, +0.89] **excludes the +1.44 the nomination predicted**, so the near-tie +2.40 a decision does *not* transfer to whole-game score; it cannot resolve anything under ±0.9. 39/80 games bit-identical (predicted 47%, got 49%); realized SD 5.81 vs 6.5 predicted — the power model held. **Delivered 80 games / 10 decks against a registered 160 / 20: `--seeds` is ignored for 2p roster arms and I did not check the dry-run game count**, so the realized limit 1.82 sits above the registered 1.5 threshold. Closed on cost grounds (±0.7 needs 540 games) |
| 2026-09-29 | **near-tie counterfactuals**: 2,045 decisions where the champion's own top-two valuations were within 0.2, both branches rolled to the end from identical determinized worlds | — (decision-level pairing, not an arm) | **+0.062** | 0.565 | — | 230 games, ~20 s a game | — | **indifference confirmed.** Registered band −0.3 to +0.3; 95% CI [−0.149, +0.273] lies entirely inside it, so this is a positive finding of indifference rather than a failed rejection. Delivered n=2,045 (floor 1,400) and SD=4.88 (ceiling 5.5), so the registration was answerable — though the realized limit 0.302 sits just outside the band half-width, so the verdict rests on the CI. 33.6% of near-ties end in *exactly* zero difference. No per-pair finding at Bonferroni 0.0031 across 16 cells; two nominations (`play_bird` over `draw_cards` −1.51 at p=0.024 n=63; `gain_food` vs `gain_food` +0.43 at p=0.051 n=393). **Closes evaluator tie-break tuning as a direction** |
| 2026-09-26 | **3p oracle-type opponent model** (perfect opponent-type knowledge from turn one), 15 decks × 2 pairs × 3 rotations, pre-registered after the audit promoted the 5-deck read | rr3p_goal_place15 | **+0.00** | **1.000** | +0.011 | ≈ belief | — | **clean null; the opponent-model family is now closed at 3p as well as 2p.** Registered +0.5 to +2.0 at deck p<0.05; measured exactly 0.00 over 90 games (sum of paired deltas exactly zero, 7/15 decks positive, deck p=1.000). The audit's 5-deck +1.36 at deck p=0.028 was noise. 79 of 90 games differ (deltas −35 to +19, 43 up / 36 down), so the switch does change play — it just does not change the score |
| 2026-09-25 | beam pre-ranking as the **unbudgeted** default, re-run after the audit put the original −0.72 at −0.16 like-for-like | rr_goal_placement | −0.86 all / **−0.96 holdout-free** | 0.43 | −0.04 | **3227 → 1230 ms (×0.38)** | 84 → 32 s a game | **not adopted.** Registered −0.5 to +0.5 on holdout-free games; −0.96 misses it. The audit's −0.16 did **not** replicate — three reads of this switch now sit at −0.72, −0.80, −0.96. But the 95% CI is [−3.34, +1.43] and the detection limit is 3.41 points, so **the arm cannot tell the adoption band from the drop**: at sd=10.5 the registered ±0.5 needs ~3,400 games. The registration was unanswerable at 80 games — see below |
| 2026-09-25 | **3p 25-deck extension**: seeds 16–25 added to the above, same 2 pairs × 3 rotations, both sides (`rr3p_goal_place25` / `rr3p_goal_heur25`) | rr3p_goal_heur25 | **+1.12** | **0.097** | +0.04 | ≈ | — | **meets the registered criterion** (deck-clustered p < 0.1 at ≥ +1) → the placement goal model is **confirmed**, reversing the 2026-09-24 "unconfirmed" label. New decks 16–25 replicate almost exactly (+1.117 vs +1.122 on 1–15). **But the verdict is fragile** — see below |
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

## Both of the audit's promotions failed their pre-registered arms

The 2026-09-25 audit re-read every row by deck and on holdout-free games, and
two rows changed enough to reopen a closed question. Both have now been tested
by a pre-registered arm, and both reverted:

| Row | audit's re-read | pre-registered arm | verdict |
|---|---|---|---|
| beam pre-ranking (2p) | −0.72 → **−0.16** holdout-free | **−0.96** on 74 holdout-free games | the audit's number was noise; the original drop stands |
| 3p oracle-type model | "null" → **deck p=0.028**, +1.36 | **+0.00, p=1.000** on 15 decks | the audit's number was noise; the original null stands |

This is the multiplicity surface recorded above doing exactly what that section
warned it would. The audit ran roughly 95 unadjusted per-cell re-reads; two
came back interesting; both were selection effects. The audit's *corrections to
method* (exact t instead of the normal approximation, deck clustering, the
holdout-free like-for-like) were real and are kept. Its *re-ranked results*
were hypotheses, and the two worth testing both died.

**The rule this earns:** a re-read of existing data never changes a verdict on
its own. It can only nominate a question for a fresh pre-registered arm. Where
an arm is too expensive to run, the row keeps its original verdict and the
re-read is recorded as a caveat, not a correction.

## Two registrations in a row asked questions their arms could not answer

Both arms read on 2026-09-25 registered a decision band narrower than the arm
could resolve. That is a design fault in the registration, not a result, and
it is now the most common way an arm wastes compute here.

| Arm | registered band | measured | detection limit at 80% power | games needed for the band |
|---|---|---:|---:|---:|
| beam pre-ranking, unbudgeted | −0.5 to +0.5 | −0.96 (CI −3.34 to +1.43) | **3.41** | **~3,400** |
| 3p placement, 25 decks | ≥ +1 at deck p<0.1 | +1.12 (deck p=0.097) | ~2.9 by deck | ~35 decks for p<0.05 |

The pre-ranking arm is the clearer case: a ±0.5 band against a per-game SD of
10.5 needs about 3,400 games, and it got 80. Whatever it returned, the answer
was going to be "inside the noise" — so the arm could only ever have produced
a point estimate dressed as a verdict.

**Standing rule from here: a registration must state the detection limit its
sample will have, and the band must be wider than that limit.** If it cannot
be, the arm should not be launched — decide on cost, mechanism or theory
instead and say so. Per-game score SD in 2p arms is 9–11 points, so an 80-game
paired arm resolves about ±3 points and nothing finer. Bands of ±1 need ~860
games; bands of ±0.5 are out of reach on this hardware.

This also reframes the pre-ranking decision honestly: it is **not adopted
because three independent reads all land near −0.8** (−0.72, −0.80, −0.96),
not because any one of them was significant. None was. The consistency of the
sign across reads with different baselines is the evidence; each individual
p-value is not.

## The 25-deck placement confirmation is fragile

The pooled 25-deck read (Δ=+1.120, deck-clustered p=0.0971, 25 decks) clears
the pre-registered bar, and the registration is honoured: the rule was fixed
before launch and it is met. But three robustness checks all say the verdict
sits on a knife edge, and a reader who quotes "confirmed, p<0.1" without them
is over-reading the row.

| Check | Result | Reading |
|---|---|---|
| Leave-one-deck-out | removing any of **14 of 25** decks pushes p above 0.1 | the verdict, not just the p-value, is one deck from flipping |
| — worst three | drop deck 2 (+10.2) → Δ=+0.74, p=0.190; deck 25 (+7.0) → +0.88, p=0.176; deck 17 (+5.8) → +0.92, p=0.165 | the confirmation leans on a few high-scoring decks |
| Sign test | 16/25 decks positive, two-sided **p=0.230** | direction alone is not significant |
| 20% trimmed mean | **+0.85** | below the +1 adoption bar once outer decks are trimmed |

Between-deck SD is 3.24 on a +1.12 effect, so a deck's identity moves the
score three times more than the switch does. The honest effect size is
**about +0.8 to +1.1**, with +1.12 at the optimistic end of that range: the
leave-one-out Δ spans +0.74 to +1.12 and the trimmed mean lands at +0.85.

What this changes: the switch stays the default (it was already adopted, and
nothing here argues for reverting — the revert line was +0.5 and every
estimate clears it). What it forbids is treating +1.12 as a measured
constant, or citing this row as a clean positive in the case study. If the
placement model's value ever needs to be known to better than ±0.3 points,
that needs decks in the hundreds, not 25 — and on cost grounds the
registration already closed the question either way.

## Audit, 2026-09-25

Every row was re-read for deck clustering, multiplicity and holdout-set
mismatch, and the p-value function was found to use a normal approximation
(exact t now). Nothing reversed; two decisions are better supported than
recorded, two findings are weaker, one dismissed row needs an arm. Full
working in `ledger_audit_2026_09_25.md`. The corrections that matter:

| row | as recorded | corrected |
|---|---|---|
| 2p placement goal model | +0.41 (p=0.69) | **+1.44 (p=0.20)** like-for-like on holdout-free games |
| production config at 5 s | −0.59 | **+0.00** like-for-like |
| beam pre-ranking | −0.72 | **−0.16** like-for-like; the drop is worth revisiting |
| 3p greedy opponent model | +2.12 (p=0.073) | p=**0.304** by deck; carried by the mirror arm (+1.89, p=0.038 on 30 decks) |
| 3p oracle-type model | +1.36, "null" | deck p=**0.028**; promoted to "needs its own arm" — **the arm ran 2026-09-26 and returned +0.00 (p=1.000). The promotion was a multiplicity artifact; the original "null" was right.** |
| layer C P2 pair | +3.48 (p=0.021) | does not survive Bonferroni across its three pre-registered pairs; follow-up null |

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

## The per-opponent breakdown is a multiplicity surface (2026-09-24)

Every `arm_contrast` run prints a headline contrast **and** one cell per
opponent: four at two players, six at three. Those cells are unadjusted
tests, and the ledger has quoted individual ones as findings:

| arm | cell quoted | p | survives Bonferroni within its own arm (α=0.05/4 = 0.0125)? |
|---|---|---:|---|
| synergy term | −7.7 vs `bonus_card_focus` | 0.006 | yes |
| budget ladder v2 | −4.2 vs `bonus_card_focus` | 0.03 | **no** |
| resource spending | vs `bonus_card_focus` | 0.07 | no |

The arithmetic: with four cells, P(at least one at p<0.05 by chance) is
**18.5%**; with six, **26.5%**. Five three-player arms have now been read
against the same baseline on the same five decks — about 35 score tests, plus
as many win-rate tests — so a handful of spurious cells is expected, not
surprising. **A single cell in a single arm is a hypothesis to test, not a
finding.**

### What pooling the cells actually shows

Pooled over five two-player arms (budget v2, K=1, pre-ranking, competent,
placement), splitting the same paired deltas by opponent:

| opponent | n | mean Δ | SD | SE |
|---|---:|---:|---:|---:|
| `archetype_bonus_card_focus` | 100 | **−2.76** | 9.64 | 0.96 |
| `greedy_immediate` | 100 | −0.73 | 9.76 | 0.98 |
| `net_value_response` | 100 | −0.69 | 9.73 | 0.97 |
| `archetype_engine_builder` | 100 | +0.59 | 9.13 | 0.91 |

The four opponents have **the same variance** (SD 9.1–9.8), so
`bonus_card_focus` is not simply the noisy cell that keeps winning the
lottery. The differential against `engine_builder` is 3.35 points at roughly
2.5 SE, it replicates across five independent switches, and there is already
a mechanism on record: four of those five arms cut search work, and
`decision_profiling.md` notes that the plies cut first are the ones that see
bonus-card scoring.

So the honest form of this finding is **pooled across arms, not read from one
cell**: cost reductions in the search cost more against a bonus-card opponent
than against the rest of the roster. Stated that way it is worth acting on;
stated as "budget v2 lost 4.2 to bonus_card_focus at p=0.03" it was one of
about five cells that chance alone would have produced.

## Reading a row fairly

Two conditions, both learned the hard way. **Pair by seed** (2026-09-01,
after a greedy agent ranked second and a seat-3 advantage that were both
artefacts). **Match the holdout set**: an arm carrying standing holdouts
its baseline lacks is charged for the deviation (2026-09-22, the four-goal
opener arm). Rows from 2026-09-17 to 2026-09-22 paired against
`rr_belief_opp` carry a downward bias of about 0.5–1.0 points from this
(estimated at 0.1–0.4 until the 2026-09-25 audit measured it on holdout-free
games; the estimate was 2–3× too small and the bias runs against the arm),
inside their detection limits; the 2026-09-22 re-baseline removes it.

## How to add a row

Every row so far is under `core_base_game_v1`. A row under another ruleset
goes in its own table (one per ruleset); cross-ruleset rows are unpaired and
say so. Register the prediction in `PROJECT_CONTEXT.md` before launching; run the
arm from a clean worktree at a recorded commit; read it through
`arm_contrast` **and** `decision_profile_report --value-against`; add the
row here with both numbers; if the decision adopts or drops a switch, add
a `Holdout` and a row to the holdout registry.
