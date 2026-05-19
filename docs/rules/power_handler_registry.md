# Power Handler Registry

Status: initial skeleton, 2026-05-04

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
- `module_path`: implementation location once available.
- `test_reference`: test file or case once covered.
- `notes`: implementation notes or simplification warnings.

## Near-Term Additions

- Add handler keys during content normalization for cards whose power text matches known templates.
- Continue moving current text-template checks behind registry-backed handler keys.
- Implement remaining high-volume base powers first, especially opponent-choice powers, "all players may" choices, deck-search powers, and exact predator constraints.
- Let experiment configs filter by handler status before running strategic comparisons.
