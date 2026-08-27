# Guardrail Policies

Status: initial YAML-configured policy guardrails, 2026-08-26

Guardrail policies sit above legal-action generation. The rules engine still produces the full set
of legal `LegalAction` objects. Guardrails only narrow or rescore that legal set before an agent
chooses, so they cannot make an illegal move legal.

The initial implementation lives in `src/wingspan_ai/agents/guardrails.py`. A sample config lives at
`configs/guardrails/base_heuristic.yaml`.

## YAML Shape

```yaml
schema_version: wingspan.guardrails.v1
name: base_heuristic_guardrails
fail_open_when_all_excluded: true
use_score_modifiers_for_pruning: true
rules:
  - id: prefer_food_for_visible_hand_deficits
    when:
      hand_has_playable_bird_missing_food: true
    action:
      type: gain_food
    guardrail:
      boost_if_food_matches_hand_deficit: 10
      penalize_if_food_unneeded: 5
      reason: Food choices should support visible birds in hand.
```

Supported effects are:

- `exclude`: removes matching actions unless every action would be removed and fail-open is enabled.
- `penalize`: lowers a matching action's guardrail score.
- `boost`: raises a matching action's guardrail score.
- `boost_if_food_matches_hand_deficit`: boosts gain-food actions that select food needed by birds in hand.
- `penalize_if_food_unneeded`: penalizes gain-food actions that select food not currently needed by birds in hand.

With `use_score_modifiers_for_pruning: true`, the wrapper keeps the allowed actions with the best
guardrail modifier and lets the wrapped agent choose within that smaller set. This makes guardrails
act as strong, explainable strategic constraints while preserving the wrapped agent's local policy.

## Telemetry

`GuardrailedAgent.summarize_decision` emits:

- original legal action count
- guardrail allowed/excluded/candidate counts
- fail-open status
- per-rule hit counts
- selected action's guardrail modifier
- selected action's matched rules and reasons
- wrapped agent decision summary over the narrowed candidate set

## Usage

```python
from wingspan_ai.agents import GreedyBaselineAgent, GuardrailedAgent, load_guardrail_config

config = load_guardrail_config("configs/guardrails/base_heuristic.yaml")
agent = GuardrailedAgent(GreedyBaselineAgent(agent_id="greedy"), config)
```

Use hard exclusions sparingly. Most Wingspan choices that look bad in the short term can still be
correct in a specific engine or scoring context, so penalties and boosts should be preferred until
batch evidence shows an action pattern is dominated.
