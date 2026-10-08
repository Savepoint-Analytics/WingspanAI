# Which card gets discarded, and what that costs

Status: audited 2026-10-08. The card guardrail is **better than the egg one** —
it considers bonus-card fit, which `egg_spend_order` does not. Three gaps
remain, and the sharpest is that the agent is never offered the choice.

Companion to `egg_spending_fidelity.md` and `hidden_power_choices.md`.

## Where cards get discarded

| site | cards affected | what happens |
|---|---|---|
| **forest "spend a card for extra food"** | every forest turn at 1 or 3 forest birds | the player action itself |
| `tuck_card` power | 21 birds | tuck a card from hand behind this bird |
| `draw_cards_then_discard` power | 8 birds | draw N, then discard one |
| gain-food-and-tuck powers | some of the 1,629-line branch | gain food, then tuck a card |

All four route through `_choose_discard_card_for_food`, which is
`min(player.hand, key=discard_priority)`.

## The guardrail that exists, and it is a good one

`discard_priority` ranks a card on **what it can still do for this player**,
ascending, lowest discarded first:

    (bonus_fit, has_room, affordable, victory_points, -food_cost, name)

Its docstring records the bug it fixed: the previous rule was printed points
alone, which "would discard a cheap bird that completes a held bonus card in
order to keep an unaffordable high-point bird that will never be played."

That is a real improvement and it is **ahead of the egg equivalent**: eggs are
ranked on round-goal protection with no bonus-card input at all, while cards are
ranked on bonus-card fit first. The two guardrails were written against
different threats and neither learned from the other.

## Gap 1 — the agent chooses *whether*, never *which*

This is the one that matters most, because it is a player-facing action offered
on most forest turns rather than a power resolution.

`_legal_gain_food_actions` calls `_choose_discard_card_for_food` **while
building the action list** and bakes the result into every variant. Measured on
seed 11 with a three-card hand and one forest bird:

```
spend-a-card actions offered : 7
distinct discard choices     : 1  -> {'Cedar Waxwing'}
    Gain invertebrate and invertebrate by discarding a card (Cedar Waxwing)
    Gain invertebrate and seed by discarding a card (Cedar Waxwing)
    Gain invertebrate and fruit by discarding a card (Cedar Waxwing)
```

Seven actions, seven food combinations, **one** card. The search can weigh which
*food* to take against giving up a card, and cannot weigh giving up one card
against another. A human picks the card last, knowing what the food is for.

This is the `hidden_power_choices.md` pattern appearing in the **action space**
rather than inside a power handler, which makes it both more visible and more
consequential.

## Gap 2 — `bonus_fit` is blind to the four count-based bonus cards

`bonus_fit` is `|held bonus names ∩ card's bonus_card_tags|`. It only sees cards
whose condition is a *property of a bird*. Four of the 26 base-game bonus cards
have **zero tagged birds**, because their condition is a property of the
*board*:

| card | condition | why no bird carries the tag |
|---|---|---|
| **Visionary Leader** | bird cards in hand at end of game | every card counts, no card qualifies |
| **Ecologist** | birds in your habitat with the fewest birds | depends on board shape |
| Oologist | birds with ≥1 egg | depends on eggs (see the egg audit) |
| Breeding Manager | birds with ≥4 eggs | depends on eggs (see the egg audit) |

`Visionary Leader` is the severe case for card discards. It scores **bird cards
in hand at game end**, so *every* card in hand is worth points — and `bonus_fit`
is 0 for all of them. Demonstrated: the discard choice is identical whether the
player holds `Cartographer`, `Historian` or `Visionary Leader`.

```
holding Cartographer      -> discards Cedar Waxwing   bonus_fit: 0,0,0
holding Visionary Leader  -> discards Cedar Waxwing   bonus_fit: 0,0,0
holding Historian         -> discards Cedar Waxwing   bonus_fit: 0,0,0
```

So the term that exists to protect bonus cards is **identically useless** on the
one card for which every discard is a direct loss. For the other 22, `bonus_fit`
works — `Historian` alone has 20 tagged birds.

## Gap 3 — `state` is accepted and never used

`discard_priority(card, player, state=None)` takes a state, every caller passes
one, and **the body never references it**. So nothing about the board or the
round can influence a card discard.

Unlike the egg case, this is **mostly harmless in the base game**, and it is
worth saying so rather than reporting a symmetric defect. None of the 16
base-game round goals involves cards or tucked cards — they are all birds in
habitats, eggs by habitat or nest type, or total birds. There is simply nothing
card-shaped to protect.

What it does cost: three goals count **birds in a named habitat**
(`[bird] in [forest]`, `[bird] in [grassland]`, `[bird] in [wetland]`) and one
counts `total [bird]`. When the active goal is `[bird] in [forest]`, discarding
your only affordable forest bird is worse than discarding a wetland bird, and
`discard_priority` cannot tell the difference — `has_room` and `affordable` are
proxies for playability in general, not for the habitat the goal is counting.
That is a genuine but narrower gap than the egg one.

Minor inconsistency alongside it: one call site
(`resolved_card_name = card_name or _choose_discard_card_for_food(player)`)
omits `state` where the other four pass it. Harmless while `state` is unused,
and a trap the moment it is not.

## What is not a gap

- **Tucking is not losing.** A tucked card is 1 VP at game end, so `tuck_card`
  converts a card into a point rather than destroying it. The discard choice
  still matters — you would rather tuck the card you cannot play — but the
  downside is bounded in a way that spending a card for food is not.
- **The ordering within the tuple is sensible.** Unplayable before unaffordable
  before low-value, and among equals the more expensive card goes first because
  it is harder to play. No complaint there.
- **The agent can decline.** Spending a card for food is an optional action, so
  the search can refuse it outright. That is its only lever, which makes the
  pre-chosen card more load-bearing, not less.

## Suggested order

1. **Offer the discard as a choice** (gap 1). Enumerate one spend-a-card variant
   per card in hand instead of one per food combination. This widens the action
   space — 7 actions became 21 in the measured case — which the cost ledger
   prices at roughly 1.7 points per doubling of thinking time in the other
   direction, so it needs the beam pre-ranking already in the production config.
   It also changes replay validation and breaks bit-identity with the archive.
2. **Give `bonus_fit` a count-based branch** (gap 2). `Visionary Leader` wants a
   flat penalty on *any* discard; `Ecologist` wants habitat shape. Both are
   board conditions, so this is the same fix shape as the egg audit's defect 1 —
   and doing them together is cheaper than twice.
3. **Use `state` for habitat goals** (gap 3), or delete the parameter. An
   accepted-and-ignored argument is worse than no argument, because the next
   reader assumes it works.

All three sit behind `VALUE_RESOURCE_SPENDING` and are testable the way the
2026-09-04 ablation was — which read **null** at 200 games an arm. Expect small
again. The case for 2 and 3 is correctness; the case for 1 is that it is a real
decision the agent has never been allowed to make.
