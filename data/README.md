# Data

Machine-readable source data and generated content artifacts.

- `raw/`: unmodified source files such as card spreadsheets or extracted rule inputs.
- `processed/`: normalized data generated from loaders or audits.
- `reference/`: stable lookup tables and hand-authored content mappings.

Keep raw source files unchanged. Write normalization logic in `src/wingspan_ai/content/`.

Current raw source:

- `raw/wingspan-card-list.xlsx`: canonical local workbook path used by loaders, audits, tests, and smoke flows. Override with `WINGSPAN_CARD_WORKBOOK` when needed.
