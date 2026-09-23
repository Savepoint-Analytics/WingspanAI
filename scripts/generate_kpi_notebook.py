"""Generate the Wingspan KPI walkthrough notebook (mirrors the GoT project's pattern)."""

import json
from pathlib import Path

NB = Path("notebooks")


def _lines(text):
    return [f"{line}\n" for line in text.strip("\n").splitlines()]


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": _lines(text)}


def code(text):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": _lines(text),
    }


cells = [
    md("""# Wingspan KPI walkthrough

One section per section of the Wingspan round/game KPI taxonomy, against
persisted telemetry. Every cell calls a function from `wingspan_ai.analysis`,
so a number here is reproducible outside the notebook.

**Read the coverage table first.** A `partial` or `missing` family is a
telemetry gap, not a zero, and the note names the field that would close it.
A column ending in `_proxy` stands in for something the simulator does not
record — do not report it as the thing itself.

Sources: PostgreSQL (`public.*` in the Savepoint Lab database — Wingspan
writes unqualified tables there rather than its own schema), MinIO
(`savepoint-ai/board-games/wingspan/...`), or local `artifacts/`."""),
    code("""from wingspan_ai.analysis import (
    SCORE_CATEGORIES,
    action_kpis,
    bird_utilization_kpis,
    bonus_card_kpis,
    comparative_kpis,
    list_persisted_runs,
    load_game_scores,
    load_local_event_records,
    load_minio_event_records,
    load_postgres_event_records,
    round_goal_kpis,
    scoring_kpis,
    taxonomy_coverage_report,
    tempo_kpis,
)

def show(rows, limit=25):
    rows = list(rows)
    try:
        import pandas as pd
        return pd.DataFrame(rows).head(limit)
    except ImportError:
        return rows[:limit]"""),
    md("""## 0. Choose the data

Scores are cheap and cover the whole archive; events are per run label.
Keep `event_names` tight — 94% of the event log is the four per-turn
decision events, and no KPI below needs all of them."""),
    code("""show(list_persisted_runs(limit=25))"""),
    code("""# Whole-archive score rows for the outcome, composition and comparative families.
scores = load_game_scores()

# Events for the families that need them. Pick a run label from the table above.
RUN_LABEL = "experiment:fp_v2_P3_AcBc"
KPI_EVENTS = ["bird_scorecard", "setup_selection_applied", "action_resolved", "round_goal_scored"]
events = load_postgres_event_records(run_label=RUN_LABEL, event_names=KPI_EVENTS)

# MinIO alternative (immutable per-game artifacts):
# events = load_minio_event_records("experiment/rr_belief_opp", event_names=KPI_EVENTS)
# Local artifacts:
# events = load_local_event_records("artifacts/rr_belief_opp", event_names=KPI_EVENTS)

len(scores), len(events)"""),
    md("## 1. Coverage: what this data can answer"),
    code("show(taxonomy_coverage_report(events), limit=20)"),
    md("## Core scoring — final score and its six categories"),
    code("""core = scoring_kpis(scores)
show(core["by_agent"])
show(core["composition"])"""),
    md("""## End-of-round goals

Totals come from the score table. Per-round placement needs
`round_goal_scored`, emitted from 2026-09-22 — earlier runs return an empty
`by_round`. Goal fit, rank volatility and points-left-on-the-table need a
counterfactual placement that is never recorded."""),
    code("""goals = round_goal_kpis(scores, events)
show(goals["by_agent"])
show(goals["by_round"], limit=30)"""),
    md("## Bonus cards — selection, and fulfilment against the birds played"),
    code("""bonus = bonus_card_kpis(events)
show(bonus["selection"], limit=20)
show(bonus["fulfilment"])
show(bonus["by_card"], limit=30)"""),
    md("## Card / bird utilization — draw efficiency, habitats, power mix"),
    code("""birds = bird_utilization_kpis(events)
show(birds["draw_efficiency"])
show(birds["by_agent"])
show(birds["by_power_color"])
show(birds["top_birds"], limit=25)"""),
    md("""## Food economy

**Not available.** No event carries a player's food tokens, so unspent food,
waste rate, excess by type and engine overshoot cannot be computed at all. A
per-turn food snapshot would close every KPI in this section at once."""),
    md("## Turn / action level — action mix and points per action"),
    code("""actions = action_kpis(events, scores)
show(actions["by_agent"])
show(actions["by_round"], limit=30)
show(actions["action_efficiency"])"""),
    md("## Tempo and strategic archetype"),
    code("""tempo = tempo_kpis(events)
show(tempo["first_habitat_round"])
show(tempo["birds_by_round"], limit=30)
# Specialization index (HHI over habitats) is in bird_utilization_kpis:
show(birds["by_agent"], limit=10)"""),
    md("## Comparative / positional"),
    code("""comparative = comparative_kpis(scores)
show(comparative["margins"])
show(comparative["head_to_head"], limit=30)"""),
    md("""## Reading the results

1. **Coverage bounds the claim.** Check section 1 before quoting any number
   from a `partial` family.
2. **Agents are not comparable across run labels.** The persisted archive is
   dominated by one study; use `run_label` to slice, or pair by seed with
   `analysis/arm_contrast.py` for a real contrast.
3. **A proxy is not a measurement.** `activation_rate_proxy` is activations
   per bird, not activations against the maximum available."""),
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
NB.mkdir(exist_ok=True)
(NB / "wingspan_kpi_walkthrough.ipynb").write_text(json.dumps(nb, indent=2) + "\n")
print("wrote notebooks/wingspan_kpi_walkthrough.ipynb")
