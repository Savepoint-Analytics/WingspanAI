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
- `agents/baseline_agents.md`: random, greedy, archetype, and Monte Carlo baseline definitions.
- `agents/bayesian_belief_model_plan.md`: first Bayesian belief model plan.
- `agents/net_value_opponent_response_agent.md`: score-margin, blocking, and next-opponent-response agent template.
- `events/simulation_event_taxonomy.md`: current simulation telemetry envelope and emitted event names.
- `events/postgresql_event_table_design.md`: draft event-log database tables and indexes.
- `experiments/case_study_outline.md`: public case-study narrative outline.
- `experiments/lookahead_compute_profile.md`: `apply_action` deep-copy profile and budgeted lookahead-agent probes.
- `experiments/potential_points_matrix10_smoke.md`: 10-seed baseline matrix findings, decision timing, and current interpretation caveats.
- `rules/game_content_schema.md`: current content schema and enum design.
- `rules/power_handler_registry.md`: registry metadata approach for bird power handlers.
- `rules/scoring_handler_audit.md`: current scoring coverage audit utility and remaining validation work.
- `rules/wingspan_card_list_audit.md`: source workbook audit and normalization needs.
- `rules/data_and_rule_encoding_recommendations.md`: recommendations for power fidelity, handler mapping, expansion representation, and rule traceability.
