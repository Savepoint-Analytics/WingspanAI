"""Event-first analysis helpers for Wingspan notebooks and ad hoc research.

``persistence`` loads telemetry from PostgreSQL, MinIO or local artifacts;
``kpis`` derives the Wingspan round/game KPI taxonomy from it. Both return
plain lists of dictionaries so a notebook can use pandas or the standard
library.
"""

from wingspan_ai.analysis.kpis import (
    SCORE_CATEGORIES,
    TAXONOMY_COVERAGE,
    action_kpis,
    agent_key,
    bird_utilization_kpis,
    bonus_card_kpis,
    comparative_kpis,
    round_goal_kpis,
    scoring_kpis,
    taxonomy_coverage_report,
    tempo_kpis,
)
from wingspan_ai.analysis.persistence import (
    list_persisted_runs,
    load_game_scores,
    load_games,
    load_local_event_records,
    load_minio_event_records,
    load_postgres_event_records,
)

__all__ = [
    "SCORE_CATEGORIES",
    "TAXONOMY_COVERAGE",
    "action_kpis",
    "agent_key",
    "bird_utilization_kpis",
    "bonus_card_kpis",
    "comparative_kpis",
    "list_persisted_runs",
    "load_game_scores",
    "load_games",
    "load_local_event_records",
    "load_minio_event_records",
    "load_postgres_event_records",
    "round_goal_kpis",
    "scoring_kpis",
    "taxonomy_coverage_report",
    "tempo_kpis",
]
