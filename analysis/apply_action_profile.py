"""Profile base action-transition costs for lookahead-heavy agents."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from statistics import mean
from time import perf_counter
from typing import Any

from wingspan_ai.content.loader import DEFAULT_WORKBOOK_PATH, load_base_game_content_catalog
from wingspan_ai.content.sample_catalog import make_sample_catalog
from wingspan_ai.content.schemas import ContentCatalog
from wingspan_ai.rules.actions import render_action
from wingspan_ai.rules.base_game import (
    apply_action,
    apply_action_in_place,
    legal_actions_for_current_player,
    setup_base_game,
)


def profile_apply_action_cost(
    catalog: ContentCatalog,
    *,
    random_seed: int = 1,
    iterations: int = 25,
) -> dict[str, Any]:
    """Return timing estimates for legal action generation, deep copy, and transition."""

    if iterations < 1:
        raise ValueError("iterations must be at least 1")

    state = setup_base_game(catalog, player_ids=["player_1", "player_2"], random_seed=random_seed)
    legal_actions = legal_actions_for_current_player(state)
    if not legal_actions:
        raise ValueError("profile state produced no legal actions")
    action = legal_actions[0]

    legal_action_ms = _time_average_ms(lambda: legal_actions_for_current_player(state), iterations)
    deep_copy_ms = _time_average_ms(lambda: state.model_copy(deep=True), iterations)
    apply_action_ms = _time_average_ms(lambda: apply_action(state, action), iterations)
    branch_copy_in_place_ms = _time_average_ms(
        lambda: apply_action_in_place(state.model_copy(deep=True), action),
        iterations,
    )
    branch_state = apply_action(state, action)
    branch_actions = legal_actions_for_current_player(branch_state)
    branch_action = branch_actions[0] if branch_actions else None
    isolated_in_place_ms = (
        _time_average_ms_over_items(
            [branch_state.model_copy(deep=True) for _index in range(iterations)],
            lambda isolated_state: apply_action_in_place(isolated_state, branch_action),
        )
        if branch_action is not None
        else 0.0
    )
    transition_without_copy_ms = max(apply_action_ms - deep_copy_ms, 0.0)
    copy_share = min(deep_copy_ms / apply_action_ms, 1.0) if apply_action_ms else 0.0

    return {
        "random_seed": random_seed,
        "iterations": iterations,
        "legal_action_count": len(legal_actions),
        "profiled_action": action.model_dump(mode="json"),
        "profiled_action_label": render_action(action),
        "legal_actions_avg_ms": legal_action_ms,
        "deep_copy_avg_ms": deep_copy_ms,
        "apply_action_avg_ms": apply_action_ms,
        "branch_copy_in_place_avg_ms": branch_copy_in_place_ms,
        "isolated_in_place_transition_avg_ms": isolated_in_place_ms,
        "estimated_transition_without_copy_ms": transition_without_copy_ms,
        "deep_copy_share_of_apply_action": copy_share,
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    """Render a compact Markdown profile report."""

    return "\n".join(
        [
            "# Apply Action Profile",
            "",
            f"- Seed: `{profile['random_seed']}`",
            f"- Iterations: `{profile['iterations']}`",
            f"- Legal actions: `{profile['legal_action_count']}`",
            f"- Profiled action: `{profile['profiled_action_label']}`",
            "",
            "| Segment | Avg ms |",
            "|---|---:|",
            f"| Legal action generation | {profile['legal_actions_avg_ms']:.3f} |",
            f"| `GameState.model_copy(deep=True)` | {profile['deep_copy_avg_ms']:.3f} |",
            f"| Full `apply_action` | {profile['apply_action_avg_ms']:.3f} |",
            f"| Branch copy + `apply_action_in_place` | "
            f"{profile['branch_copy_in_place_avg_ms']:.3f} |",
            f"| Isolated in-place transition | "
            f"{profile['isolated_in_place_transition_avg_ms']:.3f} |",
            "| Estimated transition after copy | "
            f"{profile['estimated_transition_without_copy_ms']:.3f} |",
            "",
            f"Deep copy share of `apply_action`: {profile['deep_copy_share_of_apply_action']:.1%}",
            "",
        ]
    )


def load_profile_catalog(
    workbook_path: str | Path | None = DEFAULT_WORKBOOK_PATH,
) -> ContentCatalog:
    """Load the workbook catalog if present, otherwise use the sample catalog."""

    if workbook_path is None:
        return make_sample_catalog()
    resolved_path = Path(workbook_path)
    if resolved_path.exists():
        return load_base_game_content_catalog(resolved_path)
    return make_sample_catalog()


def _time_average_ms(callback: Callable[[], object], iterations: int) -> float:
    timings = []
    for _index in range(iterations):
        started_at = perf_counter()
        callback()
        timings.append((perf_counter() - started_at) * 1000)
    return mean(timings)


def _time_average_ms_over_items(
    items: list[Any],
    callback: Callable[[Any], object],
) -> float:
    timings = []
    for item in items:
        started_at = perf_counter()
        callback(item)
        timings.append((perf_counter() - started_at) * 1000)
    return mean(timings)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook-path", default=str(DEFAULT_WORKBOOK_PATH))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    profile = profile_apply_action_cost(
        load_profile_catalog(args.workbook_path),
        random_seed=args.seed,
        iterations=args.iterations,
    )
    if args.json:
        print(json.dumps(profile, indent=2, sort_keys=True))
    else:
        print(render_profile_markdown(profile), end="")


if __name__ == "__main__":
    main()
