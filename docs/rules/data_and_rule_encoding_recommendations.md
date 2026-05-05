# Data and Rule Encoding Recommendations

Status: initial recommendations, 2026-05-03

This note answers the current data and rules open questions for the Wingspan AI simulator. It should guide the first content loader, power-handler mapping, expansion configuration, and rule traceability work.

## Recommendation Summary

| Question | Recommendation |
|---|---|
| Does `data/raw/wingspan-card-list.xlsx` contain enough structured information to encode all bird powers? | It is enough for card metadata and static scoring inputs, but not enough to execute every power without a translation layer. |
| Which card powers require hand-authored rule handlers? | Any timing-sensitive, conditional, choice-heavy, opponent-dependent, placement-changing, or expansion-specific power. |
| How should expansions be represented? | Use content packs plus rules modules. Avoid one giant alternate ruleset. |
| How should official rulebook references be tracked? | Use a rule registry that links encoded rules and power handlers to source documents, workbook fields, implementation modules, tests, and implementation status. |

## Workbook Sufficiency

`data/raw/wingspan-card-list.xlsx` is strong enough to seed the content catalog.

It contains structured fields for:
- Bird identity.
- Expansion/set.
- Power color.
- Raw power text.
- Predator, flocking, and bonus-card flags.
- Victory points.
- Nest type.
- Egg limit.
- Wingspan.
- Habitat eligibility.
- Food costs.
- Region/geography flags.
- Bonus-card eligibility columns.
- Bonus-card conditions and scoring text.
- Round-goal names and standard placement scoring.

The workbook is not, by itself, enough to execute all bird powers because `Power text` is natural language. The simulator should not attempt to infer all behaviour directly from prose.

Use the workbook for:
- Loading cards.
- Filtering content by expansion.
- Computing food costs.
- Validating habitat eligibility.
- Computing static final-scoring inputs.
- Applying bonus-card eligibility tags where already structured.
- Preserving source text for auditability.

Do not rely on the workbook alone for:
- Full power execution.
- Trigger timing.
- Multi-step card effects.
- Opponent responses.
- Deck-search logic.
- Special placement rules.
- Expansion-specific rule changes.
- Bonus-card scoring handlers.

## Power Translation Layer

Each power should have explicit metadata that separates raw source text from executable logic.

Recommended fields:

```yaml
power_text: "Discard 1 [egg] from any of your other birds to gain 2 [wild] from the supply."
power_color: brown
power_categories:
  - discard
  - gain_food
implementation_status: ready
handler_key: discard_egg_gain_wild_food
rules_modules:
  - base_game
source_refs:
  - workbook: data/raw/wingspan-card-list.xlsx
    sheet: Birds
    field: Power text
```

Recommended implementation statuses:

| Status | Meaning |
|---|---|
| `ready` | Executable handler exists and should be used in experiments. |
| `not_implemented` | Known but not yet executable. |
| `v1_no_op` | Ignored for v1 because expected strategic impact is low. |
| `expected_value_approximation` | Approximated as expected points/resources rather than exact rule resolution. |
| `heuristic_resolution` | Resolved with a simple deterministic or seeded policy. |
| `excluded_from_v1_deck` | Card/rule is removed from early experiment decks. |
| `must_implement_before_experiment` | Too strategically important to stub for the target experiment. |

## Hand-Authored Handler Categories

Start with reusable mechanic templates, then hand-author exceptions.

Reusable templates should cover:
- `gain_food`
- `lay_eggs`
- `draw_cards`
- `tuck_cards`
- `cache_food`
- `discard_to_gain`
- `discard_to_tuck`
- `draw_bonus_cards`
- `roll_for_cache`
- `all_players_gain`
- `all_players_lay_eggs`

Hand-authored handlers are required when a power has one or more of these traits:

| Power trait | Why it needs a hand-authored handler |
|---|---|
| Multi-step resolution | Order and conditional branches affect game state. |
| Opponent participation | "All other players may..." effects require response modelling. |
| Pink powers | Trigger outside the active player's turn. |
| Teal or yellow powers | Timing differs from normal activation. |
| Copy or repeat effects | Requires references to other powers and activation context. |
| Move/reposition effects | Mutates bird placement, habitat, or activation order. |
| Special placement | Sideways birds and replacement placement break normal board-slot assumptions. |
| Predator/hunt effects | Exact implementation depends on dice, deck, birdfeeder, or wingspan constraints. |
| Deck-search effects | Requires reveal, inspect, discard, cache, and stop conditions. |
| Bonus-card draw/discard effects | Requires private bonus-card state and choice policy. |
| Nectar effects | Requires Oceania-specific resource and scoring rules. |
| Hummingbird/Asia subsystem effects | Requires content-specific group handling and special actions. |

## V1 Fidelity Guidance

For first meaningful experiments, preserve the core economy loop:

```text
spend food/cards/eggs -> build habitat engine -> generate future resources/points -> compete for round goals -> maximize final score
```

Do not stub:
- Bird food costs.
- Habitat eligibility.
- Egg capacity.
- Core actions.
- Hand and card draw.
- Food generation.
- Egg laying.
- Tucking and caching as point sources.
- Round-end goals.
- Final scoring categories.

Good initial stubs:

| Edge case | Initial treatment |
|---|---|
| Rare card-specific powers | Mark as `not_implemented` or approximate expected value. |
| Complex predator roll logic | Use simplified success probability before exact dice/deck simulation. |
| Pink powers | Defer until opponent-turn reactions are modelled. |
| Copy/repeat powers | Defer or support only simple brown-power copying. |
| Many-target player choices | Use simple heuristic target choice. |
| Exact deck search/lookahead | Approximate expected value or exclude. |
| Round-goal/final-score tiebreakers | Stub unless evaluating close-match tournament outcomes. |
| Automa-specific rules | Keep separate unless solo/automa experiments are in scope. |
| Expansion-specific special resources | Defer until the base game is stable. |
| Unusual bonus-card scoring edge cases | Implement common scoring first, tag exceptions. |

## Expansion Representation

Represent expansions as **content packs plus rules modules**.

Content packs answer: "Which cards, bonus cards, round goals, or content are available?"

Rules modules answer: "Which mechanics, scoring rules, boards, player-count modes, or special procedures are active?"

Recommended content packs:

```yaml
content_packs:
  - core
  - european
  - oceania
  - asia
  - americas
  - promo_us
  - promo_europe
  - promo_asia
  - promo_nz
  - promo_ca
  - promo_uk
```

Recommended rules modules:

```yaml
rules_modules:
  - base_game
  - nectar
  - revised_player_mat
  - duet
  - flock
  - automa
  - expansion_scoring
```

Example ruleset:

```yaml
ruleset_id: core_oceania_v1
content_packs:
  - core
  - oceania
rules_modules:
  - base_game
  - nectar
  - revised_player_mat
player_count: 4
automa_enabled: false
```

This separation matters because some expansions mostly add cards, while others change resources, mats, player counts, scoring, setup, or automa behaviour. It also keeps the reusable board-game AI template cleaner for games beyond Wingspan.

## Rulebook and Source Traceability

Every encoded rule, scoring function, and special power handler should carry source metadata.

Recommended rule registry shape:

```yaml
rule_id: action.play_bird.pay_food_and_eggs
status: implemented
applies_to:
  content_packs:
    - core
  rules_modules:
    - base_game
source_refs:
  - document: rulebook_pdfs/WS_Core_Rulebook.pdf
    page: null
    section: Play a Bird
implementation:
  module: wingspan_ai.rules.actions.play_bird
tests:
  - tests/rules/test_play_bird.py::test_play_bird_pays_food
  - tests/rules/test_play_bird.py::test_play_bird_pays_egg_cost
notes: >
  Handles base food and egg costs. Expansion-specific discounts or replacement
  costs should be separate modifiers or handlers.
```

Recommended card-power registry shape:

```yaml
card_name: Chihuahuan Raven
power_handler_key: discard_egg_gain_wild_food
implementation_status: ready
source_refs:
  - workbook: data/raw/wingspan-card-list.xlsx
    sheet: Birds
    field: Power text
implementation:
  module: wingspan_ai.rules.powers.discard_egg_gain_food
tests:
  - tests/rules/powers/test_discard_egg_gain_food.py
```

For v1, source references can use `page: null` until rulebook page mapping is audited. Do not block simulator work on perfect citation metadata, but do require every rule and handler to have a stable `rule_id` or `handler_key`.

## Implementation Implications

Near-term implementation should:
- Keep raw `Power text` unchanged as source data.
- Add normalized `power_categories`.
- Add `implementation_status`.
- Add optional `handler_key`.
- Maintain a registry of handler keys and their tests.
- Let experiments filter by implementation status.
- Let unsupported mechanics appear in audit reports instead of being silently ignored.

Suggested first deliverable:

```text
docs/rules/power_handler_registry.md
```

That file should list every v1-supported power template, handler key, implementation status, sample source powers, and required tests.
