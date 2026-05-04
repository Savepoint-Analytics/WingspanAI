# Project Package Structure

Status: initial foundation, 2026-05-03

## Recommended Tree

```text
WingspanAI/
├── src/wingspan_ai/
│   ├── board_game/       # reusable game interfaces: state, actions, policies, rewards
│   ├── content/          # game content schemas, source audits, loaders, normalization
│   ├── rules/            # legal actions, validation, transitions, scoring, rule modules
│   ├── state/            # full state, player state, observations, belief state
│   ├── agents/           # random, scripted, heuristic, search, Bayesian, learned policies
│   ├── simulation/       # single-game, batch, and tournament runners
│   ├── telemetry/        # event contracts and event emission
│   └── experiments/      # MLflow/evaluation helpers and experiment configuration
├── data/
│   ├── raw/              # unchanged source inputs
│   ├── processed/        # generated normalized artifacts
│   └── reference/        # hand-authored stable lookup tables
├── docs/
│   ├── architecture/
│   ├── rules/
│   ├── events/
│   ├── agents/
│   ├── experiments/
│   └── decisions/
├── notebooks/            # exploratory analysis only
├── analysis/             # reusable Python/R/SQL analysis scripts
├── flows/                # Prefect orchestration
└── tests/                # unit and regression tests
```

## Boundary Decisions

- Keep Wingspan-specific rules under `src/wingspan_ai/rules/` for now, but keep reusable concepts visible in `src/wingspan_ai/board_game/`.
- Keep workbook column parsing out of the schema models. Source-specific quirks belong in `src/wingspan_ai/content/`.
- Keep simulation telemetry independent from analysis notebooks so every run can be replayed and compared.
- Add abstractions only when the second concrete use case appears or when a boundary protects hidden information, rules fidelity, or experiment reproducibility.

## Near-Term Implementation Order

1. Finish content audit and source normalization mappings.
2. Add a base content loader that converts `wingspan-card-list.xlsx` into typed `BirdCard`, `BonusCard`, and `RoundGoal` objects.
3. Add base-game state models under `state/`.
4. Add legal action and transition skeletons under `rules/`.
5. Add random legal agent and single-game runner once legal actions exist.

