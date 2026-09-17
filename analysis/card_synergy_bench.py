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

Modes (``--mode``):

- ``same_row`` (default): brown pairs in one habitat, one activation.
- ``cross``: A alone in one habitat and B alone in another, both rows
  activated once in each order — the draw-then-tuck and food-then-cache
  chains that cross rows. Baseline: the same two activations with blanks.
- ``onplay``: a white (on-play) bird played into a row with A already there,
  against playing it next to a blank — board-composition effects such as
  "lay an egg on each bird with a cavity nest".
- ``pink``: a pink (reaction) bird on the board while the opponent takes each
  triggering action, alone and next to B in the same row — the
  "lay an egg on a bird with a bowl nest" class needs a partner that has one.

    python analysis/card_synergy_bench.py --seeds 1 2 3 --out artifacts/synergy_bench
    python analysis/card_synergy_bench.py --mode cross --out artifacts/synergy_bench
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
    # Capacity-aware (2026-09-17, after layer C's P3 reversal): every other row
    # holds two egg-full blanks and the placed birds start one egg below their
    # own limit, so an egg-laying synergy is measured where the cap binds.
    "capped": {"hand": 1, "food_each": 1, "capped": True},
}
DEFAULT_CONTEXTS = ("rich", "scarce")


#: Bench states are pydantic models with extra="forbid", so the context flag
#: lives beside them, keyed by identity (the states list keeps them alive).
_CAPPED_STATES: dict[int, bool] = {}


def bench_state(catalog, seed: int, context: str = "rich") -> GameState:
    """A mid-game state with an empty board and the context's hand and food."""

    settings = CONTEXTS[context]
    state = setup_base_game(catalog, player_ids=["player_1", "player_2"], random_seed=seed)
    player = state.players[0]
    for habitat in Habitat:
        player.habitats[habitat] = []
    if settings.get("capped"):
        for habitat in Habitat:
            blank = blank_bird(catalog, habitat)
            player.habitats[habitat] = [
                BirdSlot(card=blank, eggs=blank.egg_limit) for _ in range(2)
            ]
    _CAPPED_STATES[id(state)] = bool(settings.get("capped", False))
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
    """Place ``cards`` in ``habitat`` (after any pre-filled blanks), eggs per context."""

    branch = state.model_copy(deep=True)
    capped = _CAPPED_STATES.get(id(state), False)
    prefilled = [slot for slot in branch.players[0].habitats[habitat] if capped]
    branch.players[0].habitats[habitat] = prefilled + [
        BirdSlot(card=card, eggs=max(card.egg_limit - 1, 0) if capped else 0) for card in cards
    ]
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


def run_bench(
    catalog,
    seeds: list[int],
    *,
    max_birds_per_habitat: int | None = None,
    contexts: tuple[str, ...] = DEFAULT_CONTEXTS,
) -> dict:
    states = [bench_state(catalog, seed, context) for seed in seeds for context in contexts]
    brown = [card for card in catalog.birds if card.power.color == PowerColor.BROWN]
    results: dict = {
        "seeds": seeds,
        "contexts": list(contexts),
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


def _reactivate(state: GameState) -> GameState:
    """Hand the turn back to the bench player after an action advanced it."""

    state.round_state.active_player_index = 0
    state.round_state.game_over = False
    state.players[0].action_cubes_available = max(state.players[0].action_cubes_available, 3)
    return state


def measure_sequence(state: GameState, habitats: list[Habitat]) -> dict[str, int] | None:
    """Owner's deltas from activating the given rows in order."""

    before = snapshot(state)
    current = state
    for habitat in habitats:
        action = next(
            (
                a
                for a in legal_actions_for_current_player(current)
                if a.action_type == ROW_ACTION[habitat]
            ),
            None,
        )
        if action is None:
            return None
        current = _reactivate(apply_action(current, action))
    after = snapshot(current)
    return {key: after[key] - before[key] for key in YIELD_KEYS}


def with_rows(state: GameState, rows: dict[Habitat, list[BirdCard]]) -> GameState:
    branch = state.model_copy(deep=True)
    for habitat, cards in rows.items():
        branch.players[0].habitats[habitat] = [BirdSlot(card=card) for card in cards]
    return branch


def run_cross_bench(catalog, seeds: list[int], *, max_birds: int | None = None) -> dict:
    """A in one row, B in another; both rows activated once, each order."""

    states = [bench_state(catalog, seed, context) for seed in seeds for context in CONTEXTS]
    brown = [card for card in catalog.birds if card.power.color == PowerColor.BROWN]
    blanks = {h: blank_bird(catalog, h) for h in Habitat}
    results: dict = {"seeds": seeds, "contexts": list(CONTEXTS), "mode": "cross", "pairs": {}}
    for h1 in Habitat:
        for h2 in Habitat:
            if h1 == h2:
                continue
            order = [h1, h2]
            residents_1 = [c for c in brown if h1 in c.habitats][:max_birds]
            residents_2 = [c for c in brown if h2 in c.habitats][:max_birds]
            base = average(
                [
                    measure_sequence(with_rows(s, {h1: [blanks[h1]], h2: [blanks[h2]]}), order)
                    for s in states
                ]
            )
            single_1 = {
                a.common_name: average(
                    [
                        measure_sequence(with_rows(s, {h1: [a], h2: [blanks[h2]]}), order)
                        for s in states
                    ]
                )
                for a in residents_1
            }
            single_2 = {
                b.common_name: average(
                    [
                        measure_sequence(with_rows(s, {h1: [blanks[h1]], h2: [b]}), order)
                        for s in states
                    ]
                )
                for b in residents_2
            }
            pairs: dict[str, dict] = {}
            started = time.time()
            for a in residents_1:
                for b in residents_2:
                    if a.common_name == b.common_name:
                        continue
                    both = average(
                        [measure_sequence(with_rows(s, {h1: [a], h2: [b]}), order) for s in states]
                    )
                    synergy = {
                        k: both[k]
                        - single_1[a.common_name][k]
                        - single_2[b.common_name][k]
                        + base[k]
                        for k in YIELD_KEYS
                    }
                    pairs[f"{a.common_name} @{h1.value} | {b.common_name} @{h2.value}"] = {
                        "left": f"{a.common_name} @{h1.value}",
                        "right": f"{b.common_name} @{h2.value}",
                        "pair_yield": both,
                        "synergy": synergy,
                        "synergy_points": composite(synergy),
                    }
            results["pairs"][f"{h1.value} then {h2.value}"] = pairs
            print(
                f"{h1.value} then {h2.value}: {len(pairs)} pairs in {time.time() - started:.0f}s",
                file=sys.stderr,
                flush=True,
            )
    return results


def _play_state(catalog, seed: int, context: str) -> GameState:
    state = bench_state(catalog, seed, context)
    state.players[0].food_tokens = {food: 3 for food in BASE_FOOD_TYPES}
    return state


def measure_play(state: GameState, card: BirdCard, habitat: Habitat) -> dict[str, int] | None:
    """Owner's deltas from playing ``card`` into ``habitat`` (cost and points included)."""

    branch = state.model_copy(deep=True)
    branch.players[0].hand.append(card)
    action = next(
        (
            a
            for a in legal_actions_for_current_player(branch)
            if a.action_type == ActionType.PLAY_BIRD
            and a.bird_common_name == card.common_name
            and a.habitat == habitat
        ),
        None,
    )
    if action is None:
        return None
    before = snapshot(branch)
    after = snapshot(apply_action(branch, action))
    return {key: after[key] - before[key] for key in YIELD_KEYS}


def run_onplay_bench(catalog, seeds: list[int], *, max_birds: int | None = None) -> dict:
    """White on-play birds played next to A, against next to a blank."""

    states = [_play_state(catalog, seed, context) for seed in seeds for context in CONTEXTS]
    whites = [card for card in catalog.birds if card.power.color == PowerColor.WHITE]
    results: dict = {"seeds": seeds, "contexts": list(CONTEXTS), "mode": "onplay", "pairs": {}}
    for habitat in Habitat:
        blank = blank_bird(catalog, habitat)
        residents = [
            c for c in catalog.birds if habitat in c.habitats and c.power.color != PowerColor.NONE
        ][:max_birds]
        played = [c for c in whites if habitat in c.habitats][:max_birds]
        pairs: dict[str, dict] = {}
        started = time.time()
        for b in played:
            base = average(
                [measure_play(with_row(s, habitat, [blank]), b, habitat) for s in states]
            )
            for a in residents:
                if a.common_name == b.common_name:
                    continue
                with_a = average(
                    [measure_play(with_row(s, habitat, [a]), b, habitat) for s in states]
                )
                synergy = {k: with_a[k] - base[k] for k in YIELD_KEYS}
                pairs[f"{a.common_name} | play {b.common_name}"] = {
                    "left": a.common_name,
                    "right": f"play {b.common_name}",
                    "pair_yield": with_a,
                    "synergy": synergy,
                    "synergy_points": composite(synergy),
                }
        results["pairs"][habitat.value] = pairs
        print(
            f"{habitat.value}: {len(played)} whites x {len(residents)} residents in "
            f"{time.time() - started:.0f}s",
            file=sys.stderr,
            flush=True,
        )
    return results


PINK_TRIGGERS = {
    "opponent lays eggs": ActionType.LAY_EGGS,
    "opponent gains food": ActionType.GAIN_FOOD,
    "opponent plays a bird": ActionType.PLAY_BIRD,
}


def measure_reaction(state: GameState, trigger: ActionType) -> dict[str, int] | None:
    """Owner's (player 1) deltas when the opponent takes one action of ``trigger``."""

    branch = state.model_copy(deep=True)
    branch.round_state.active_player_index = 1
    opponent = branch.players[1]
    opponent.action_cubes_available = max(opponent.action_cubes_available, 3)
    if trigger == ActionType.LAY_EGGS and not opponent.played_birds:
        return None
    if trigger == ActionType.PLAY_BIRD and not opponent.hand:
        return None
    action = next(
        (a for a in legal_actions_for_current_player(branch) if a.action_type == trigger),
        None,
    )
    if action is None:
        return None
    before = snapshot(branch)
    after = snapshot(apply_action(branch, action))
    return {key: after[key] - before[key] for key in YIELD_KEYS}


def _pink_state(catalog, seed: int, context: str) -> GameState:
    """Bench state whose opponent can lay eggs, gain food and play a bird."""

    state = bench_state(catalog, seed, context)
    opponent = state.players[1]
    opponent.food_tokens = {food: 3 for food in BASE_FOOD_TYPES}
    for habitat in Habitat:
        opponent.habitats[habitat] = [BirdSlot(card=blank_bird(catalog, habitat))]
    return state


def run_pink_bench(catalog, seeds: list[int], *, max_birds: int | None = None) -> dict:
    """Pink reactions per trigger, alone and next to a same-row partner."""

    states = [_pink_state(catalog, seed, context) for seed in seeds for context in CONTEXTS]
    pinks = [card for card in catalog.birds if card.power.color == PowerColor.PINK]
    results: dict = {
        "seeds": seeds,
        "contexts": list(CONTEXTS),
        "mode": "pink",
        "singles": {},
        "pairs": {},
    }
    for habitat in Habitat:
        blank = blank_bird(catalog, habitat)
        residents = [c for c in catalog.birds if habitat in c.habitats][:max_birds]
        singles: dict[str, dict] = {}
        pairs: dict[str, dict] = {}
        started = time.time()
        for pink in [c for c in pinks if habitat in c.habitats]:
            for trigger_name, trigger in PINK_TRIGGERS.items():
                base = average(
                    [measure_reaction(with_row(s, habitat, [blank]), trigger) for s in states]
                )
                alone = average(
                    [measure_reaction(with_row(s, habitat, [pink]), trigger) for s in states]
                )
                single = {k: alone[k] - base[k] for k in YIELD_KEYS}
                singles[f"{pink.common_name} | {trigger_name}"] = single
                if composite(single) == 0.0 and all(v == 0 for v in single.values()):
                    continue
                for partner in residents:
                    if partner.common_name == pink.common_name:
                        continue
                    partner_alone = average(
                        [measure_reaction(with_row(s, habitat, [partner]), trigger) for s in states]
                    )
                    together = average(
                        [
                            measure_reaction(with_row(s, habitat, [pink, partner]), trigger)
                            for s in states
                        ]
                    )
                    synergy = {
                        k: together[k] - alone[k] - partner_alone[k] + base[k] for k in YIELD_KEYS
                    }
                    if all(abs(v) < 1e-9 for v in synergy.values()):
                        continue
                    pairs[f"{pink.common_name} | {partner.common_name} | {trigger_name}"] = {
                        "left": pink.common_name,
                        "right": f"{partner.common_name} ({trigger_name})",
                        "pair_yield": together,
                        "synergy": synergy,
                        "synergy_points": composite(synergy),
                    }
        results["singles"][habitat.value] = singles
        results["pairs"][habitat.value] = pairs
        print(
            f"{habitat.value}: pink singles {len(singles)}, interacting pairs {len(pairs)} in "
            f"{time.time() - started:.0f}s",
            file=sys.stderr,
            flush=True,
        )
    return results


def report(results: dict, *, top: int) -> str:
    mode = results.get("mode", "same_row")
    lines = [f"# Card synergy bench — mode `{mode}`", ""]
    lines.append(
        f"Seeds: {results['seeds']}; contexts: {results.get('contexts', ['rich'])} (averaged). "
        f"Composite weights: {COMPOSITE_WEIGHTS}."
    )
    for habitat, singles in results.get("singles", {}).items():
        blank = results.get("row_base", {}).get(habitat, {}).get("blank", "blank")
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
    parser.add_argument(
        "--mode", choices=("same_row", "cross", "onplay", "pink"), default="same_row"
    )
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--max-birds-per-habitat", type=int, default=None)
    parser.add_argument(
        "--contexts",
        nargs="+",
        choices=tuple(CONTEXTS),
        default=list(DEFAULT_CONTEXTS),
        help="resource contexts to average over (same_row mode)",
    )
    parser.add_argument("--tag", default="", help="suffix for the output files")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK_PATH)
    parser.add_argument("--out", type=Path, default=None, help="directory for JSON + report")
    args = parser.parse_args(argv)
    catalog = load_base_game_content_catalog(args.workbook)
    runner = {
        "same_row": lambda: run_bench(
            catalog,
            args.seeds,
            max_birds_per_habitat=args.max_birds_per_habitat,
            contexts=tuple(args.contexts),
        ),
        "cross": lambda: run_cross_bench(catalog, args.seeds, max_birds=args.max_birds_per_habitat),
        "onplay": lambda: run_onplay_bench(
            catalog, args.seeds, max_birds=args.max_birds_per_habitat
        ),
        "pink": lambda: run_pink_bench(catalog, args.seeds, max_birds=args.max_birds_per_habitat),
    }[args.mode]
    results = runner()
    text = report(results, top=args.top)
    print(text)
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        suffix = ("" if args.mode == "same_row" else f"_{args.mode}") + (
            f"_{args.tag}" if args.tag else ""
        )
        (args.out / f"synergy_bench{suffix}.json").write_text(json.dumps(results, indent=1))
        (args.out / f"synergy_bench{suffix}.md").write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
