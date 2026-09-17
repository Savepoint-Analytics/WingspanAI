"""Lab-bench card synergy: compute what pairs of birds yield together, from the rules.

Layer A of the synergy programme (``docs/agents/synergy_planner_agent.md``).
A combination's mechanical value does not have to be waited for in simulated
games, where a specific pair may never be dealt together: the rules engine
can score it directly. For each habitat, every bird that can live there is
placed alone on a controlled board and the habitat is activated once; then
every ordered pair (left slot, right slot — brown powers resolve right to
left, so order is part of the synergy) is placed and activated once. Yields
are the owner's deltas in food, cards, eggs, tucked cards, cached food and
score.

    power(config) = yield(config) − yield(same-size row of power-less birds)
    synergy(A, B) = power(A, B) − power(A) − power(B)

is the interaction contrast: what the pair's powers produce beyond the sum of
their parts, with the mat's own scaling (a two-bird row lays more eggs than a
one-bird row) removed by the size-matched blank baseline. Each configuration
is measured in several seeded contexts (different feeder rolls and deck
order) and averaged, so predator hunts and feeder
draws are represented at their seeded odds rather than as one lucky roll.

Scope of this first bench: brown (activation) powers, same-habitat pairs,
one activation. Cross-habitat chains, white on-play powers and pink
reactions are the documented next extensions.

    python analysis/card_synergy_bench.py --seeds 1 2 3 --out artifacts/synergy_bench
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from statistics import mean

from wingspan_ai.content.loader import (
    BASE_FOOD_TYPES,
    DEFAULT_WORKBOOK_PATH,
    load_base_game_content_catalog,
)
from wingspan_ai.content.schemas import BirdCard, Habitat, PowerColor
from wingspan_ai.rules.actions import ActionType
from wingspan_ai.rules.base_game import (
    apply_action,
    legal_actions_for_current_player,
    score_player,
    setup_base_game,
)
from wingspan_ai.state.models import BirdSlot, GameState

YIELD_KEYS = ("food", "cards", "eggs", "tucked", "cached", "score")
#: Points-equivalent weights for the composite column. Eggs, tucked cards and
#: cached food are literal end-game points; food and cards are conversion
#: proxies (a bird costs ~2 food and is worth ~4 points plus its engine).
COMPOSITE_WEIGHTS = {"food": 0.6, "cards": 0.5, "eggs": 1.0, "tucked": 1.0, "cached": 1.0}
ROW_ACTION = {
    Habitat.FOREST: ActionType.GAIN_FOOD,
    Habitat.GRASSLAND: ActionType.LAY_EGGS,
    Habitat.WETLAND: ActionType.DRAW_CARDS,
}
BENCH_PLAYER = "player_1"


#: Resource contexts. Many powers only interact under scarcity — a tuck-from-hand
#: bird next to a card-draw bird does nothing while the hand is full — so each
#: configuration is measured rich and scarce and the two are averaged.
CONTEXTS = {
    "rich": {"hand": 3, "food_each": 2},
    "scarce": {"hand": 0, "food_each": 0},
}


def bench_state(catalog, seed: int, context: str = "rich") -> GameState:
    """A mid-game state with an empty board and the context's hand and food."""

    settings = CONTEXTS[context]
    state = setup_base_game(catalog, player_ids=["player_1", "player_2"], random_seed=seed)
    player = state.players[0]
    for habitat in Habitat:
        player.habitats[habitat] = []
    player.hand = list(state.decks.bird_deck[: settings["hand"]])
    del state.decks.bird_deck[: settings["hand"]]
    player.food_tokens = {food: settings["food_each"] for food in BASE_FOOD_TYPES}
    player.action_cubes_available = 6
    state.round_state.round_number = 2
    state.round_state.active_player_index = 0
    return state


def measure(state: GameState, habitat: Habitat) -> dict[str, int] | None:
    """Owner's counter deltas from one activation of the row, or None if illegal."""

    action_type = ROW_ACTION[habitat]
    action = next(
        (a for a in legal_actions_for_current_player(state) if a.action_type == action_type),
        None,
    )
    if action is None:
        return None
    before = snapshot(state)
    after_state = apply_action(state, action)
    after = snapshot(after_state)
    return {key: after[key] - before[key] for key in YIELD_KEYS}


def snapshot(state: GameState) -> dict[str, int]:
    player = state.players[0]
    slots = [slot for habitat in Habitat for slot in player.habitats[habitat]]
    return {
        "food": sum(player.food_tokens.values()),
        "cards": len(player.hand),
        "eggs": sum(slot.eggs for slot in slots),
        "tucked": sum(slot.tucked_cards for slot in slots),
        "cached": sum(slot.cached_food for slot in slots),
        "score": score_player(state, BENCH_PLAYER).total,
    }


def with_row(state: GameState, habitat: Habitat, cards: list[BirdCard]) -> GameState:
    branch = state.model_copy(deep=True)
    branch.players[0].habitats[habitat] = [BirdSlot(card=card) for card in cards]
    return branch


def composite(delta: dict[str, float]) -> float:
    return sum(COMPOSITE_WEIGHTS[key] * delta.get(key, 0.0) for key in COMPOSITE_WEIGHTS)


def average(rows: list[dict[str, int] | None]) -> dict[str, float]:
    kept = [row for row in rows if row is not None]
    if not kept:
        return dict.fromkeys(YIELD_KEYS, 0.0)
    return {key: mean(row[key] for row in kept) for key in YIELD_KEYS}


def blank_bird(catalog, habitat: Habitat) -> BirdCard:
    """A power-less resident of the habitat, used to baseline the row's own yield."""

    candidates = [
        card
        for card in catalog.birds
        if card.power.color == PowerColor.NONE and habitat in card.habitats
    ]
    return max(candidates, key=lambda card: (card.egg_limit, card.common_name))


def run_bench(catalog, seeds: list[int], *, max_birds_per_habitat: int | None = None) -> dict:
    states = [bench_state(catalog, seed, context) for seed in seeds for context in CONTEXTS]
    brown = [card for card in catalog.birds if card.power.color == PowerColor.BROWN]
    results: dict = {
        "seeds": seeds,
        "contexts": list(CONTEXTS),
        "singles": {},
        "pairs": {},
        "row_base": {},
    }
    for habitat in Habitat:
        residents = [card for card in brown if habitat in card.habitats]
        if max_birds_per_habitat is not None:
            residents = residents[:max_birds_per_habitat]
        blank = blank_bird(catalog, habitat)
        row_base = {
            size: average(
                [measure(with_row(state, habitat, [blank] * size), habitat) for state in states]
            )
            for size in (1, 2)
        }
        results["row_base"][habitat.value] = {
            "blank": blank.common_name,
            **{str(size): row_base[size] for size in row_base},
        }
        singles: dict[str, dict[str, float]] = {}
        for card in residents:
            raw = average([measure(with_row(state, habitat, [card]), habitat) for state in states])
            singles[card.common_name] = {k: raw[k] - row_base[1][k] for k in YIELD_KEYS}
        results["singles"][habitat.value] = singles
        pairs: dict[str, dict] = {}
        started = time.time()
        for left in residents:
            for right in residents:
                if left.common_name == right.common_name:
                    continue
                raw = average(
                    [measure(with_row(state, habitat, [left, right]), habitat) for state in states]
                )
                pair = {k: raw[k] - row_base[2][k] for k in YIELD_KEYS}
                synergy = {
                    key: pair[key]
                    - singles[left.common_name][key]
                    - singles[right.common_name][key]
                    for key in YIELD_KEYS
                }
                pairs[f"{left.common_name} | {right.common_name}"] = {
                    "left": left.common_name,
                    "right": right.common_name,
                    "pair_yield": pair,
                    "synergy": synergy,
                    "synergy_points": composite(synergy),
                }
        results["pairs"][habitat.value] = pairs
        print(
            f"{habitat.value}: {len(residents)} brown residents, {len(pairs)} ordered pairs "
            f"in {time.time() - started:.0f}s",
            file=sys.stderr,
            flush=True,
        )
    return results


def report(results: dict, *, top: int) -> str:
    lines = ["# Card synergy bench (brown powers, same habitat, one activation)", ""]
    lines.append(
        f"Seeds: {results['seeds']}; contexts: {results.get('contexts', ['rich'])} (averaged). "
        f"Composite weights: {COMPOSITE_WEIGHTS}."
    )
    for habitat, singles in results["singles"].items():
        blank = results["row_base"][habitat]["blank"]
        lines += [
            "",
            f"## {habitat}: power yield per activation (single bird, beyond a row of `{blank}`)",
            "",
            "| Bird | food | cards | eggs | tucked | cached | points-eq |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        ranked = sorted(singles.items(), key=lambda item: -composite(item[1]))
        for name, d in ranked[:top]:
            lines.append(
                f"| {name} | {d['food']:+.2f} | {d['cards']:+.2f} | {d['eggs']:+.2f} | "
                f"{d['tucked']:+.2f} | {d['cached']:+.2f} | {composite(d):+.2f} |"
            )
    for habitat, pairs in results["pairs"].items():
        lines += [
            "",
            f"## {habitat}: pair synergy (left | right; right resolves first)",
            "",
            "| Pair | synergy food | cards | eggs | tucked | cached | points-eq |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        ranked = sorted(pairs.values(), key=lambda p: -p["synergy_points"])
        shown = [p for p in ranked if abs(p["synergy_points"]) > 1e-9]
        for p in shown[:top]:
            s = p["synergy"]
            lines.append(
                f"| {p['left']} \\| {p['right']} | {s['food']:+.2f} | {s['cards']:+.2f} | "
                f"{s['eggs']:+.2f} | {s['tucked']:+.2f} | {s['cached']:+.2f} | "
                f"{p['synergy_points']:+.2f} |"
            )
        negatives = [p for p in ranked if p["synergy_points"] < -1e-9]
        if negatives:
            lines += ["", f"Anti-synergies ({len(negatives)}), worst {min(top, 8)}:", ""]
            for p in negatives[-min(top, 8) :]:
                lines.append(f"- {p['left']} | {p['right']}: {p['synergy_points']:+.2f}")
        nonzero = sum(1 for p in ranked if abs(p["synergy_points"]) > 1e-9)
        lines.append(f"\n{nonzero} of {len(ranked)} ordered pairs interact at all.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--max-birds-per-habitat", type=int, default=None)
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    parser.add_argument("--out", type=Path, default=None, help="directory for JSON + report")
    args = parser.parse_args(argv)
    catalog = load_base_game_content_catalog(args.workbook)
    results = run_bench(catalog, args.seeds, max_birds_per_habitat=args.max_birds_per_habitat)
    text = report(results, top=args.top)
    print(text)
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "synergy_bench.json").write_text(json.dumps(results, indent=1))
        (args.out / "synergy_bench.md").write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
