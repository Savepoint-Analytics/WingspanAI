# Opponent-Fit Denial: A Modelling Gap

Status: **implemented** 2026-09-02 (was: gap identified)

## The hypothesis (Alex, 2026-09-02)

The first player has a real advantage from uncontested first pick of the bird
tray, and the advantage should **strengthen with more players**.

The mechanism is not simply "gets the best card first". It is a decision problem
for the *later* players:

> Players after the starting player have to pick cards from their starting five,
> and can risk leaving one for a better one in the tray if they think it won't
> get picked up. This can happen because it's a card that aligns well with
> another card the player chose to keep, that likely won't align with the
> starting player's much — especially if it's niche.

So the strategic content is a **read on opponent fit**: a later player may safely
leave a niche tray card that only they can use, but must grab a card their
opponents also want. With more players, more opponents pick before the tray comes
back around, so the gamble gets worse and first pick gets more valuable.

## What the agents currently model

Checked 2026-09-02.

### `PotentialPointsAgent`: no denial at all

- Never references `bird_tray`.
- The string "denial" does not appear in the module.
- Its only opponent-aware component is `_round_goal_pressure`, which compares
  counts on the current competitive round goal.

It evaluates a tray draw purely by what the card does for **itself**. That
removing the card deprives an opponent is invisible.

### `NetValueOpponentResponseAgent`: denial exists, but is opponent-agnostic

`_tray_card_denial_value` sums `_public_card_threat_value(card)` over the taken
tray indices. That function has signature:

```python
def _public_card_threat_value(card: BirdCard) -> float
```

It takes **only the card**. No state, no opponent, no board. It scores intrinsic
strength: victory points, flocking, predator, bonus-card tags, and power-text
keywords.

### Why that is the wrong shape for this hypothesis

The hypothesis is about *niche* cards: low intrinsic value, high value **to one
specific opponent**. Intrinsic scoring rates those lowest:

| Card | VP | Habitats | Denial value |
|---|---:|---:|---:|
| Blue-Gray Gnatcatcher | 1 | 1 | 0.92 |
| Black Vulture | 2 | 1 | 0.64 |
| Bald Eagle | 9 | 1 | 1.88 |
| Baltimore Oriole | 9 | 1 | 1.88 |

A card that would complete an opponent's bonus card scores roughly a third of a
generically strong card. The decision Alex describes — leave it because they
can't use it, or take it because they can — is not representable.

## What an opponent-fit denial model would need

Denial value should be a function of `(card, opponent_public_state)`, not `card`:

1. **Bonus-card fit.** Opponent bonus cards are hidden, but the *number* held is
   public, and their revealed board implies which bonus cards are plausible.
   `BirdCard.bonus_card_tags` already maps every bird to the bonus cards it
   satisfies, so a belief over opponent bonus cards yields expected fit.
2. **Habitat fit.** A card is worth more to an opponent with room and engine
   depth in its habitat, which is fully public.
3. **Food affordability.** An opponent who cannot pay a card's cost soon is
   unlikely to use it; food tokens are public.
4. **Round-goal fit.** Whether the card advances the current competitive goal for
   that opponent.
5. **Nest-type fit** for egg-based goals and bonus cards.

Points 2-5 are computable from public state today. Point 1 needs the belief layer
in `wingspan_ai/belief/`, which already maintains a posterior over opponent type
and could be extended to a posterior over held bonus cards.

## Relationship to the seat-order results

Two seat-order studies found no effect larger than about 3.4 points at two
players — one with a roster that is 100% blind to tray-card identity, and one
with tray-aware agents. Neither tested the mechanism above, because **no agent
models opponent-fit denial**, so no agent can play the strategy that would
generate the advantage.

The 2-player null is therefore not evidence against the hypothesis. Testing it
properly requires implementing opponent-fit denial first.

## Decision

Keep the first-pick mechanic and keep investigating it, even though the measured
2-player effect is near zero. The measured null reflects agent capability, not
necessarily game structure.

## Implementation (2026-09-02)

All five signals listed above are now modelled.

### Denial reuses the owner-side valuation
`_tray_card_denial_value` estimates what a card would do on each opponent's
board by calling `_played_power_value` — the same routine that values a played
bird for its owner — driven by `_public_expected_habitat_activations`, a
public-information mirror of the owner-side activation estimate.

| Property | Before | After |
|---|---|---|
| Repeatable brown vs one-shot white | Gnatcatcher 0.92 < Goldfinch 1.16 | 1.02 > 0.36 |
| Tempo | constant | 1 turn 0.23 -> 16 turns 1.92 |
| No habitat room | unchanged | 0.00 |
| Cannot afford | ignored | discounted by shortfall |

### Bonus-card fit via a hidden-card posterior
`wingspan_ai/belief/bonus_cards.py` infers which bonus cards an opponent holds
from the tags on their **played** birds. Because every bird satisfies many bonus
cards, raw tag counts are dominated by common tags; the estimator compares each
tag against the average tag count on that opponent's own board, so a tag well
above their own average is the signal of pursuit. Mass is scaled to the number of
bonus cards they actually hold, which is public.

Worked example — opponent board of four bowl-nest birds, holding one bonus card:

| Inferred bonus card | P(held) |
|---|---:|
| Wildlife Gardener | 0.449 |
| Cartographer | 0.136 |
| Passerine Specialist | 0.136 |

Denial then values a card by expected fit against that posterior:

| Card | VP | Bonus fit | Denial |
|---|---:|---:|---:|
| Song Sparrow (niche, bowl nest) | **0** | 0.72 | 0.79 |
| Bald Eagle (generic strong) | 9 | 0.04 | 1.13 |

A **zero-point** card now scores 70% of a nine-point card's denial value, driven
almost entirely by bonus fit. Under the previous intrinsic-strength model it
would have scored near zero. This is the exact case the hypothesis identified.

### Information boundary preserved
The posterior reads only played birds and `bonus_card_count`, both public. A test
asserts denial is unchanged when an opponent's hidden hand *contents* change at
fixed hand count.

## Next steps

- [ ] Run the seat study at 3+ players with tray-aware agents (in progress).
- [ ] Implement `opponent_fit_denial_value(card, opponent_public_state)` using
      habitat room, food affordability, round-goal fit and nest type.
- [ ] Extend the belief module to a posterior over opponent bonus cards, then add
      expected bonus-card fit to the denial term.
- [ ] Re-run the seat study with a denial-aware agent at 2, 3 and 5 players. Only
      then is the hypothesis genuinely tested.
- [ ] Separately: fix tray-card blindness in greedy and the six archetypes, which
      is a defect regardless of its seat-effect implications.
