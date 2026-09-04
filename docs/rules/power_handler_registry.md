# Power Handler Registry

Status: complete base-game coverage, 2026-08-31

## Purpose

Bird powers should never silently disappear from experiments. Each executable or planned handler needs traceable metadata connecting card text, rulebook sources, implementation modules, tests, and current fidelity.

The first registry lives in `src/wingspan_ai/rules/power_registry.py`.

## Current Entries

| Handler | Status | Purpose |
|---|---|---|
| `no_power` | `no_op_for_v1` | Explicit no-op for birds without powers. |
| `gain_food_from_birdfeeder` | `heuristic_resolution` | Deterministic handler for common one-die food-gain powers, including hand-need food preference. |
| `draw_card` | `heuristic_resolution` | Deterministic handler for simple draw-one-card powers. |
| `lay_egg` | `heuristic_resolution` | Deterministic handler for simple lay-one-egg templates. |
| `tuck_card` | `heuristic_resolution` | Deterministic handler for simple tuck-one-card templates, including tuck-then-draw variants. |
| `cache_food` | `heuristic_resolution` | Deterministic handler for simple cache-one-food templates. |
| `pink_reaction` | `heuristic_resolution` | First deterministic hooks for opponent-turn lay-egg, gain-food, cache, and tuck reactions. |
| `predator_hunt` | `heuristic_resolution` | Deterministic seeded approximation for predator hunt rolls. |
| `discard_egg_gain_wild_food` | `heuristic_resolution` | Spends an egg and gains food prioritized by visible hand needs. |
| `discard_to_tuck` | `heuristic_resolution` | Spends required food and tucks cards from the deck when available. |
| `gain_food_from_supply` | `heuristic_resolution` | Adds fixed food directly to the player's supply. |

## Registry Fields

- `handler_key`: stable key referenced by content.
- `implementation_status`: same enum used by card powers and scoring rules.
- `source_reference`: rulebook, workbook, or design source.
- `rulebook_page`: printed rulebook page used for the current handler's source reference.
- `module_path`: implementation location once available.
- `test_reference`: test file or case once covered.
- `notes`: implementation notes or simplification warnings.

## Coverage

As of 2026-08-31 the base-game workbook reports **174/174 powered cards classified
and implemented** (was 125/174, 71.8%). `tests/test_power_handlers.py` guards this
with a workbook-backed coverage assertion.

## Handlers Added 2026-08-31

| Handler | Cards | Notes |
|---|---:|---|
| `draw_bonus_cards_keep_one` | 15 | Keeps the bonus card scoring highest on the current board. |
| `play_additional_bird` | 10 | Plays the best affordable hand bird; bounded recursion depth. |
| `move_bird_habitat` | 8 | Only when rightmost; moves to the emptiest habitat. |
| `draw_cards_then_discard` | 8 | Discard resolved immediately rather than at end of turn. |
| `all_players_draw_cards` | 5 | Was misclassified as a self-only draw. |
| `all_players_lay_eggs` | 3 | Was dead code; generic `lay_egg` matched first. |
| `discard_egg_draw_cards` | 2 | Optional cost always taken when an egg exists. |
| `repeat_brown_power` | 2 | Cannot target other repeat powers. |
| `each_player_gains_birdfeeder_food` | 2 | Was misclassified as a self-only gain. |
| `fewest_birds_draw_cards` | 2 | Was unconditional; now compares habitat counts. |
| `fewest_birds_gain_food` | 1 | Was unconditional; now compares habitat counts. |
| `draw_cards_player_select` | 1 | Opponent selection is not modelled as a choice. |
| `draw_tray_cards` | 1 | Takes the tray, then refills it. |
| `trade_food_with_supply` | 1 | Trades most-abundant for most-needed. |

`draw_card` and `gain_food_from_supply` now parse counts rather than assuming one.

## Remaining Work

- All handlers are `heuristic_resolution`, not `ready`. Choice-heavy powers use
  deterministic heuristics rather than agent decisions; see each entry's `notes`.
- Promote high-impact choices (which bird to play, which brown power to repeat,
  which habitat to move to) into real agent decisions via `LegalAction`.
- Filter by handler status with `power_status_filter` / `excluded_power_handler_keys`
  when a comparison must exclude an approximated mechanic.
