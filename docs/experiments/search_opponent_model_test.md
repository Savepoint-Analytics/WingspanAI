# Belief-Driven Opponent Model in the Search

Status: complete, 2026-09-16. **Null on score (+0.31, p=0.73); decision cost more than halved.**
Code: `b9805bc` (clean worktree; every manifest records it)
Artifacts: `artifacts/rr_belief_opp/`, baseline `artifacts/rr_food_cand6/`
Module: `src/wingspan_ai/agents/search_opponent.py`,
`PotentialPointsAgent(search_opponent_model="greedy" | "belief")`.
Baseline is the current default agent: depth 3, every turn, K=4,
`search_food_candidates=6`, greedy opponent model.

## Why this experiment

Two open threads point at the same piece of code.

**Compute.** After gain-food pruning
([search_food_candidates.md](search_food_candidates.md)), about 40% of a
`potential_points` decision was the greedy model playing the opponent's turns
inside the search. On every modelled opponent turn it prices every legal
action through `apply_action` — about 16 ms a turn, multiplied across every
node of a depth-3 tree over four determinization samples. Arms per week is
the binding constraint on the project, so this is the next thing to cut.

**The thesis.** `COMPANY_CONTEXT.md` puts Bayesian opponent modelling at the
centre of the project, and `wingspan_ai.belief` has existed since 2026-08-31
with a calibrated posterior over six opponent profiles. But the only agent
that consumed it, `net_value_response`, sits near the bottom of every round
robin, and no experiment has yet shown a belief changing a decision for the
better. The search is the first place in the codebase where a belief can do
real work: the question "what will the opponent do next?" is asked thousands
of times per decision, and currently answered by a fixed greedy heuristic.

## What changed

`BeliefSearchOpponentModel` plays each opponent turn in two steps:

1. **Family.** Compute public candidate values for the four action families
   (the same `_public_response_candidates` template `net_value_response`
   uses), ask the opponent's `OpponentBeliefState` for the marginal
   distribution over families, and take the most likely family that has a
   legal action. Cost ~0.2 ms; reads only `to_public_state` and the posterior.
2. **Action.** Within that family, pick by a proxy that never applies an
   action: printed points less the slot's egg cost for a bird, eggs laid for
   lay-eggs, otherwise greedy's own tie-break (food need, tray-card quality).
   The proxy agrees with greedy inside play-bird on every probe state tested;
   what it drops is points a power would add on activation.

The posterior is updated only from the real game, through the runner's
existing `observe_action` hook, which `PotentialPointsAgent` now implements.
Search branches read it and never write it. Each decision's telemetry records
`search_opponent_model` and the current posterior per opponent, so the arm
is identifiable from artifacts and the belief's sharpening can be inspected.

The greedy model is unchanged and remains the default. A regression test
pins it to `GreedyBaselineAgent` so archived decisions replay bit for bit.

## Registered predictions

Written before the arm runs.

1. **Compute (primary, expected to hold).** Mean `potential_points` decision
   time falls by **≥30%** against the same states. The back-to-back probe
   (`analysis/search_opponent_profile.py`, seed 1 vs `archetype_engine_builder`)
   is the clean measurement; the arm's wall-clock telemetry is the noisy one.
2. **Score (prior: null or small negative).** Paired delta on the 80
   `potential_points` games is within **−1.0 … +1.0 points**, not
   significant. Reasoning: the modelled opponent is cruder within a family
   (no activation points), which should cost about what pruning cost; a
   better-calibrated *family* choice might give it back. Four valuation
   changes in a row have been null; the prior is that this one is too.
3. **Non-inferiority gate.** The switch becomes the default only if the
   paired score delta is **≥ −1.0** and the win-rate delta is not
   significantly negative. A larger loss means the cheaper model is not
   cheap enough to be worth it, and the search-cost problem needs a different
   answer (a cached greedy pick, or a shallower opponent).
4. **Belief sharpening (diagnostic, not a gate).** By the last round, the
   most likely profile in the belief-arm telemetry should be
   `value_maximizing` against `greedy_immediate` and `engine_builder` against
   `archetype_engine_builder` in a majority of games. If the posterior stays
   near uniform, the family choice is driven by the priors and candidate
   values alone, and the result says nothing about *Bayesian* modelling.

What would make the compute result uninteresting: if the reduction is real
but the score loss exceeds the pruning loss, the right comparison is
`search_food_candidates=None` plus the belief model against the current
default, and that has to be run before either is adopted.

## Design

Reduced paired design, identical to the last two arms: the four two-agent
lineups containing `potential_points`, both seat rotations, seeds 1–10, `control`
setup — **80 games**, contrasted against the same 80 inside `rr_food_cand6`
with `analysis/arm_contrast.py`. The 120 games without `potential_points` are
bit-identical by construction and are not re-run.

Arm settings: agent defaults plus
`PotentialPointsSearchConfig(search_opponent_model="belief")`, passed
explicitly so the manifest records it. Run from a clean worktree at the
committed revision with an absolute `workbook_path`. Chunked as before:
three lineup groups × five two-seed chunks.

```python
from flows.round_robin import run_round_robin
from wingspan_ai.agents.potential_points import PotentialPointsSearchConfig

run_round_robin(
    roster=["potential_points", "greedy_immediate"],   # then the other three lineups
    seeds=[1, 2],
    setup_policy_kinds=["control"],
    artifact_root="artifacts/rr_belief_opp",
    batch_label="rrbelief_grepot_s1_2",
    potential_points_search=PotentialPointsSearchConfig(search_opponent_model="belief"),
)
```

```bash
python analysis/arm_contrast.py --baseline artifacts/rr_food_cand6 --arm artifacts/rr_belief_opp
```

## Compute probe (prediction 1: holds)

`analysis/search_opponent_profile.py --seed 1 --opponent archetype_engine_builder`,
one process, both models timed back to back on each of the 26 `potential_points`
decisions along the greedy-modelled agent's trajectory. Machine load was ~7 on
8 cores throughout, so absolute times are inflated; the ratio is not.

| | greedy model | belief model |
|---|---:|---:|
| total decision time | 142.9 s | **84.2 s** |
| mean decision | 5.50 s | 3.24 s |
| worst decision (48-action root) | 32.5 s | 20.5 s |
| reduction, all 26 decisions | | **41.1%** |
| reduction, 11 decisions over 5 s | | 40.8% |
| same action chosen | | 24 of 26 (92.3%) |

The reduction clears the registered 30% and is larger than the 40% share
estimated from profiling, because the opponent model is paid at every node of
the tree and its share grows with depth. The two decisions that differed were
at turns 5 and 22, both in the first two rounds; every endgame decision agreed.

**Diagnostic worth carrying into the arm.** After 25 observations of
`archetype_engine_builder`, the posterior sat at `food_acceleration` 0.9995,
`engine_builder` 0.0000. Two readings, both probably true: the archetype does
gain food on a plurality of turns (36% gain-food, 26% play-bird over five games vs greedy), so
the label is behaviourally defensible; and the posterior is far too confident,
because each observation is scored as an independent draw from hand-tilted
profile priors that were never fitted to this roster. Prediction 4 as written
(the most likely profile "should be `engine_builder`") is therefore the wrong
test; the honest version is whether the posterior *concentrates*, and whether
the family it predicts matches the family the opponent actually plays. The
2026-08-31 follow-up "refit belief family priors per opponent kind from
round-robin telemetry" is the fix and is still open.

## Result: null on score, as registered (predictions 2 and 3 hold)

80 paired games at `b9805bc`, all 40 manifests `dirty: false`, all replays
valid. `analysis/arm_contrast.py --baseline artifacts/rr_food_cand6 --arm
artifacts/rr_belief_opp`:

| Metric | greedy model | belief model | Δ | p |
|---|---:|---:|---:|---:|
| `potential_points` avg score | 78.10 | 78.41 | **+0.31** | 0.733 |
| `potential_points` win rate | 0.863 | 0.875 | +0.013 | 0.740 |

Identical outcomes: 3 of 80. The games diverge almost everywhere — a
different modelled opponent changes what the search sees on most turns — and
the outcome does not move. By opponent: `archetype_bonus_card_focus` +1.95,
`net_value_response` +1.40, `archetype_engine_builder` −1.00,
`greedy_immediate` −1.10; none significant at n=20, two up and two down, which
is what a null looks like cell by cell. No opponent's own score moves
significantly either (largest: `greedy_immediate` +3.70, p=0.21).

Action mix is unchanged to within half a point: play-bird 28.3% → 28.3%,
lay-eggs 27.3% → 26.9%, draw 23.8% → 24.3%, gain-food 20.6% → 20.5%. The
agent plays the same game against a cheaper imagined opponent.

The non-inferiority gate (Δ ≥ −1.0, win not significantly negative) passes.

### What it buys

`potential_points` decision cost, 2,080 decisions per arm:

| | greedy model | belief model |
|---|---:|---:|
| mean | 17.47 s | **7.58 s** |
| median | 6.78 s | 3.53 s |
| p95 | 69.9 s | 28.5 s |
| p99 | 161.3 s | 62.5 s |
| max | 491.5 s | **178.9 s** |
| per game | 454 s | 197 s |
| worst game | 1788 s | 754 s |
| arm total | 10.09 h | **4.38 h** |

Load caveat as always: the baseline shared the machine with one other arm,
this arm ran as four concurrent runners on a box already at load ~7. The
back-to-back probe (41.1%) is the clean measurement; the arm's 57% is the
realized bill, and both point the same way. Wall clock for the whole 80-game
arm was 1 h 15 min with four runners (12:25 → 13:40).

### The posterior identifies behaviour, not type (prediction 4, rewritten)

At each game's final `potential_points` decision, the belief about the
opponent had concentrated (mean mass on the top profile 0.73–0.88, never
below 0.46), and the top profile matched the family the opponent actually
played most:

| Opponent | Its plurality family (share) | Top profile at game end (of 20) |
|---|---|---|
| `archetype_bonus_card_focus` | draw_cards 36% | card_draw 9, food_acceleration 4, random_legal 3, … |
| `archetype_engine_builder` | gain_food 35% | food_acceleration 11, card_draw 5, … |
| `greedy_immediate` | gain_food 45%, lay_eggs 22% | food_acceleration 11, egg_focus 6, value_maximizing 2 |
| `net_value_response` | draw_cards 42% | card_draw 15, random_legal 4, egg_focus 1 |

So the model works as a classifier of *action-family mix* and is consistent
about it. What it is not is a classifier of opponent *type*: greedy is the
roster's purest value-maximizer and the `value_maximizing` profile wins only
2 of 20 games against it, because that profile's likelihood is a low-
temperature softmax over the *public candidate values* — and those values
rank families differently from greedy's real immediate-score ranking, so a
food-tilted prior explains greedy's turns better than "rational" does. The
posterior is also overconfident, as the probe suggested: observations are
scored as independent draws from hand-tilted priors that were never fitted
to this roster. The 2026-08-31 follow-up to refit profile priors from
round-robin telemetry remains the fix.

## Decision

**Applied 2026-09-16 (Alex's call):** `search_opponent_model="belief"` is the
default and `artifacts/rr_belief_opp` is the baseline for the default agent
from here. The registered gate passed, the action mix is unchanged, and the
arm cost falls from ~10 h to ~4.4 h, which is the binding constraint on
everything downstream.

**With a standing control.** Alex's two reservations — the null could be a
false positive at n=80, and adopting the belief model everywhere could bias
any agent that later learns from past games toward what the belief-modelled
search tends to see — are met by a holdout rather than by trust. A
deterministic **5% of games keep the greedy model**
(`PotentialPointsSearchConfig.search_opponent_holdout_share=0.05`,
`search_opponent_holdout_model="greedy"`). Which games are held out is a
SHA-256 draw over `(random_seed, lineup, lineup position)`, so:

- seed-matched arms hold out the same games and stay paired;
- both seat rotations of a game hold out together, so the control subset is
  counterbalanced like everything else;
- the manifest records the effective model per `potential_points` seat
  (`games[].search_opponent_models`) and every decision records it too.

In the standard 80-game design the draw holds out 6 games (seeds 10, 1 and 3
in three of the four lineups); at seeds 1–30 it is 8 of 240. The control
therefore accrues slowly by design — it is a long-run experiment, not a
per-arm test — and `analysis/holdout_guardrail.py` pools artifact roots and
reports the unpaired contrast with its own detection limit, refusing to read
fewer than 40 held-out games as a finding.

Two things this result does and does not say:

- It does not say Bayesian opponent modelling makes the agent stronger. A
  posterior that tracks the opponent's action mix is now in the loop and the
  score did not move — the same shape as the four valuation nulls. What is
  new is that this term was measured *against* a real search rather than
  inside a one-ply evaluator, and it still landed null.
- It does say the search is robust to a much cruder opponent model. Every
  node's imagined opponent went from a full greedy evaluation to a family
  guess plus a proxy, and the agent lost nothing measurable. That is the
  useful engineering fact: the opponent model is not where the search's
  strength lives either.

Revisit if: a stronger opponent enters the roster (a second searching agent),
where the family-plus-proxy model may be too crude to anticipate real threats;
or if refitted priors make `value_maximizing` identifiable, at which point the
"belief vs greedy" contrast is worth re-running as a test of the thesis.

## Caveats

- One roster, two players, n=80; detection limit around 2–3 points at this
  size, so this bounds the effect as small rather than zero.
- The within-family proxy ignores points a power adds on activation. Against
  the current roster that did not matter; against an engine-heavy opponent it
  might.
- `same_choice` in the probe was 92%; across the arm only 3 of 80 games were
  identical. Divergence is expected — the point is that it is not directional.

## Follow-up arm (registered 2026-09-18): the oracle-type bound

**Question.** The belief model in the search is worth ≈0 points at 2p. Is
that because type inference is slow (25 observations to converge), or
because knowing the type buys nothing with this response model? The
cheapest way to separate the two is to hand the search the answer.

**Model.** `search_opponent_model="oracle"`
(`OracleTypeSearchOpponentModel`): the belief model seeded, for every
opponent seat from turn one, with the posterior it converges to for that
agent kind by the end of a game — pooled from 56–60 games per kind across
`rr_belief_opp`, `rr_opener_v2` and `rr_synergy_board` by
`analysis/oracle_type_posteriors.py` into
`configs/belief/oracle_type_posteriors.json` — and never updated. It reads
the seat's `agent_id`, which no real player can; it is a bound, not a
candidate default. Kinds absent from the table fall back to ordinary
updating. The converged posteriors are themselves the calibration finding
above in numbers: `greedy_immediate` → food_acceleration 0.49 / egg_focus
0.32; `archetype_engine_builder` → food_acceleration 0.52; `net_value_response`
→ card_draw 0.77; `archetype_bonus_card_focus` → card_draw 0.41.

**Prediction.** Null: −1 to +1 against `rr_belief_opp` on the standard 80
paired games. A result at or above +2 says inference speed is the
bottleneck and a refit of the profile priors to the roster is worth an arm;
a null closes the opponent-model family at 2p (the 5% greedy holdout keeps
watching) and moves the question to 3–4 players, where the seat-order
study found real interaction.

**Cost.** Identical to `belief` (one dict lookup replaces 25 Bayes updates).

**Result (2026-09-18).** `artifacts/rr_oracle_opp` vs `rr_belief_opp`, 80
paired games at `9adb314`, clean: `potential_points` **78.41 → 78.65
(+0.24, p=0.83)**, win 0.875 → 0.900 (+0.025, p=0.57); by opponent +0.40 /
+3.00 / −0.70 / −1.75, none significant; 5 of 80 games identical. Null, as
registered. Decision latency unchanged within load noise.

Reading: three opponent models — greedy (applies every opponent action),
belief (learns the type over the game), oracle (knows the converged type
from turn one) — score within ±0.3 of each other at two players. What the
search's opponent turns do with the type does not matter here, because the
opponent model only decides which family the imagined opponent plays and
the acting player's own plan is robust to that at 2p (the tray and feeder
contention it creates is similar under every family). The
opponent-model family is closed at two players: keep `belief` for its
cost, keep the 5% greedy holdout watching, and take the question to three
and four players where the seat-order study found real interaction.
Refitting the profile priors to the roster is not worth an arm on this
evidence — the oracle already supplies what a perfect refit would learn.

## Three players (2026-09-18): the opponent model is not free any more

Design (registered above): `player_count=3`, `potential_points` with every
pair of {engine_builder, bonus_card_focus, net_value_response,
greedy_immediate}, all three rotations, seeds 1–5 — 90 games per root,
paired game for game across `artifacts/rr3p_opp/{belief,greedy,oracle}`,
at `5a3e7d5`, six runners.

| Contrast | Δ score | p | Δ win | PP mean decision |
|---|---:|---:|---:|---:|
| greedy − belief | **+2.12** | 0.073 | +0.067 | 15.6 s vs 8.8 s |
| oracle − belief | +1.36 | 0.18 | +0.033 | 6.1 s (ran alone) vs 8.8 s |

`potential_points` at three players: 74.2 points, win 0.76 with the belief
model (2p: 78.4, 0.875); 76.3 / 0.83 with greedy; 75.5 / 0.79 with the
oracle. By seat with belief: 76.2 / 73.8 / 72.5 and win 0.83 / 0.77 / 0.67
from seat 1 to 3 — the third seat is the hard one for the searching agent,
the reverse of the 3p seat-order study's finding for the roster as a whole.

**Reading.** The registered predictions were belief − greedy 0 to +2 and
oracle − belief 0 to +1. The first came out with the opposite sign: at
three players the greedy model, which applies every candidate action on
the real branch, beats the belief model's family-then-proxy pick by about
two points (p=0.07), and knowing the type from turn one recovers about
1.4 of that. Neither is significant at 90 games (detection limit ≈ 2), but
the direction is consistent across both contrasts and across seats 1 and
3, and it is what two modelled opponent turns per ply should do: the
approximation error of the within-family proxy (it ignores what a power
does on activation) compounds. At two players the same approximation was
worth ≈0; at three it costs ≈2. So the opponent-model question is **not
closed at three players**; it is priced: greedy's +2.1 costs +6.8 s a
decision, 0.31 points per second, the same rate as the fourth
determinization sample.

**Decision.** `belief` stays the default at every player count (the cost
argument that adopted it is stronger at 3p, where greedy averages 15.6 s a
decision), the greedy holdout keeps watching, and the next arm is the
obvious hybrid: **predict the family with the posterior, then pick within
the family by applying** — greedy's accuracy inside the one family that
matters, at roughly a quarter of greedy's cost. Registered:
`search_opponent_model="belief_apply"`, 3p design as above, prediction
+1 to +2 over `belief`; and a 2p check that it does not lose there.

Built the same day (`BeliefApplySearchOpponentModel`). Single-state 2p
probe, K=1, three mid-game states: decision 563 / 455 / 437 ms with
`belief`, **850 / 645 / 749 ms** with `belief_apply`, 1,050 / 973 / 882 ms
with `greedy` — the opponent turns cost 24, 200–370 and 400–440 ms
respectively. Restricting to one family halves greedy's opponent cost
rather than quartering it (the gain-food family alone can be most of the
legal list), so the price is +40–70% of a belief decision, not the
+20–40% first guessed. The 3p arm decides whether +2 points is worth it;
at 0.31 points per second it would be about break-even with the fourth
determinization sample.

**Result (2026-09-19).** `rr3p_belief_apply` vs `rr3p_opp/belief`: **−0.48
(p=0.21)**, win −0.011, **76 of 90 games identical**; 2p `rr_belief_apply`
vs `rr_belief_opp`: −0.61 (p=0.26), 63 of 80 identical, decision ×0.57 of
the old copy-path baseline. The registered +1 to +2 failed, and the way
it failed is the finding: applying inside the predicted family almost
never changes the pick — the proxy and greedy agree within a family. So
greedy's +2.1 at 3p does not come from *how* the opponent plays a family
but from *which* family the search assumes; the belief model's family
prediction is what costs the two points, exactly where the calibration
section above said the model is weak (its response likelihoods were never
fitted to the roster and classify action mix, not type). Not adopted; no
separate holdout (it would replay the belief model's game in 84% of
cases; the greedy holdout already guards the slot).

**Where this leaves the opponent model.** Ordered by what the arms say:
the family the search assumes matters at 3p (≈2 points), the type it
infers matters less (≈1.4 with an oracle), the pick inside the family not
at all. The fix is therefore the response model, not the inference:
refit `P(family | profile, candidate values)` to the roster from the
archive (about 6,000 recorded opponent decisions at 2p and 3p with public
candidate values), score it by log loss against the current hand-set
priors, and run one 3p arm with the fitted model. Registered prediction:
+1 to +2 over `belief` at 3p at no extra cost, closing most of the gap to
greedy; a null there means the family a scripted opponent plays is simply
not predictable from public values, and greedy's edge is the price of
applying — which the 5 s production cap could afford at 2p but not at 3p.

## The refit (2026-09-19): the family is not predictable from public values — by anyone

Registered above: refit `P(family | profile, candidate values)` to the
roster, score by held-out log loss, run one 3p arm if it wins. Built as
`analysis/fit_response_model.py` (extract: replay every archived game at
the current rules and record, at each of the 53,603 distinct opponent
decisions, the public candidate values the belief model sees and the family
chosen; fit: per roster kind, `logit(a) = log prior(a) + w(a)·v(a)` by
maximum likelihood; score: sequential predict-then-observe through 70
whole held-out games, leave-one-seed-out).

| Model | Held-out log loss | Top-1 family |
|---|---:|---:|
| uniform over available families | 1.386 | — |
| hand-set profiles (`DEFAULT_PROFILE_MODELS`) | 1.194 | 0.393 |
| fitted, per-family slope, posterior inference | 1.183 | 0.408 |
| fitted, true kind known from turn one | 1.244 | 0.392 |

The fit gains 0.011 nats a decision, is worse on `engine_builder`, and
knowing the kind is *worse* than inferring it — the mixture's per-game
drift across profiles is doing the work of features the model does not
have (round, cubes left, egg room, hand size). **Gate failed; the 3p arm is
not run.** The fitted table is written to
`configs/belief/fitted_response_models.json` behind
`search_belief_profiles="fitted"` so the switch exists, default `hand_set`.

The instructive number came from the benchmark. On the same 6,760 real
opponent decisions, the family each search opponent model would have
played (`artifacts/response_fit/greedy_family_match.txt`):

| Opponent kind | greedy model matches | belief model matches |
|---|---:|---:|
| `bonus_card_focus` | 0.45–0.47 | 0.50–0.54 |
| `engine_builder` | 0.44–0.46 | 0.46–0.47 |
| `net_value_response` | 0.35–0.39 | 0.36–0.42 |
| `greedy_immediate` | 1.00 | 0.49 |

The greedy model predicts the three archetypes' families *less* often
than the belief model does; its +2.1 at 3p is not concentrated in lineups
containing `greedy_immediate` (+4.5 in `bonus_card_focus+net_value_response`,
+1.0 in `engine_builder+greedy_immediate`). So greedy's edge is not
predictive accuracy about the real opponent, and `belief_apply` already
showed it is not the pick inside the family. What is left is the property
the two models differ in on **branch** states: greedy chooses a competent
family for the state the search has imagined — an opponent that takes the
tray card the plan wanted — while the belief model's temperature-2 priors
make the imagined opponent play nearly the same family in every branch,
whatever the searcher just did. The search gains from an opponent that
answers its plan, not from one that mimics the roster.

**Registered next: the competent-response opponent model.**
`search_opponent_model="competent"`: family = argmax of the public
candidate values on the branch state (the `VALUE_MAXIMIZING` profile at
temperature → 0, no posterior, no inference), pick inside by the existing
proxy. Cost equal to `belief`. Predictions: 3p **+1 to +2 over `belief`**
(recovering most of greedy's +2.1 at a fraction of its cost); 2p **0 to
+1**. A positive confirms responsiveness is the mechanism and retires
opponent-type inference from the search loop (the posterior remains
useful as telemetry and for the net-value agent); a null leaves greedy's
+2.1 as the price of applying, and the opponent-model programme moves to
self-play (`self_play_opponent_plan.md`), where the opponent is a planner.
