# Bonus Card Selection Study Plan

Status: requested by Alex 2026-08-31. Not yet designed in detail, not yet run.

## Research question

**Which bonus cards are better choices to keep at the start, and what
circumstances make a given card the right keep?**

Setup deals 2 bonus cards and the player keeps 1 (`STARTING_BONUS_CARD_COUNT = 2`).
That single binary choice is made before almost anything is known, and it commits
the player to a scoring path for the whole game.

Sub-questions:

1. **Is there a context-free ranking?** Are some bonus cards simply better keeps
   than others regardless of situation?
2. **What makes a card situational?** Which cards only pay off given a particular
   opening hand, habitat spread, food position, or round-goal set?
3. **How much does the choice matter?** Expected points, and expected win-rate
   delta, between the better and worse keep of a dealt pair.
4. **Does the right keep depend on player count?** Competitive green round goals
   and shared-resource contention both change with table size.
5. **Do agents currently choose well?** `PotentialPointsSetupPolicy` and the
   archetype policies already make this choice; how far from optimal are they?

## Why this is worth studying now

Three findings from 2026-08-31 make it concrete rather than speculative:

- A player holds one bonus card, and **83% of hand cards match nothing** against
  it (measured over 20 seeded openings: 50 of 60 hand cards had zero matches).
- Bonus cards yield few points in practice — roughly **2.0** for an agent
  actively pursuing them, against ~20-60 total.
- `archetype_bonus_card_focus` became the *weakest* archetype once it genuinely
  pursued its held card, while the version that ignored the card and just played
  birds aggressively scored 9.0/10. See `../agents/archetype_policy_fix.md`.

Taken together these suggest bonus cards may be a low-value, high-variance
scoring path in this simulator — but that has not been tested, and it may be an
artifact of which bonus cards get dealt or of weak pursuit rather than of the
cards themselves.

## Infrastructure that already exists

This study is cheaper than it looks; most of the pipeline is in place:

| Piece | Where |
|---|---|
| The keep/discard choice is a policy hook | `agents/setup.py`, `InitialSelectionContext` |
| Both kept **and discarded** bonus cards are logged | `setup_selection_applied` telemetry |
| Kept/discarded names exposed in SQL | `v_setup_selections` |
| Setup choice joined to final outcome | `v_setup_policy_outcomes` |
| Per-card scoring against a board | `_score_single_bonus_card` |
| Bird-to-bonus-card tag mapping | `BirdCard.bonus_card_tags` (all 180 birds tagged) |

Crucially, the telemetry already records the card **not** kept, which makes the
counterfactual identifiable without extra instrumentation.

## Design sketch

The natural design is a **forced-keep experiment**, because observational data
only shows the branch the policy chose:

- For each seed, deal the opening as normal.
- Run the game twice: once forcing the keep of card A, once forcing card B, with
  everything else identical. `random_seed` is now the sole reproducibility key
  (ADR 0003), so the two arms are matched.
- The paired difference in final score isolates the value of the keep decision,
  holding hand, deck, and opponent constant.

Requires a small addition: a setup policy that accepts a forced bonus-card
choice. Everything else exists.

Analysis dimensions to cross:
- bonus card identity (26 cards)
- opening hand composition (habitat spread, food cost, tag overlap with each card)
- round-goal set for the game
- player count
- the turn policy pursuing it

## Metrics

- Mean paired score delta per card, keep-A minus keep-B.
- Win-rate delta.
- Realized bonus points versus the card's theoretical ceiling.
- Completion rate: how often a kept card scores anything at all.
- Conditional deltas: value of card X given tag overlap with opening hand, given
  habitat spread, given player count.

## Caveats to plan around

- **Scoring coverage.** All 26 base bonus cards are covered by
  `_score_single_bonus_card`, but the handlers have not been individually
  validated against the rulebook appendix. Do that first — a card scoring wrongly
  would invert its ranking.
- **Pursuit quality confound.** A card can look weak because the agent pursues it
  badly rather than because it is weak. Run at least two turn policies.
- **Deal frequency.** Some cards will be dealt rarely across a seed set; the
  forced-keep design should sample cards deliberately rather than rely on random
  deals.

## Prerequisites

- [ ] Validate all 26 bonus-card scoring handlers against the rulebook appendix.
- [ ] Add a forced-bonus-card setup policy for the paired design.
- [ ] Decide the turn policies to hold constant.
- [ ] Confirm compute budget: 26 cards x paired arms x seeds is the cost driver.
