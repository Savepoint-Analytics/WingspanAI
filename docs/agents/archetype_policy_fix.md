# Archetype Policy Fix

Status: fixed and regression-guarded, 2026-08-31

## The finding

The 2026-08-31 round robin (`round_robin_v1.md`) showed
`archetype_engine_builder` and `archetype_bonus_card_focus` posting **identical
win rates in every single matchup** (0.500/0.500, 0.700/0.700, 0.900/0.900,
0.250/0.250, 0.650/0.650) with near-identical action mixes:

| Agent | draw | food | eggs | play |
|---|---:|---:|---:|---:|
| `archetype_engine_builder` | 18.8% | 48.5% | 18.8% | 13.9% |
| `archetype_bonus_card_focus` | 17.4% | 50.0% | 18.8% | 13.8% |

This contradicted the standing success criterion that each archetype should have
a measurable behavioural signature in telemetry.

## Root cause 1: archetypes with no opinion

`_engine_builder_bonus`, `_bonus_card_focus_bonus`, and `_round_goal_chase_bonus`
scored only `PLAY_BIRD` actions and returned `0` for everything else. Whenever a
bird was unaffordable — most early turns — those archetypes collapsed to
`_base_immediate_score`, which is plain greedy.

Worse, `_base_immediate_score` returns the *score delta*, which is 0 for both
`gain_food` and `draw_cards`. Ties resolve to the first maximum, and legal
actions are generated in the order play-bird, gain-food, lay-eggs, draw-cards.
So every opinionless archetype defaulted to **gain food**, which is exactly the
~49% gain-food signature observed.

Measured before the fix, on turn one with 10 legal actions:

| Archetype | Actions scored non-zero |
|---|---|
| `egg_focus` | 2/10 |
| `engine_builder` | 2/10 |
| `bonus_card_focus` | 2/10 |
| `round_goal_chase` | 2/10 |
| `food_acceleration` | 6/10 |
| `card_draw` | 6/10 |

## Root cause 2: bonus tags matched the whole game, not the held card

`_bonus_card_focus_bonus` scored `4 + 3 * len(card.bonus_card_tags)`. But every
one of the 180 birds carries tags for **all** bonus cards it could ever satisfy —
`Small Clutch Specialist` appears on 83 birds, `Bird Feeder` on 78, and so on.
The term was therefore a large near-constant that discriminated nothing, while
swamping the rest of the score.

The archetype scored **0.0 bonus points on average** — it was failing at the one
thing it is named for.

## Root cause 3: unbounded accumulation

`food_acceleration` and `card_draw` applied a flat `+8` to their signature
action. Unlike laying eggs (capped by egg capacity) or playing birds (capped by
affordability), gaining food and drawing cards are always legal, so those two
archetypes looped forever — 87.2% and 82.1% of actions respectively, scoring
21.7 and 11.0 points.

## Fixes

1. **Full-spectrum preferences.** Every archetype now scores all four action
   families, expressing how each family serves its strategy: enablers get
   moderate weight, off-strategy actions a small floor. All six archetypes now
   score 10/10 actions non-zero.
2. **Held-card tag matching.** `bonus_card_focus` intersects a bird's tags with
   the bonus cards the player actually holds, weighting `6.0` per genuine match.
3. **Diminishing returns.** `food_acceleration` decays its appetite once food
   stock exceeds what the hand can spend; `card_draw` decays once the hand is
   deep. Both now yield to playing birds when saturated.
4. **Egg-goal chasing.** `round_goal_chase` previously scored `LAY_EGGS` at 0,
   making every egg-based round goal literally unchaseable. It now recognizes
   egg goals and matching nest types.

## Result

Action mixes, five seeds against `random_legal`:

| Archetype | play | food | eggs | draw |
|---|---:|---:|---:|---:|
| `egg_focus` | 12.8% | 66.7% | **19.2%** | 1.3% |
| `engine_builder` | 19.2% | 55.1% | 11.5% | 14.1% |
| `food_acceleration` | 17.9% | **59.0%** | 15.4% | 7.7% |
| `card_draw` | 24.4% | 25.6% | 11.5% | **38.5%** |
| `bonus_card_focus` | 21.8% | 28.2% | 12.8% | 37.2% |
| `round_goal_chase` | 12.8% | **71.8%** | 15.4% | 0.0% |

`engine_builder` and `bonus_card_focus` — previously identical — are now
separated by an L1 distance of 0.539 on action mix.

`bonus_card_focus` bonus points rose from 0.0 to 2.0 (versus 0.8 for its nearest
neighbours), and its average score from 41.7 to 51.6.

## Remaining weakness

`card_draw` and `bonus_card_focus` are now the closest pair at L1 = 0.077,
because both lean on drawing. They separate on the dimension that matters —
bonus points scored — but not strongly on action mix. If sharper separation is
needed, `card_draw` should be re-specified around what it does with the cards it
draws rather than the draw rate itself.

## Diagnosed: why `bonus_card_focus` got *weaker* after the fix

The corrected agent fell from 9.0/10 to 6.0/10 in the baseline matrix, making it
the weakest archetype, even though its bonus points rose from 0.0 to 2.0.

Measured over 20 seeded openings:

- A player holds **one** bonus card. Against it, **83% of hand cards match
  nothing** (50 of 60 cards had zero matches; 10 had one).
- Consequently the play-bird bonus averages 5.14 while the draw-cards bonus is a
  flat 5.00 — effectively tied. The agent draws about as often as it plays
  (37.2% draw versus 21.8% play), which is backwards for a strategy defined by
  *playing* matching birds.

The v1 agent scored 9.0/10 for the wrong reason. Counting all tags gave every
bird roughly `4 + 3 x 8 = 28`, which made it an aggressive play-birds bot wearing
a bonus-card label. Aggressive bird-playing is a good strategy in this simulator,
so it won — while scoring 0.0 bonus points.

So the fix traded an accidentally-strong mislabeled agent for a faithful but weak
one. The deeper finding is that **bonus-card focus is genuinely weak here**: one
held card matches ~17% of hand cards, and bonus cards yield few points.

### Recommended tuning (not yet applied)

Raise the play-bird floor above the draw floor so the agent still converts, and
keep the match term as the discriminator rather than the driver:

```python
# play_bird: 6.0 + 6.0 * matches + (3.0 if bonus_card_power else 0.0)
# draw_cards: 3.0 + _hand_pressure(state)
```

Not applied because `baseline_matrix10_v2.md` was measured against the current
weights; changing them would make that row stale. This is a deliberate
hold, not an oversight.

## Regression guards

`tests/test_strategy_agents.py::ArchetypeDistinctnessTests` asserts:

- every archetype scores every legal action non-zero (the exact degeneracy above);
- each archetype's bonus function weights its signature family highest;
- accumulator archetypes show diminishing returns when saturated;
- `round_goal_chase` values laying eggs when the round goal is egg-based.
