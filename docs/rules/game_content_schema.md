# Game Content Schema

Status: initial Pydantic schema, 2026-05-03

The initial machine-readable content schema lives in `src/wingspan_ai/content/schemas.py`.

## Models Added

| Model | Purpose |
|---|---|
| `BirdCard` | Bird identity, expansion pack, habitats, food cost, points, nest, eggs, wingspan, power metadata, and source row. |
| `BonusCard` | Bonus-card condition text, content packs, scoring text, prevalence, and future scoring handler metadata. |
| `RoundGoal` | End-of-round or map-style goal name, content pack, scoring values, reverse goal, and rules module. |
| `FoodCost` | Fixed food symbols plus wild, choice, and variable food-cost indicators. |
| `Power` | Power color, text, category tags, implementation status, and optional handler key. |
| `RulesetMetadata` | Simulation ruleset ID, content packs, rules modules, player count, automa flag, seed, and version. |
| `ContentCatalog` | Validated bundle of birds, bonus cards, round goals, and rulesets. |

## Important Enums

- `ContentPack`: core, chronological expansions, promos, and fan art content.
- `RulesModule`: base game, nectar, revised mat, duet, flock, automa, and expansion scoring.
- `FoodType`: invertebrate, seed, fish, fruit, rodent, nectar, and wild.
- `Habitat`: forest, grassland, and wetland.
- `PowerColor`: white, brown, pink, teal, yellow, and none.
- `PowerImplementationStatus`: ready, not implemented, v1 no-op, expected-value approximation, heuristic resolution, excluded from v1 deck, or must implement before experiment.

## Design Notes

- The schema accepts unsupported powers as data, but requires `ready` powers to name a `handler_key`.
- `BirdCard.wingspan_cm` can be null when `wingspan_is_variable=true`, which supports cards marked with `*` in the workbook.
- `RulesetMetadata` separates `content_packs` from `rules_modules`, matching the project decision that expansions are content packs plus rules modules rather than one giant alternate ruleset.
- `RoundGoal` can represent standard end-of-round scoring and later duet/map goals by switching `rules_module`.

## Related Design Notes

- `docs/rules/wingspan_card_list_audit.md` documents what the workbook can and cannot provide directly.
- `docs/rules/data_and_rule_encoding_recommendations.md` defines the recommended power translation layer, hand-authored handler categories, v1 fidelity threshold, expansion representation, and rulebook traceability approach.
