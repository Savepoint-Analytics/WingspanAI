# Power Handler Registry

Status: initial skeleton, 2026-05-04

## Purpose

Bird powers should never silently disappear from experiments. Each executable or planned handler needs traceable metadata connecting card text, rulebook sources, implementation modules, tests, and current fidelity.

The first registry lives in `src/wingspan_ai/rules/power_registry.py`.

## Current Entries

| Handler | Status | Purpose |
|---|---|---|
| `no_power` | `no_op_for_v1` | Explicit no-op for birds without powers. |
| `gain_food_from_birdfeeder` | `not_implemented` | Planned handler for common food-gain powers. |
| `draw_card` | `not_implemented` | Planned handler for common draw-card powers. |

## Registry Fields

- `handler_key`: stable key referenced by content.
- `implementation_status`: same enum used by card powers and scoring rules.
- `source_reference`: rulebook, workbook, or design source.
- `module_path`: implementation location once available.
- `test_reference`: test file or case once covered.
- `notes`: implementation notes or simplification warnings.

## Near-Term Additions

- Add handler keys during content normalization for cards whose power text matches known templates.
- Implement high-volume base powers first: gain food, draw cards, lay eggs, tuck/cache, predator hunt.
- Let experiment configs filter by handler status before running strategic comparisons.
