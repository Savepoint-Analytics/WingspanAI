# Base-Game Bonus-Card Composition

Status: settled 2026-09-16 from the workbook's `Bonus` sheet (`Set` column).

## The question

The catalog's 26 core bonus cards include `Anatomist [swift_start_asia]` and
`Visionary Leader`, while every bird carries `bonus_card_tags` for `Diet
Specialist` and `Bird Bander`, which are not in the deck. Before quoting any
bonus-card finding as a claim about Wingspan rather than about the simulator,
the deck had to be confirmed against the source.

## Answer

The workbook's `Set` column is explicit:

| Card | Set | In the core deck? |
|---|---|---|
| Anatomist | `core, asia` | yes — a core card that the Asia swift-start pack reprints; the `[swift_start_asia]` suffix is a workbook naming artifact that `normalize_bonus_name` strips |
| Cartographer, Photographer | `core, asia` | yes, same pattern |
| Visionary Leader | `core` | yes |
| Bird Bander | `european` | no — European expansion |
| Diet Specialist | `european` | no — European expansion |

So the 26 cards the simulator deals are exactly the workbook's `core` set.
Birds are tagged for expansion cards because the `Birds` sheet carries one
column per bonus card across all sets; the tags are inert until the matching
expansion pack is enabled. The loader's tag column list
(`content/loader.py`) includes both expansion names for that reason.

## What it means for findings

`docs/experiments/bonus_card_selection_study_plan.md` can be read as a claim
about the base-game deck, subject to its other caveats (one pursuit policy,
two players, per-card resolution). The composition caveat there is closed.

## Revisit if

The European pack is enabled: the deck grows to 31 and Bird Bander / Diet
Specialist join the ranking, with their tags already in place.
