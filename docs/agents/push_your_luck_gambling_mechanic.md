<!-- Context Summary: The user requested a Markdown file containing the mathematical expected value (EV) thresholds and optimal stop strategies for the push-your-luck ("gambling") birds in Wingspan Asia. This formats the previously provided analysis into clean, downloadable Markdown. -->

# Wingspan Asia: Gambling Bird Optimal Strategy Guide

The Wingspan Asia expansion introduces a "push-your-luck" gambling mechanic where players roll food dice or draw cards sequentially up to three times, risking a complete bust if they fail on subsequent attempts. 

To maximize your long-term score, the exact mathematical expected value (EV) cut-offs tell you to **always push for a second die roll** with high-odds predators, but **stop drawing cards if your current total wingspan reaches 65 cm**.

---

## 🃏 Card-Drawing Predators ("Blackjack" Birds)
The **Eurasian Marsh-Harrier** and **Eurasian Eagle-Owl** require you to draw up to 3 cards. You bust if the total cumulative wingspan hits 110 cm or more. 

| Current State | Combined Wingspan Threshold | Optimal Action | Statistical Justification |
| :--- | :--- | :--- | :--- |
| **After 1st Draw** | **Under 65 cm** | **Draw Card #2** | ~82% chance the first card is valid. Pushing is positive EV if under 65 cm. |
| **After 1st Draw** | **65 cm or Higher** | **STOP & Tuck** | At exactly 65 cm, you have a 50.4% chance to bust on the next card. |
| **After 2nd Draw** | **Under 39 cm** | **Draw Card #3** | The deck average is too high to risk a third draw unless your buffer is huge. |
| **After 2nd Draw** | **39 cm or Higher** | **STOP & Tuck** | Pushing here yields negative EV over time; bank your 2 points. |

---

## 🎲 Dice-Rolling Predators ("Push-Your-Luck" Birds)
These birds use the custom Wingspan dice. Rolling an invalid face busts all food collected during that turn.

### 1. White-throated Kingfisher
* **Hit Targets:** Fish, Invertebrate, or Rodent (4 out of 6 die faces).
* **Success Rate:** **66.7%** per roll.
* **Optimal Strategy:** **Always roll at least twice.** 
* **The Math:** If you stop after 1 success, you gain 1 food. If you push for a 2nd roll, your expected value scales to **1.33 food** (0.667 × 2). After a successful second roll, you are perfectly indifferent to rolling a 3rd time (EV stays flat at exactly **2.00 food**), making a 3rd roll mathematically optional.

### 2. Forest Owlet
* **Hit Targets:** Strictly specific food items matching its card text (3 out of 6 die faces).
* **Success Rate:** **50.0%** per roll.
* **Optimal Strategy:** **Never roll a third time.**
* **The Math:** After 1 success, pushing for a 2nd roll yields an identical EV of **1.00 food** (0.50 × 2), making you mathematically indifferent on roll two. However, if you succeed on the 2nd roll and hold 2 food, rolling a 3rd time drops your EV down to **1.50 food** (0.50 × 3). **Always bank your 2 food tokens.**

---

# Review Against Card Text and Deck Data

Added 2026-09-04. Card text and wingspan data read from the workbook
(707 birds, 695 with wingspan). **One conclusion above is wrong and reverses.**

## Correction: Forest Owlet rolls two dice, not one

Printed text:

> Choose any **2** [die]. Roll them up to 3 times. Each time, if you roll **at
> least 1** [invertebrate] or [rodent], cache 1 here. If not, stop and return all
> food cached here this turn.

The guide above treats this as a single die at "3 out of 6 faces, 50.0%". The
card rolls **two** dice and succeeds if **either** shows a hit:

| Quantity | Value |
|---|---:|
| P(one die shows invertebrate or rodent) | 0.500 |
| P(at least one of two dice) | **0.750** |

Recomputing:

| Holding | Bank | Push | Correct action |
|---:|---:|---:|---|
| 1 food | 1.00 | 0.75 x 2 = **1.50** | **PUSH** |
| 2 food | 2.00 | 0.75 x 3 = **2.25** | **PUSH** |

So the Forest Owlet should **always push all three times**, the opposite of the
"Never roll a third time / always bank your 2 food" advice above. The error came
from applying the single-die success rate to a two-die power.

Note the per-die 3/6 is right only because the sixth die face shows
invertebrate + seed and therefore counts as an invertebrate: invertebrate covers
two faces, rodent one. See `docs/rules/birdfeeder_dice.md`.

## Confirmed: White-Throated Kingfisher

Printed text: "Choose any 1 [die]. Roll it up to 3 times. Each time, if you roll
a [invertebrate], [fish], or [rodent], cache 1 here."

One die, hits on invertebrate (2 faces), fish (1), rodent (1) = **4/6 = 0.667**,
as stated. Holding 1, push gives 1.33 > 1.00. Holding 2, push gives exactly 2.00
— genuinely indifferent, as the guide says.

## Refined: Eurasian Eagle-Owl thresholds

Printed text: "Up to 3 times, draw 1 [card] from the deck. When you stop, if the
birds' total wingspan is less than 110 cm, tuck them behind this bird. If not,
discard them."

Computed by exact dynamic programming over the empirical wingspan distribution of
the core + Asia deck (270 birds, mean 64.1 cm, **median 42 cm** — the
distribution is strongly right-skewed, which is why the mean misleads here):

| State | Guide above | Computed | Action |
|---|---:|---:|---|
| Before any draw | — | EV 1.11 VP | always draw |
| After 1 card | stop at 65+ | **stop at 68+** | draw below 68 cm |
| After 2 cards | stop at 39+ | **stop at 44+** | draw below 44 cm |

The guide's thresholds are close and directionally right; the computed values are
slightly more aggressive. The difference is deck composition — thresholds shift
with which expansions are in the deck, so they should be **derived at runtime
from the actual deck**, not hardcoded.

A note on the stated justification: "~82% chance the first card is valid" is not
the right framing, because the first card can never bust on its own (no bird has
wingspan ≥ 110 cm except variable-wingspan cards). The real decision is entirely
about the *second and third* draws.

The guide also names a "Eurasian Marsh-Harrier" as a card-drawing predator. No
such bird is in the workbook; only the Eagle-Owl matches this pattern. Worth
checking before relying on it.

## Implementation status: unmodelled

No push-your-luck handler exists. `power_registry.py:548` classifies predator
powers by matching `"predator"`, `"roll all dice"` or `"roll any"`, and resolution
routes to `predator_hunt`, a single-attempt success check. The sequential
push-and-bust structure is absent, so:

- Sequential attempts are not simulated.
- The stop decision is never made — there is no policy hook for it.
- `_registered_per_trigger_power_value` values `predator_hunt` at a flat 0.45
  regardless of the bird, so a gambling bird and an ordinary predator score alike.

## How this should be handled

1. **Add a `push_your_luck` handler key** distinct from `predator_hunt`, carrying
   attempts allowed, the hit condition, and the bust rule.
2. **Make stopping a policy decision, not a rules constant.** The rules should
   offer "roll again or bank" as a choice; the agent decides. Hardcoding optimal
   play into the rules engine would make the mechanic untestable as strategy and
   would violate the separation the project maintains elsewhere.
3. **Derive thresholds at runtime** from the live deck for card-based birds, and
   from the die model (`content/birdfeeder.py`) for dice-based ones. Both already
   have the primitives.
4. **Value the food by need, not by count.** The EV figures above treat food as
   linear. An agent needing exactly one invertebrate should bank earlier than one
   converting surplus into cached points — the indifference points above are
   where that consideration decides the play.
5. **Weight by risk posture.** Pure EV is right in the long run; a bot behind on
   the final round should accept negative-EV pushes for variance, and one ahead
   should bank. This is the same variance-versus-mean argument as in
   `pink_power_valuation.md`.

## Priority

Low until expansion content is enabled — all three birds are Asia. But item 1
should be recorded now so these powers are not silently resolved as ordinary
predators when Asia is switched on, which would produce plausible-looking and
wrong results.
