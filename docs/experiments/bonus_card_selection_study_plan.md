# Bonus Card Selection Study

Status: **designed and launched 2026-09-16; predictions registered before the
arms ran.** Requested by Alex 2026-08-31; scope widened 2026-09-16 with two
synergy objectives (§4 and §5).
Code: `ForcedBonusCardSetupPolicy` (`agents/setup.py`), `forced_bonus_choice`
on the batch and round-robin flows, `analysis/bonus_card_seed_coverage.py`,
`analysis/bonus_card_keep_contrast.py`, `analysis/card_structure.py`.
Artifacts: `artifacts/bonus_keep/force0/`, `artifacts/bonus_keep/force1/`;
seed set `artifacts/bonus_keep/seeds_t8.json`.

## 1. Research question

**Which bonus cards are better choices to keep at the start, and what
circumstances make a given card the right keep?**

Setup deals 2 bonus cards and the player keeps 1. That single binary choice is
made before almost anything is known and commits the player to a scoring path
for the whole game.

Sub-questions:

1. **Is there a context-free ranking?** Are some cards simply better keeps?
2. **What makes a card situational?** Which cards pay off only given a
   particular opening hand, habitat spread, or round-goal set?
3. **How much does the choice matter?** Expected points between the better
   and worse keep of a dealt pair.
4. **Are some cards better because of what qualifies for them?** (Alex,
   2026-09-16.) Does a card's value come from inherent synergy with the birds
   that satisfy it — plentiful, cheap, high-scoring, egg-rich, strong powers —
   rather than from its printed tiers?
5. **The reverse, for birds.** (Alex, 2026-09-16.) Are some birds simply
   better picks because they work with good bonus cards and round goals, or
   are overpowered for their cost? §5 is the companion study.
6. **Do the agents currently choose well?** `PotentialPointsSetupPolicy`
   makes this choice today; how far from the hindsight-optimal keep is it?

Player count is deferred: the whole study runs at two players first.

## 2. Why it is ready now

- All 26 bonus-card scorers were rebuilt from the printed formulas and
  validated on 2026-09-03 (five had been wrong). The blocking prerequisite
  from the 2026-08-31 plan is closed.
- Both kept and discarded bonus cards are already logged
  (`setup_selection_applied`), so the counterfactual is identifiable.
- `random_seed` is the sole reproducibility key (ADR 0003), so two arms that
  differ only in the forced keep are matched on deck, tray, feeder, opponent
  deal and opponent play.
- The searching agent's decisions cost half what they did last week
  ([search_opponent_model_test.md](search_opponent_model_test.md)), which is
  what makes 222 games a single afternoon.

## 3. Design

### The instrument: forced keep

`ForcedBonusCardSetupPolicy(base_policy, dealt_index)` keeps the dealt card at
index 0 or 1 and lets the agent's usual opening policy choose birds and food
*conditional on that card*. So an arm measures "keep this card and play around
it", not "keep it and ignore it". Applied to the study agent only; the
opponent's setup is untouched, so the two arms differ in exactly one decision.

### Paired arms

- **Arm A** (`force0`): study agent keeps dealt card 0.
- **Arm B** (`force1`): study agent keeps dealt card 1.
- Same seeds, same lineup, seat rotation 0 (study agent in seat 1). Seat is
  identical in both arms, so counterbalancing adds nothing to the contrast;
  seat generality is a later question.
- `score_A − score_B` per seed is the value of card 0 over card 1 on that
  deal; each seed gives `+Δ` to the card kept in A and `−Δ` to the card kept
  in B.

### Sampling cards deliberately

Left to chance, 26 cards over a short seed range come out badly unbalanced.
`bonus_card_seed_coverage.py` scans seeds 1–600 (setup only, ~1 s), then
greedily picks the fewest seeds that give every card at least 8 paired units:
**111 seeds**, 8–11 units per card (`artifacts/bonus_keep/seeds_t8.json`).
The dealt pair depends on the seed alone, so this transfers to any roster
with the study agent in seat 1.

### Roster and settings

- Study agent: `potential_points` at defaults (depth 3, every turn, K=4,
  food candidates 6, belief opponent model with the 5% greedy holdout — the
  holdout falls on the same seeds in both arms).
- Opponent: `archetype_engine_builder` — mid-table, cheap, deterministic.
- Setup: `agent_default` for both seats (the study agent's own
  `PotentialPointsSetupPolicy` chooses birds/food around the forced card).
- 111 seeds × 2 arms = **222 games**, four runners, ~3–4 h.

### Analysis

`bonus_card_keep_contrast.py --arm-a force0 --arm-b force1` reports per card:
paired units, mean advantage over its dealt partners, paired-t p, win Δ,
realized bonus points when kept, and share of games where it scored at all.
Across deals: mean |Δ| (how much the choice matters) and the share of deals
swinging 5+ points. The study agent's own policy is scored in hindsight by
reconstructing each deal from the seed and asking the policy — no extra games.

`card_structure.py --bonus` gives every card's qualifying supply: count and
share of the deck, expected qualifiers in a 5-card opening hand, mean VP,
food cost, egg capacity, brown-power share, power score, and habitat split.
§4 correlates that with the measured advantage.

## 4. Registered predictions (written before the arms ran)

1. **The choice matters.** Mean |keep A − keep B| is **≥ 3 points**, and at
   least a quarter of deals swing 5+ points. Basis: realized bonus points run
   3–6 per game for the searching agent, and the forced card also changes
   which birds are kept.
2. **Per-bird cards with a broad supply beat high-threshold tiered cards.**
   At least two of {Omnivore Expert, Rodentologist, Falconer, Bird Counter}
   land in the top quartile of mean advantage, and at least two of
   {Bird Feeder, Backyard Birder, Oologist, Visionary Leader} in the bottom
   quartile. Basis: a two-player game plays roughly 10–12 birds, so tiers
   that need 5–8 qualifying birds are rarely reached, while "2 per bird"
   pays from the first qualifier.
3. **Synergy is real (§4 of the question).** Across the 22 bird-tagged cards,
   Spearman ρ between mean advantage and *expected opening-hand qualifiers ×
   points per qualifier* (per-bird cards: 2; tiered cards: top tier ÷ top
   threshold) is **≥ 0.3**. A null here would mean card value is mostly
   about what the agent does after setup, not what the deck supplies.
4. **The current policy is barely better than a coin flip.** In hindsight
   `PotentialPointsSetupPolicy` picks the better keep on **55–65%** of decided
   deals. Basis: `_potential_bonus_score` counts tag overlap with the five
   dealt birds only, and 83% of hand cards match nothing.
5. **Board-state cards are situational, not bad.** Breeding Manager (1 per
   bird with 4+ eggs) has above-median advantage for this egg-heavy agent
   (27% of its actions lay eggs); Oologist and Visionary Leader do not.

## 5. Companion: the bird-value study (planned, not yet run)

The reverse question. Three layers, cheapest first:

1. **Static features** (done: `card_structure.py --birds`): VP, food cost, egg
   capacity, nest, habitats, power colour and a power score, the number of
   bonus cards the bird satisfies, and a cost-efficiency figure
   `(VP + 0.5 × eggs + power score) / cost`. Once §3 has run, `--card-values`
   weights each bird's bonus coverage by the measured keep advantage of those
   cards, which is the "works well with good bonus cards" column.
2. **Realized value from telemetry** (needs one new event): a per-bird
   scorecard at game end — printed points, eggs on it, food cached, cards
   tucked, power activations (`bird_power_triggered` count), and the bonus
   cards and round goals it counted toward. Then a ridge regression of final
   score on birds-played indicators over every archived game, which is free
   given the artifacts, gives an observational "points per appearance" per
   bird, confounded by who plays it and when but broad.
3. **Causal, the same instrument as §3**: `ForcedBirdKeepSetupPolicy` —
   for a seed where bird X is dealt, arm A forces X into the kept opening
   hand (policy fills the rest), arm B forces it out. The paired Δ is the
   value of keeping X at setup. Sample birds deliberately the same way
   (`seed_coverage` generalizes to any dealt item). 180 birds × 8 units is
   ~720 seeds × 2 arms, so this runs in waves by feature class (cheap
   brown engines, high-VP predators, egg-capacity birds), not all at once.

Registered prior for layer 3, to be sharpened after §3: cheap brown birds
with tuck/cache powers and 3+ egg capacity outrank high-VP one-shot birds
at setup, because the searching agent's points come from round goals and
eggs as much as from bird points.

## 6. Caveats to carry

- **Pursuit quality confound.** A card can look weak because the agent
  pursues it badly. One pursuit policy in this wave; `archetype_engine_builder`
  as a second study agent is the planned replication.
- **Relative, not absolute.** A card's advantage is over the partners it was
  dealt with. Coverage balancing spreads partners, but a card that only met
  strong partners is under-rated by the advantage column and over-rated by
  its raw bonus points; read both.
- **Detection.** 8 paired units at a paired SD of ~9.5 resolves about
  ±7 points per card; the per-card table ranks, it does not certify.
  Pooled contrasts (per-bird vs tiered, broad vs narrow supply) carry the
  statistical weight.
- **Catalog composition.** The catalog's 26 bonus cards include
  `Anatomist [swift_start_asia]` (normalized to Anatomist) and `Visionary
  Leader`, while birds carry tags for `Diet Specialist` and `Bird Bander`,
  which are not in the deck. Which 26 the physical base game ships is a
  content question to settle before any of this is quoted as a Wingspan
  claim rather than a simulator claim.
- One opponent, two players, rotation 0.

## 7. Launch

```python
from flows.simulation_batch import run_simulation_batch

run_simulation_batch(
    seeds=CHUNK,                      # from artifacts/bonus_keep/seeds_t8.json
    player_agent_kinds=["potential_points", "archetype_engine_builder"],
    seat_rotation=0,
    setup_policy_kind="agent_default",
    artifact_root="artifacts/bonus_keep/force0",   # and force1
    batch_label="bkeep_f0_c3",
    forced_bonus_choice={"potential_points": 0},   # and 1
)
```

```bash
python analysis/bonus_card_keep_contrast.py \
    --arm-a artifacts/bonus_keep/force0 --arm-b artifacts/bonus_keep/force1
```

## 8. Result

_Not yet run._
