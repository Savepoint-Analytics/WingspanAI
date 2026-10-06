# The joint opener: adopted on mechanism, 2026-10-06

Status: **adopted as the default** (`potential_points_setup_v4`), with the
previous opener (`..._v2`) held out in 5% of games. **No arm was run**, and the
reason is the point of this document.

## Where it came from

Alex, preparing to play the ten human games, observed that a human chooses
birds, bonus card and starting food *in tandem* and with all four round goals
face up, and asked whether the agent could do the same.

It could not, in two ways: it chose the **bonus card first**, scored against all
five dealt birds including the ones it was about to discard, and
`goal_horizon` defaulted to `"first"`, so it read only round 1's goal.

## What measurement found, including two of my own claims it killed

| Claim | Measured |
|---|---|
| "choosing bonus-then-birds loses points" | **false.** Joint enumeration is never *strictly* better: 0 of 240 openings. In 89 (37%) it picks a *different* bonus card at an **identical score** — a tie, not a gain |
| "reading all four goals matters" | **barely.** `goal_horizon="all"` changes the opening in **1 hand in 240** |
| "the fix works because it prices the bonus against the kept cards" | **mostly false.** The opener keeps all five birds in **570 of 600** openings, so the kept set *is* the dealt hand; subset pricing changes the figure in **0.3%** of openings |

The 37% tie rate was the clue. `_selection_score`'s only bonus-dependent terms
were `_bonus_alignment_score` — a hand-written if-chain covering about a dozen
named cards and returning **0 for every other card** — and whatever the card
scorer did with it. Meanwhile `expected_bonus_points`, which prices *every* card
from its parsed scoring rule and printed prevalence, was used only to make the
initial pick.

**So the good scorer saw the wrong card set and the crude one made the
decision.** Enumerating jointly over a function that cannot tell the two cards
apart buys nothing, which is exactly what the 0-of-240 result says.

## The change

`bonus_scoring="joint"` enumerates `(bonus card × keep set × food)` together,
prices the bonus **inside** the loop with `expected_bonus_points`, drops the
crude alignment term so it is not counted twice at two different qualities, and
breaks the frequent ties with the richer scorer so joint enumeration cannot be
arbitrarily worse than choosing first.

It changes the opening in **9.6% of hands** (15 of 240 a different bonus card,
8 of 240 different birds) — 24× the all-goals switch.

The driver is the in-loop pricing, not the kept subset: **36 of 41 bonus-card
changes happen at keep==5**, where the kept set and the dealt hand are the same
cards. The bonus is now chosen by the whole opening score *including* its
expected points, rather than by its expected points alone followed by a crude
alignment tie-break.

## Why there is no arm

| what would be measured | games needed at 80% power |
|---|---:|
| the population effect (~0.2 points) | **21,609** |
| the conditional effect on the 9.6% of hands that change | 972 (~2.7 h), limit 2.08 |

A conditional effect measured at that limit multiplies back to **0.20 points**
population-wide. Standing registration rule 1 says that when no affordable
sample can clear the band, do not launch — decide on mechanism and say so. This
is the first time that rule has stopped an arm **before** the compute was spent
rather than after.

**Adopted on mechanism**, on three grounds:

1. It strictly dominates under its own scoring function, by construction: the
   joint maximum is over a superset of the sequential one, and ties are broken
   by the richer scorer rather than iteration order.
2. The defect it fixes is a plain error — the sophisticated scorer was pointed
   at the wrong card set — not a judgement call about weights.
3. It makes the agent capable of the coordination a human does, which the ten
   human games need for the comparison to be fair. The measured size of that
   coordination advantage, ~0.2 points, is itself the answer to the fairness
   objection.

What adoption does **not** claim: that the agent is stronger. Nobody has
measured that and nobody affordably can.

## The bigger thing this turned up

**The opener keeps all five birds, and therefore zero starting food, in 95% of
hands.** A five-bird no-food opening is poor play by convention — you cannot
play anything until you have earned food — and the joint opener only moves it to
four birds 29 times in 600.

The keep count is already known to be mispriced in the other direction too:
forcing three birds (`..._v3_keep3`) measured **−1.9**. So neither "keep
everything" nor "keep three" is right, and the trade between a kept bird and a
kept food token is not understood. That is a larger prize than anything in this
document and it has never been studied directly.

Registered as the follow-up: measure the realized value of a starting food token
against a kept bird, from archived openings, before proposing a keep rule.

## Reproducing the measurements here

    python - <<'PY'
    from wingspan_ai.agents.setup import potential_points_setup_policy, InitialSelectionContext
    from wingspan_ai.rules.base_game import setup_base_game
    # compare any two policy ids over N deals; see tests/test_joint_opener.py
    PY

`tests/test_joint_opener.py` pins the adoption, the enumeration, the scorer
contract and the mechanism. One of those tests exists because the first version
of this change shipped with a **vacuous** assertion — it checked that subset
pricing differed from dealt-hand pricing, which never happens at keep==5, and
the vacuity guard is what caught the overstated mechanism.
