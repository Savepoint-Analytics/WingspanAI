# Hidden player choices inside power handlers

Status: audited 2026-10-08. **16 handlers, 112 of the 180 base-game birds with
powers (62%).** Nothing here is a bug report against the power registry — see
*What "complete coverage" does and does not mean* below.

## The question that started it

Alex, on the eight cards that read *"If this bird is to the right of all other
birds in its habitat, move it to another habitat"* (Song Sparrow and siblings):

> I found that these birds can be quite useful at obtaining additional food,
> eggs or bird cards when played early. However, I can easily see its play
> potential to be badly under-utilized in the simulations so far. How does this
> card and other cards like it assess how to play it?

It does not assess it. The destination is chosen by one line inside the
transition function:

```python
target_habitat = min(candidates, key=lambda item: (len(player.habitats[item]), item.value))
```

Move to the habitat with the **fewest birds**, tie-broken alphabetically
(forest → grassland → wetland). In the real game the destination is the
player's decision, and "emptiest habitat" is close to the opposite of good
play: the emptiest row is usually the one with the weakest payoff and the least
reason to activate.

Asking how many other powers are like it produced this audit.

## The inventory

Every handler where a decision the rules give the player is resolved by a fixed
rule inside `base_game.py`:

| handler | cards | what the engine decides |
|---|---:|---|
| `tuck_card` | 21 | which card to tuck; which bird gets the egg |
| `draw_bonus_cards_keep_one` | 15 | which bonus card to keep |
| `gain_food_from_birdfeeder` | 13 | which die to take |
| `lay_egg` | 12 | which bird to lay on |
| `play_additional_bird` | 10 | which bird to play |
| **`move_bird_habitat`** | **8** | **destination habitat** |
| `draw_cards_then_discard` | 8 | which card to discard |
| `gain_food_from_supply` | 7 | which wild food |
| `discard_egg_gain_wild_food` | 5 | which food; which egg to spend |
| `draw_card` | 3 | which card |
| `all_players_lay_eggs` | 3 | which bird — for *every* player |
| `each_player_gains_birdfeeder_food` | 2 | which die — for every player |
| `repeat_brown_power` | 2 | which brown power to repeat |
| `trade_food_with_supply` | 1 | which food to give and which to get |
| `fewest_birds_gain_food` | 1 | which food |
| `draw_cards_player_select` | 1 | which card to keep |

**Total: 112 of 180 powered birds (62.2%).**

Genuinely mechanical, for contrast: `predator_hunt` (14), `pink_reaction` (12),
`deck_search_tuck_by_wingspan` (10), `cache_food` (5), `draw_tray_cards` (1 —
you take all three), `discard_to_tuck` (5 — the food type is printed on the
card), `no_power` (6).

The shared chooser helpers are `_choose_discard_card_for_food`,
`_place_eggs_on_player_birds`, `_gain_preferred_food_from_birdfeeder` and
`_preferred_food_for_hand`. Finding those is the reliable way to re-run this
audit; a regex for `min(`/`max(`/`sorted(` alone both over- and under-counts
(it flags bounds checks like `min(tuck_count, len(deck))` and misses handlers
that delegate to a helper).

## Three severities, which should not be lumped together

**1. The heuristic looks actively wrong.** `move_bird_habitat`, 8 cards.
Measured on the archive: these birds end the game **buried behind a later bird
51.6% of the time** (1,030 of 1,998 on final boards), so the power is dead more
often than not. Per card the burial rate runs 42.3% (Common Nighthawk) to 59.0%
(Chimney Swift). Because each successful move appends the bird to the end of
another habitat — making it rightmost again — a 51.6% burial rate means the
agent routinely plays a bird to the right of it *before* the row is next
activated. That is a sequencing failure, not luck.

**2. The heuristic is sensible but invisible to the search.** Most of the rest.
Keeping the highest-scoring bonus card and taking the food you need are
reasonable defaults. The cost is not that they are bad; it is that the search
**cannot plan around them**. When the evaluator considers playing a tuck bird it
cannot ask "what if I tuck the card I would rather keep?", because that branch
does not exist in the action space.

**3. Forced activation of an optional power.** A separate gap in the other
direction: several of these read "you *may*" in the rulebook and fire
unconditionally here. `discard_to_tuck` triggers whenever the player holds the
food. The agent cannot decline.

## Why this is invisible to the whole experimental apparatus

These choices happen inside the transition function, after the agent has
committed to an action. So:

- **No arm can measure them.** Every registered arm in `results_ledger.md`
  varies something in the *evaluator* or the *search*. A hardcoded power choice
  is outside both.
- **The near-tie instrument cannot see them either.** It reads the agent's
  ranked candidates, and these decisions never become candidates.
- **They do not appear in any manifest.** A batch records the search config and
  the setup policy; it does not record that `tuck_card` picked the discard for
  21 different birds.

## What "complete coverage" does and does not mean

`power_handler_registry.md` says *"complete base-game coverage, 2026-08-31"*,
with a workbook-backed assertion. That is true and worth keeping: every
base-game power **does something**, and nothing silently no-ops.

It says nothing about whether the *player chooses*. The case study's "every
base-game bird power handled" is accurate on the same reading and easy to
misread as "every power is played well". Both documents now link here.

## Measured impact, where it has been measured

Only `move_bird_habitat` has numbers so far:

| | the 8 movers | other brown birds |
|---|---:|---:|
| times played | 1,998 | 68,640 |
| mean activations | 2.28 | 3.91 |
| mean round played | 2.55 | **2.13** |
| **power yield recorded as zero** | **99.0%** | 21.1% |

The 99% is the mechanism behind the under-utilisation Alex noticed: the move
produces no food, eggs or cards, so the telemetry records an empty
`power_yield` and the evaluator — which prices birds substantially on what
their powers produce — sees **nothing**. The whole value is positional, and
position is what the valuation cannot see. The agent plays them *later* than
other brown birds (2.55 vs 2.13) when the human read is that they are strong
played early.

One caveat on the activation gap: `activations` increments when a power
*triggers*, before the handler checks rightmost-ness, so 2.28 vs 3.91 reflects
later placement and weaker rows rather than burial. The burial figure above is
measured separately from end-of-game slot positions.

## Fixing one of these is real work

Lifting a decision into the legal-action space changes the action enumeration,
which changes replay validation and breaks bit-identity with the archive. It is
a per-handler project, not a config switch, and it widens the search's branching
factor — which the cost ledger prices at roughly 1.7 points per doubling of
thinking time, in the other direction.

Suggested order, by expected value rather than card count:

1. **`move_bird_habitat` (8 cards)** — the only one where the heuristic looks
   wrong rather than merely unoptimised, and the one with evidence.
2. **`lay_egg` (12) and `tuck_card` (21)** — the largest card counts, and
   "which bird gets the egg" interacts with egg capacity and the round goals,
   which is where the project's one real evaluator win came from.
3. **`draw_bonus_cards_keep_one` (15)** — bonus-card choice is independently
   measured at 6.4 points, and this handler makes that choice for 15 cards
   without the search's involvement.

Before building to make these cards better, measure whether they *are* better:
the counterfactual rollout instrument (`play_counterfactuals.py`) can price a
mover play against its alternative on archived states with no new simulation.

## Re-running the audit

    grep -nE "^def (_choose|_preferred|_place_eggs|_gain_preferred)" \
        src/wingspan_ai/rules/base_game.py

then check which `handler_key` dispatch arms reach each helper. Card counts come
from the catalog's `power.handler_key`.
