# Pooled holdout guardrail, 2026-10-04

First read since the guardrail was built. Eight default-agent roots pooled
(`rr_goal_placement`, `rr3p_goal_place15/25`, `rr_reroll_base`,
`rr_reroll_pen2`, `rr_prerank_v2`, `rr3p_oracle15`, `rr_prod_placement`):
**640 `potential_points` seats**, of which 2,360 games across the whole archive
carry holdout records.

Every decided switch keeps its losing side in a deterministic 5% of games, keyed
`holdout:{field}:{seed}:{lineup}:{position}`. Assignment is therefore
pseudo-random and **unpaired** — the comparison is between different games, so
deck luck is randomised rather than differenced out. That matters for reading the
table below.

## The six fields

| field | preferred | n | held out | n | Δ score | p | Δ win | p | limit |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| **`round_goal_model`** | placement 80.11 | 569 | heuristic 72.48 | 71 | **+7.64** | **<0.001** | −0.082 | 0.015 | 3.5 |
| `search_opponent_model` | belief 79.42 | 514 | greedy 76.40 / oracle 79.76 | 42 / 84 | +3.02 | 0.105 | — | — | — |
| `search_prerank` | none 79.79 | 450 | beam_leaf 78.03 | 190 | +1.76 | 0.096 | +0.005 | 0.865 | 3.0 |
| `mechanic_synergy` | False 79.37 | 587 | True 78.11 | 53 | +1.26 | 0.576 | +0.152 | 0.018 | 6.3 |
| `setup_policy` | v1 79.25 | 621 | v3_keep3 79.95 | 19 | −0.70 | 0.795 | −0.121 | <0.001 | 7.5 |
| `search_child_expansion` | fast 79.27 | 637 | copy 78.67 | 3 | +0.60 | 0.963 | +0.190 | 0.568 | 36.9 |

Six fields × two metrics is **twelve tests**, so Bonferroni is p < 0.004. Only
two clear it: `round_goal_model` on score, and `setup_policy` on win rate. The
second is **19 held-out games against a 7.5-point detection limit** and is
discarded as noise, which is what the instrument's own "too few to read" warning
says.

## The one real finding, and it disagrees with the arms

`round_goal_model` is the only survivor, and it is a surprise:

| source | design | Δ score |
|---|---|---:|
| guardrail, 2026-10-04 | unpaired, 640 seats, 71 held out | **+7.64** |
| `rr3p_goal_place25` arm | paired, 25 decks | +1.12 |
| `rr_goal_placement` arm | paired, 2p | +0.41 |

**A seven-fold disagreement between a randomised unpaired read and two paired
arms is not something to average.** Three candidate explanations, none tested:

1. **Pairing is the more precise design and the arms are right.** The guardrail
   pools 2p and 3p, and pools games where *other* holdouts also fired, so a
   held-out game can differ from its comparison set in more than one switch. With
   71 games that contamination does not average out.
2. **The guardrail is right and the arms understate it.** The arms compared
   placement against the heuristic in a *fully placement-tuned* agent; the
   holdout flips one seat's goal model inside an otherwise-current agent, which
   is a different quantity.
3. **Selection on the holdout key.** The draw is deterministic in
   `(field, seed, lineup, position)`, so the held-out 11% is a *fixed* subset of
   decks rather than a fresh draw per game. If those decks are unusual for goal
   scoring, the effect is deck luck, and 71 games cannot distinguish that from a
   real effect.

Explanation 3 is the one I would test first and it is cheap: the held-out set is
computable without running anything, so the deck composition of the held-out
games can be compared to the rest directly.

**Nothing changes on the strength of this read.** The placement model is already
the adopted default, so the guardrail agrees with the decision and only disputes
its size — and rule 3 of the standing registration rules says a re-read nominates
and never settles. Recorded as a nomination.

## Retirement: nothing qualifies yet

The task was to retire fields past the 100-game bar that agree with their
decision. Measured against that bar:

| field | held-out games | past 100? | agrees with its decision? |
|---|---:|---|---|
| `search_prerank` | 190 | **yes** | yes (+1.76 for the preferred `none`) |
| `search_opponent_model` | 126 | **yes** | yes (+3.02 for `belief`) |
| `round_goal_model` | 71 | no | yes, but disputes the size |
| `mechanic_synergy` | 53 | no | yes |
| `setup_policy` | 19 | no | unreadable |
| `search_child_expansion` | 3 | no | unreadable |

Two fields are past the bar and agree with their decision, so by the stated rule
`search_prerank` and `search_opponent_model` are retirable. **I am not retiring
them yet**, for one reason: both sit *below* their own detection limits (+1.76
against 3.0, and +3.02 at p=0.105), so "agrees with its decision" means "is not
measurably different from it", which is weaker than the rule's wording implies.
Retiring on that basis would remove the control that would eventually detect a
mistake.

Recommendation: raise the retirement bar to **the point estimate is inside the
detection limit *and* the limit is under 2 points**, which neither field meets
yet, and keep pooling. The tax is 5% of games per field; at six fields that is
real but not urgent.

## Reading this instrument again

    python analysis/holdout_guardrail.py artifacts/rr_goal_placement \
        artifacts/rr3p_goal_place15 artifacts/rr3p_goal_place25 \
        artifacts/rr_reroll_base artifacts/rr_reroll_pen2 \
        artifacts/rr_prerank_v2 artifacts/rr3p_oracle15 artifacts/rr_prod_placement

Pass roots explicitly. A shell-built root list silently produced "No games with
holdout records found" on the first attempt, which looked like an instrument
failure and was not.
