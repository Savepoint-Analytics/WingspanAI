# Bonus Card Selection Study

Status: **complete, 2026-09-16.** Four of five registered predictions held; the
synergy prediction reversed and the reversal is the finding.
Requested by Alex 2026-08-31; scope widened 2026-09-16 with two synergy
objectives (§4 and §5). Run at `010cf7b` (clean worktree; every manifest
records it).
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

222 games (111 seeds × forced index 0/1), all replays valid, all manifests
`dirty: false` at `010cf7b`. 12 of 222 games (5.4%) fell in the greedy
holdout — the same seeds in both arms, so pairing is unaffected. Wall clock
3 h 06 min on four runners. Report:
`analysis/bonus_card_keep_contrast.py --arm-a artifacts/bonus_keep/force0 --arm-b artifacts/bonus_keep/force1`.

### Predictions scored

| # | Prediction | Result | |
|---|---|---|---|
| 1 | Choice worth ≥3 points; ≥25% of deals swing 5+ | **6.41 points**; 64 of 111 (58%) swing 5+; max 29 | holds |
| 2 | Per-bird broad-supply cards top; high-threshold tiered cards bottom | Falconer #1, Bird Counter #2, Omnivore #3 (3 of 4 named); Oologist #21, Bird Feeder #24 (2 of 4 named) | holds |
| 3 | Spearman ≥ 0.3, advantage vs *expected hand qualifiers × points per qualifier* | **ρ = −0.40** | **reversed** |
| 4 | Current policy right on 55–65% of decided deals | **52 of 105 (50%)** | direction holds; it is a coin flip |
| 5 | Breeding Manager above median; Oologist and Visionary Leader not | Breeding Manager +1.00 (rank 12/26); Oologist −3.12; Visionary Leader −1.33 | holds |

### The keep decision is worth about six points

A dealt pair differs by 6.4 points on average — the deal-to-deal SD of the
paired delta is 8.0 and the largest swing was 29 — against a ~78-point
agent whose whole opponent-to-opponent spread is a few points. Setup is
the single most valuable decision this agent makes badly: its own policy
picks the better side exactly half the time.

### Per-card ranking (paired advantage over the card's dealt partners)

| Card | n | Advantage | p | Bonus pts when kept |
|---|---:|---:|---:|---:|
| Falconer | 8 | **+7.00** | 0.043 | 5.25 |
| Bird Counter | 11 | **+6.36** | 0.045 | 5.91 |
| Omnivore Expert | 8 | **+4.38** | 0.050 | 6.62 |
| Wildlife Gardener | 9 | +3.33 | 0.251 | 6.67 |
| Prairie Manager | 8 | +2.75 | 0.507 | 4.12 |
| Platform Builder | 8 | +2.62 | 0.177 | 3.75 |
| Passerine Specialist | 8 | +2.62 | 0.372 | 4.00 |
| Food Web Expert | 8 | +2.12 | 0.304 | 6.00 |
| Anatomist | 8 | +1.75 | 0.565 | 4.50 |
| Photographer | 8 | +1.62 | 0.342 | 3.88 |
| Rodentologist | 8 | +1.25 | 0.692 | 6.38 |
| Breeding Manager | 8 | +1.00 | 0.727 | 5.38 |
| Wetland Scientist | 9 | 0.00 | 1.000 | 3.56 |
| Fishery Manager | 8 | −0.75 | 0.736 | 5.50 |
| Ecologist | 8 | −1.00 | 0.637 | 4.12 |
| Cartographer | 8 | −1.00 | 0.697 | 4.75 |
| Visionary Leader | 9 | −1.33 | 0.404 | **8.44** |
| Backyard Birder | 9 | −2.44 | 0.302 | 4.22 |
| Forester | 9 | −2.44 | 0.225 | 4.33 |
| Historian | 8 | −2.75 | 0.353 | 6.00 |
| Oologist | 8 | −3.12 | 0.201 | 4.88 |
| Large Bird Specialist | 10 | **−3.30** | 0.020 | 3.60 |
| Nest Box Builder | 8 | −3.38 | 0.190 | 4.38 |
| Bird Feeder | 9 | −3.89 | 0.104 | 5.78 |
| Enclosure Builder | 10 | −4.80 | 0.145 | 4.60 |
| Viticulturalist | 9 | −5.44 | 0.061 | 4.67 |

Eight units per card resolves about ±7 points, so only the ends reach
significance; the ranking is the deliverable, the p-values are not. The
pooled contrasts carry the weight:

| Payoff shape | paired units | Mean advantage | p |
|---|---:|---:|---:|
| **per bird** (2 per qualifier; Breeding Manager 1) | 51 | **+3.25** | **0.009** |
| tiered (3–4 points at a low threshold, 6–8 at a high one) | 138 | −0.93 | 0.16 |
| board state (Oologist, Ecologist, Visionary Leader, Breeding Manager) | 33 | −1.12 | 0.31 |

### Synergy: real, but it is not breadth (prediction 3, reversed)

The registered metric — expected qualifiers in the opening hand × points per
qualifier — was meant to capture "a card is good when the deck supplies it".
It correlates **negatively** (ρ = −0.40) with measured value, because it is
dominated by tiered cards with broad supply: Forester, Enclosure Builder and
Bird Feeder score highest on the metric and sit in the bottom third of the
table. Their tiers need 4–8 qualifying birds on one 10–12-bird board split
across three habitats, and pay nothing until the threshold.

Exploratory (post hoc, not registered) correlations across the 22 bird-tagged
cards say where the synergy actually lives:

| Feature of the card or its qualifiers | ρ with advantage |
|---|---:|
| per-bird payoff (1/0) | **+0.49** |
| points per qualifier | +0.39 |
| qualifiers' mean power score | **+0.39** |
| qualifiers' brown-power share | +0.34 |
| qualifiers' mean VP | +0.09 |
| qualifiers' mean egg capacity | −0.18 |
| qualifiers' mean food cost | −0.26 |
| **deck share** (breadth) | **−0.37** |

So the answer to Alex's question 4 is yes, with a specific shape: a bonus
card is a good keep when **every qualifier pays** and **the qualifiers are
engine birds the agent wants to play anyway**. Bird Counter's qualifiers are
96% brown powers with the highest power score in the table; Falconer's are
100% brown predators. Breadth of supply is, if anything, a warning sign,
because the broad cards are the tiered ones.

### Bonus points printed ≠ value of keeping

Realized bonus points when kept correlate only ρ = 0.15 with keep advantage.
Visionary Leader scores the most bonus points of any card (8.44) and has a
negative keep value (−1.33): holding cards to score it costs more tempo than
the points return. Reading a bonus card by what it scored is the wrong lens;
the value is in what pursuing it does to the rest of the game.

### The current opening policy is a coin flip

`PotentialPointsSetupPolicy` picked the hindsight-better card on 52 of 105
decided deals. `_potential_bonus_score` counts tag overlap with the five
dealt birds, which this study shows is nearly uninformative: the strong cards
pay per qualifier drawn over the whole game, not per qualifier in hand. A
policy that simply preferred per-bird cards would have been right more often
than the current one on this data. That is the cheapest improvement the study
suggests and it should be built behind a switch and measured, not assumed.

### Companion bird table, weighted by measured card value

`card_structure.py --birds --card-values artifacts/bonus_keep/card_values.json`
sums each bird's bonus coverage by the cards' measured keep advantage. The
top of that column is dominated by cheap brown birds that qualify for
Falconer, Bird Counter and Omnivore Expert at once (Greater Roadrunner +18.0,
both hummingbirds +13.7, Ferruginous Hawk +11.9); the bottom by birds whose
tags are all tiered cards (Wild Turkey −17.4, Northern Flicker −16.2, Wood
Duck −16.0). That is a feature for the bird-value study (§5), not a result:
it inherits every caveat above and says nothing about the bird's own play.

### Decision

- The per-card table and the pooled per-bird effect are the project's first
  strategy findings about content rather than about agents, and they came
  from 222 games in three hours. Quote the pooled effect (+3.25, p=0.009)
  and the six-point stake; quote individual cards as a ranking with the
  ±7-point resolution attached.
- Next arm on this question: replicate with `archetype_engine_builder` as
  the study agent (pursuit confound). If the per-bird effect survives a
  non-searching pursuer, it is about the cards.
- Build `PerBirdPreferenceSetupPolicy` (or a learned keep scorer on these
  111 deals) behind a switch; its success criterion is >60% hindsight
  accuracy on a fresh seed set, then a paired arm against the current
  policy.
- Bird-value study §5 layer 2 (per-bird scorecard event) is next after that.

### Caveats

- One pursuit policy, one opponent, two players, seat 1 only.
- Relative advantage over dealt partners; coverage balancing spreads partners
  but does not equalize them.
- The catalog composition question (§6) stands: Anatomist and Visionary
  Leader are in, Diet Specialist and Bird Bander are not.
