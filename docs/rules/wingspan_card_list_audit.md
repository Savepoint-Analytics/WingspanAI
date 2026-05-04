# Wingspan Card Workbook Audit

Status: source audit, 2026-05-03

Source workbook: `wingspan-card-list.xlsx`

## Sheets

| Sheet | Rows | Columns | Missing expected columns | Extra source columns |
|---|---:|---:|---|---|
| Birds | 707 | 65 | None | Flavor text, geography flags, fan-art metadata, and bonus-card tag columns |
| Hummingbirds | 40 | 8 | None | Anatomist, Cartographer, Photographer |
| Bonus | 60 | 7 | None | None |
| Goals | 56 | 7 | None | None |

Ignored workbook artifact sheets:

- `__Solver__`
- `__Solver___conflict218311158`
- `__Solver___conflict1916279113`
- `__Solver___conflict1288898709`
- `__Solver___conflict952169930`

## Expansion Coverage

### Birds

| Content pack | Rows |
|---|---:|
| core | 180 |
| european | 81 |
| oceania | 95 |
| asia | 90 |
| americas | 111 |
| promo_us | 25 |
| promo_europe | 25 |
| promo_asia | 25 |
| promo_nz | 25 |
| promo_ca | 25 |
| promo_uk | 25 |

### Bonus Cards

| Content pack | Rows |
|---|---:|
| core | 26 |
| european | 7 |
| oceania | 5 |
| asia | 16 |
| americas | 9 |

Some bonus cards belong to multiple packs in the workbook, such as `core, asia`.

### Goals

| Content pack | Rows |
|---|---:|
| core | 16 |
| european | 10 |
| oceania | 8 |
| asia | 12 |
| americas | 10 |

## Field Issues

| Count | Sheet | Field | Issue |
|---:|---|---|---|
| 12 | Birds | Wingspan | Non-numeric `*`; normalize as variable or unknown wingspan. |
| 12 | Goals | round-end scoring | Placement scoring columns are blank; these are likely duet/map goals. |
| 8 | Birds | Nest type | Blank nest type; normalize to an explicit special/non-nesting category. |
| 7 | Bonus | VP | Bonus scoring text is blank; likely needs hand-authored scoring rule. |
| 6 | Birds | Color | Blank power color; normalize to `PowerColor.NONE` only after confirming no power. |
| 4 | Birds | Beak direction | Unexpected values `LR` or `LL`; add normalization mapping or review source. |

## Normalization Needs

- Map workbook set labels such as `promoUS` and `promoEurope` to snake-case `ContentPack` values.
- Convert food symbols into `FoodCost.fixed`, `wild_food_count`, `choice_food_count`, and `variable_food`.
- Convert habitat flag columns into a `set[Habitat]`.
- Convert `Color` blanks to `PowerColor.NONE` only when the card truly has no power text.
- Decide how blank `Nest type` values should be represented before rules tests depend on nest categories.
- Convert `Wingspan` value `*` to `wingspan_is_variable=true` with `wingspan_cm=null`.
- Convert `Beak direction` values `L`, `R`, and `N` to normalized enum values.
- Decide whether multi-direction values `LR` and `LL` are valid Asia metadata or source errors.
- Parse `VP` scoring text on bonus cards into hand-authored scoring handlers over time.
- Split duet/map goals from standard end-of-round goals because they do not use scoring columns `1` through `4`.

## Related Recommendations

See `docs/rules/data_and_rule_encoding_recommendations.md` for the recommended interpretation of this audit:

- The workbook is sufficient for static card metadata and content loading.
- Raw `Power text` is not sufficient for full executable power logic without a power translation layer.
- Expansion labels should map to content packs, while game-changing mechanics should map to separate rules modules.
- Encoded rules and hand-authored power handlers should carry source references, implementation status, and test references.

## Reproducible Audit Command

```bash
PYTHONPATH=src python -m wingspan_ai.content.workbook_audit wingspan-card-list.xlsx
```
