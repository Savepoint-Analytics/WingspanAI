# Scoring Handler Audit

Status: initial coverage utility, 2026-05-16

## Purpose

Scoring handlers should be auditable before simulation results become public-facing strategy claims. The first code utility lives in `src/wingspan_ai/rules/scoring_audit.py` and reports which loaded bonus cards and round goals are currently covered by implemented scoring logic.

## Current Coverage Direction

The audit is intentionally conservative:

- Supported bonus cards are matched by explicit handler names.
- Unsupported bonus cards remain visible instead of silently scoring as zero.
- Round goals are considered supported only when they use currently implemented bird, egg, nest, habitat, set, or total-bird patterns.

## How To Use

```python
from wingspan_ai.content.loader import load_base_game_content_catalog
from wingspan_ai.rules import audit_scoring_coverage

catalog = load_base_game_content_catalog()
audit = audit_scoring_coverage(catalog)
print(audit.bonus_card_coverage, audit.unsupported_bonus_cards)
print(audit.round_goal_coverage, audit.unsupported_round_goals)
```

## Remaining Work

- Compare every supported handler against the local rulebook PDFs before using results in public case-study claims.
- Source references currently identify the core rulebook path and source section; add exact page numbers after PDF page mapping.
- Add test references per scoring handler.
- Extend the audit to expansion-specific scoring once expansion rules modules are active.
