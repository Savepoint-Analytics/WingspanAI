# Docs

Project documentation beyond the root context files.

- `architecture/`: package structure, simulator design, and reusable board-game AI interfaces.
- `rules/`: encoded rule assumptions, expansion scope, data/rule encoding recommendations, and fidelity notes.
- `events/`: simulation telemetry contracts.
- `agents/`: baseline strategy definitions and model cards.
- `experiments/`: experiment plans and results.
- `decisions/`: ADR-style decisions.

Key rules docs:

- `architecture/simulator_architecture.md`: base simulator and rules-engine design.
- `events/simulation_event_taxonomy.md`: current simulation telemetry envelope and emitted event names.
- `events/postgresql_event_table_design.md`: draft event-log database tables and indexes.
- `rules/game_content_schema.md`: current content schema and enum design.
- `rules/wingspan_card_list_audit.md`: source workbook audit and normalization needs.
- `rules/data_and_rule_encoding_recommendations.md`: recommendations for power fidelity, handler mapping, expansion representation, and rule traceability.
