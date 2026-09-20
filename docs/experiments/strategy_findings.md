# Strategy findings: what the archive says about Wingspan, and what it cannot yet say

_Collected 2026-09-20 from `results_ledger.md`, the experiment write-ups,
and a descriptive pass over `artifacts/rr_belief_opp` (80 two-player games)
and `artifacts/rr3p_opp/belief` (90 three-player games). Every number
carries the design it came from; nothing here is stronger than its
detection limit (≈1.9 points for an 80-game paired arm, ≈2 for 90 games at
3p, ±3 for anything unpaired at n=200)._

The project's founding questions were about the game — which strategies
dominate, how to play under hidden information, what the opponent is worth,
how openings and card choices matter. The archive was built to answer
agent questions, and it answers the game questions only where those
coincide. This document separates the two honestly.

## 1. Dominance: one idea, then a plateau

| Claim | Evidence | Design | Status |
|---|---|---|---|
| Lookahead is the dominant skill. Depth-3 search on every turn is worth **+10.4 points** over the same evaluator one ply deep. | `search_depth_experiment.md`, 2026-09-05 | 80 paired, p<0.001 | established |
| Depth 4 adds +2.4 at four times the cost; endgame-only search adds +0.3. | same | 80 paired | established (cost-gated) |
| Nothing else tried is worth two points. Feeder odds (×3), reroll chance node, resource spending, mat scaling, opponent-aware denial, pink-power valuation, synergy terms, three openers: every one inside ±2. | ledger rows 2026-09-01 → 09-18 | 80–200 paired each | established as a pattern |
| Greedy immediate scoring is the **worst** way to play (0.275 win rate, last of five); guardrails that stop it from wasting food/cards rescue it by +10.4. | `round_robin_v2.md`, `round_robin_v3_guardrails.md` | 200 games each, counterbalanced | established |
| Guardrails do nothing for the searching agent. | `round_robin_v3_guardrails.md` | 200 games | established |

**Reading.** In this game, against these opponents, planning two of your
own turns ahead (with the opponents' turns in between) is worth more than
every valuation refinement combined. The valuation plateau is the second
finding: once the search exists, the heuristic agent is not limited by how
finely it prices food, dice or cards. That is why the project stopped
refining the evaluator and priced its cost instead.

## 2. Hidden information: plan, don't peek

| Claim | Evidence | Design | Status |
|---|---|---|---|
| Letting the search read the deck and the opponent's hand makes it **worse** (−2.4) than determinizing four samples. | `determinized_search_test.md` | 80 paired, p=0.008 | established |
| Knowing the feeder roll in advance is worth nothing (−0.3 n.s.). | `reroll_chance_node.md` | 80 paired | null |
| Feeder odds valuation is worth nothing, three times over (+0.5, −0.1, +0.2). | `round_robin_v5_feeder_odds.md`, `feeder_odds_search_rerun.md` | 80–200 paired | null ×3 |

**Reading.** The hidden information in base-game Wingspan is not where
the points are. Peeking overfits the plan to one deck order; averaging
over samples is better because the plan has to survive several. The dice
are close enough to fair that pricing them is noise.

## 3. Horizon: the round is the unit of planning

| Claim | Evidence | Design | Status |
|---|---|---|---|
| Counting the whole game's remaining turns instead of the round's costs **−12.0 points**. | `game_horizon_ablation.md` | 80 paired, p<0.001 | established |
| Behaviourally: the champion's action mix is round-shaped. Draw-cards falls from 26% of actions in round 1 to **14% in round 4**; lay-eggs rises from 25% to **38%**. Every scripted archetype keeps a flat mix all game (engine builder gains food 33–38% in every round; bonus-card focus draws 30–41% in every round). | descriptive, `rr_belief_opp` | 80 games | descriptive |

**Reading.** The round-end scoring and the shrinking cube count make
Wingspan a sequence of four short economies, not one long one. The
strongest single strategic rule the archive supports is *convert in
round 4*: stop drawing, lay eggs, play what is playable. The searching
agent discovers it; the scripted bots never do.

## 4. How the strong agent wins: a generalist profile

Mean points by category, 2p roster games (`rr_belief_opp`):

| Agent | birds | bonus | goals | eggs | cache | tuck | total | birds/game |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `potential_points` | 35.5 | 5.6 | 15.6 | 13.1 | 3.0 | 5.6 | **78.4** | 7.35 |
| `bonus_card_focus` | 29.9 | 5.8 | 11.1 | 7.0 | 3.3 | 5.3 | 62.5 | 7.15 |
| `engine_builder` | 29.4 | 3.8 | 10.7 | 7.1 | 3.3 | 4.3 | 58.6 | 6.95 |
| `net_value_response` | 22.2 | 3.9 | 11.2 | 6.4 | 3.1 | 5.7 | 52.5 | 5.05 |
| `greedy_immediate` | 18.2 | 3.0 | 12.4 | 10.6 | 3.9 | 2.6 | 50.7 | 4.45 |

At 3p the same shape holds (74.2: birds 35.1, goals 12.8, eggs 13.3).

Against itself (A1 mirror, 2026-09-20) the profile holds: 75.3 at 2p (winners
36.4 birds / 15.8 goals / 14.0 eggs, losers 32.8 / 12.0 / 11.4) and 78.3 at
3p. The round-shaped mix is unchanged in the mirror (draws 27% → 11%, eggs
22% → 40%). Winners in strong play separate on **round goals and eggs**
more than on birds.

**Reading.** The champion beats the best archetype by about +6 birds,
+4.5 round goals and +6 eggs, and ties it on bonus, cache and tuck. It is
not a specialist. Against this roster, egg-focus, cache/tuck-focus and
bonus-card-focus as *primary* strategies are dominated by a plan that
plays a bird roughly every third action and fills the board with eggs in
the last round. Whether a specialist could beat that plan is exactly what
the roster cannot tell us (§8).

## 5. Openings and card choices

| Claim | Evidence | Design | Status |
|---|---|---|---|
| The opening bonus-card choice is worth **6.4 points** between its best and worst option; per-bird-type cards beat the rest by +3.25 (p=0.009). | `bonus_card_selection_study_plan.md` | 322 forced-keep deals, paired | established |
| The historic opener picked the better card 50% of the time; `expected_points` picks it 61% (+0.85, p=0.011). | same, `keep_policy_eval.py` | free re-scoring of the forced arms | established |
| Which *birds* to keep is not answered. Three openers (v2, measured v3, plain) are within 2 points of each other; the measured opener kept birds worth more and then played fewer of them (64% vs 72%), later. | `results_ledger.md` 2026-09-16, 09-18 | 80 paired each | null; play value ≠ keep value |
| Bird main effects dominate synergy. Per-bird value resolves to ±7 points from 320 games; pair synergies are small next to that, pursuer-dependent and capacity-dependent (egg synergies collapse when the egg cap binds). | `bird_value_regression.py`, `synergy_planner_agent.md` layers A–C | observational + 240-seed forced play | established as a pattern |
| One confirmed pair for a cheap pursuer (Canvasback + Anhinga, +3.5, p=0.02) does **not** transfer to the searching agent (−1.7 n.s.). | layer C, 2026-09-17 | 240 paired | established |

**Reading.** Card value in this game is mostly the card, not the combo,
and mostly whether it gets played, not whether it was kept. The one
card-choice lever with a measured, transferable payoff is the bonus card.

## 6. Opponent and seat

| Claim | Evidence | Design | Status |
|---|---|---|---|
| At two players, what the search assumes the opponent will do is worth ≈0 (greedy, belief, oracle within ±0.3). | `search_opponent_model_test.md` | 80 paired ×3 | established (vs this roster) |
| At three players it is worth ≈2 (greedy +2.1 over belief, p=0.07; oracle +1.4). | same, 2026-09-18 | 90 paired 3p | suggestive |
| The gain is not from predicting the real opponent: greedy predicts the archetypes' families *less* often (35–47%) than the belief model (36–54%), and `belief_apply` was null. The working hypothesis is responsiveness on branch states; the `competent` arm (in flight) tests it. | 2026-09-19 refit + benchmark | 6,760 real decisions | open |
| A fourth cheap opponent model (`competent`: argmax public value on the branch) is null at both counts (+0.1 / −0.7); the pooled greedy holdout (51 games) reads belief +1.5. Against scripted opponents the programme is closed: whatever the greedy model has is the applied branch state, at its full cost. | `search_opponent_model_test.md` 2026-09-20 | 90 + 80 paired | closed (vs this roster) |
| **First seat signal in strong play:** in the 2p mirror the first player scores +5.1 and wins 0.575 (p=0.051, n=40 seeds); at 3p seat 3 wins 0.23 vs seat 1's 0.40. | `self_play_opponent_plan.md` A1 | 80 + 90 mirror games, rotations collapsed | suggestive (A2 pools) |
| Denial has no measurable value against this roster (−0.01). | 2026-09-02 | 200 paired | null (vs this roster) |
| Seat order at 2–3p: no robust effect. The 3p seat-3 advantage (+3.6, p=0.0009) did not replicate; two points of seat effect need 179 paired units to see. | `seat_order_investigation_3p.md`, `seat_effect_power_analysis.md` | 200 + 200 | not established |
| The champion is weakest from seat 3 at 3p (72.5 / 0.67 vs 76.2 / 0.83 from seat 1). | `rr3p_opp/belief` | 90 games, unpaired by seat | suggestive |

**Reading.** Against scripted opponents the opponent barely matters at
two players and matters a little at three. Whether that is a property of
the game or of the roster is the open question the self-play arms are
for (§8).

## 7. Cost, for completeness

Not a game finding, but it bounds the others: the search in production
form (pre-ranked, 5 s cap) keeps the full +10.4 at 1.1 s a decision
(−0.6 n.s.); depth buys ≈1.7 points per doubling of time, extra
determinization samples ≈0.9. `decision_profiling.md`.

## 8. What the archive cannot say yet, and why

1. **Dominant strategy among strong players.** Every row in §1–§5 is against
   a roster whose best member wins 60% of its games. "Egg focus is
   dominated" means dominated *by the searching generalist against scripted
   opponents*. The A1 mirror archive (170 games, 2026-09-20) is the first
   strong-versus-strong evidence: the generalist profile survives contact
   with itself, and winners separate on goals and eggs. Whether a
   specialist could beat it is still untested — that needs mirror arms
   with a specialised study seat, not a scripted specialist.
2. **Balance of cards, goals, and food.** The two-player round-robin
   archive covers **ten seeds**; the bonus-card study 111 coverage seeds;
   layer C 240. That is enough for paired agent contrasts (the seed is
   differenced out) and thin for claims about *which* cards or goals are
   strong. Round-goal and food-type balance have not been studied at all.
   The production configuration (a mirror game a minute) is the instrument
   for seed coverage; it is not for paired arms (wall-clock budget breaks
   cross-process determinism).
3. **Human play.** No human games exist. The belief model's profiles were
   fitted to scripts; the human-trace study (H1–H3) is built and waits on
   ten games.
4. **Expansions.** Base game only. Every instrument above (bird values,
   bonus keep, synergy bench, the ledger) re-baselines when a content pack
   changes the deck or the economy.

## How to extend this document

Add a row when a ledger entry answers one of the eight questions; cite
the write-up and the design; mark the status one of `established`
(paired, p<0.05, replicated or inside a consistent pattern), `suggestive`
(paired, 0.05<p<0.2, or unpaired), `null` (inside the detection limit
with a registered prediction), `descriptive` (no contrast), `open`.
