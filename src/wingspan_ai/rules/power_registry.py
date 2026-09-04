"""Registry metadata for bird power handlers."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from wingspan_ai.content.schemas import ContentCatalog, PowerColor, PowerImplementationStatus

DRAW_CARDS_PATTERN = re.compile(r"draw (\d+) \[card\]")
GAIN_FOOD_PATTERN = re.compile(r"gain (\d+) \[(seed|invertebrate|fish|fruit|rodent|wild)\]")

IMPLEMENTED_POWER_STATUSES = frozenset(
    {
        PowerImplementationStatus.READY,
        PowerImplementationStatus.NO_OP_FOR_V1,
        PowerImplementationStatus.EXPECTED_VALUE_APPROXIMATION,
        PowerImplementationStatus.HEURISTIC_RESOLUTION,
    }
)


class PowerHandlerMetadata(BaseModel):
    """Traceable status for one executable or planned power handler."""

    model_config = ConfigDict(extra="forbid")

    handler_key: str
    implementation_status: PowerImplementationStatus
    source_reference: str
    rulebook: str | None = None
    rulebook_page: int | None = None
    source_section: str | None = None
    module_path: str | None = None
    test_reference: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class PowerAuditResult:
    """Coverage summary for bird power handler classification and implementation."""

    total_birds: int
    powered_card_count: int
    no_power_count: int
    classified_power_count: int
    implemented_power_count: int
    unclassified_power_count: int
    unsupported_power_count: int
    handler_counts: dict[str, int]
    status_counts: dict[str, int]
    unsupported_power_cards: list[dict[str, str | int | None]]
    handler_source_references: dict[str, dict[str, str | int | None]]

    @property
    def handler_coverage(self) -> float:
        if not self.powered_card_count:
            return 1.0
        return self.classified_power_count / self.powered_card_count

    @property
    def implementation_coverage(self) -> float:
        if not self.powered_card_count:
            return 1.0
        return self.implemented_power_count / self.powered_card_count


POWER_HANDLER_REGISTRY: dict[str, PowerHandlerMetadata] = {
    "no_power": PowerHandlerMetadata(
        handler_key="no_power",
        implementation_status=PowerImplementationStatus.NO_OP_FOR_V1,
        source_reference="Core rulebook: birds without powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird cards without power text",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Cards with no power require no transition-time handler.",
    ),
    "gain_food_from_birdfeeder": PowerHandlerMetadata(
        handler_key="gain_food_from_birdfeeder",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: brown powers and forest activation",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=7,
        source_section="Activate forest habitat / brown powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="High-priority base economy handler for common gain-food powers.",
    ),
    "draw_card": PowerHandlerMetadata(
        handler_key="draw_card",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: brown powers and wetland activation",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=9,
        source_section="Activate wetland habitat / brown powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="High-priority card-flow handler for early engine experiments.",
    ),
    "lay_egg": PowerHandlerMetadata(
        handler_key="lay_egg",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: white, brown, and pink egg powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that lay eggs",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Covers simple lay-one-egg templates with deterministic target selection.",
    ),
    "tuck_card": PowerHandlerMetadata(
        handler_key="tuck_card",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: brown tuck powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that tuck cards",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Covers simple tuck-one-card templates and tuck-then-draw variants.",
    ),
    "cache_food": PowerHandlerMetadata(
        handler_key="cache_food",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: cache food powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that cache food",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Covers simple cache-one-food templates.",
    ),
    "pink_reaction": PowerHandlerMetadata(
        handler_key="pink_reaction",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: pink opponent-turn powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Pink powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="First deterministic hooks for lay-egg, food-gain, cache, and tuck reactions.",
    ),
    "predator_hunt": PowerHandlerMetadata(
        handler_key="predator_hunt",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: predator roll powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Predator powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Deterministic heuristic hunt resolution using seeded dice outside birdfeeder.",
    ),
    "discard_egg_gain_wild_food": PowerHandlerMetadata(
        handler_key="discard_egg_gain_wild_food",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: discard egg to gain wild food powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers with costs",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Spends one egg from another bird when available, then gains needed food.",
    ),
    "discard_to_tuck": PowerHandlerMetadata(
        handler_key="discard_to_tuck",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: discard food to tuck card powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers with costs",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Spends required food when available and tucks from deck behind the bird.",
    ),
    "gain_food_from_supply": PowerHandlerMetadata(
        handler_key="gain_food_from_supply",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: gain fixed food from supply powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that gain food",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Adds fixed food directly to the active player's supply.",
    ),
    "all_players_gain_food": PowerHandlerMetadata(
        handler_key="all_players_gain_food",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: all players gain food powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers affecting all players",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Deterministically assumes all eligible players accept beneficial food.",
    ),
    "all_players_lay_eggs": PowerHandlerMetadata(
        handler_key="all_players_lay_eggs",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: all players lay eggs powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers affecting all players",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Deterministically assumes all eligible players accept beneficial eggs.",
    ),
    "deck_search_tuck_by_wingspan": PowerHandlerMetadata(
        handler_key="deck_search_tuck_by_wingspan",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: predator/deck-search tuck powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that reveal or tuck deck cards",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes=(
            "Draws/reveals the top deck card and tucks it if it satisfies "
            "the wingspan threshold."
        ),
    ),
    "discard_egg_draw_cards": PowerHandlerMetadata(
        handler_key="discard_egg_draw_cards",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: discard egg to draw cards powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers with costs",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Spends one egg from the player's board when available, then draws the "
            "stated number of cards from the deck. The optional cost is always taken "
            "when an egg exists, which slightly overvalues cards relative to eggs."
        ),
    ),
    "draw_cards_then_discard": PowerHandlerMetadata(
        handler_key="draw_cards_then_discard",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: draw-then-discard brown powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=9,
        source_section="Activate wetland habitat / brown powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Draws the stated number of cards, then immediately discards the "
            "lowest-value card. The real power defers the discard to end of turn, so "
            "this simplification removes one turn of optionality."
        ),
    ),
    "move_bird_habitat": PowerHandlerMetadata(
        handler_key="move_bird_habitat",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: birds that move between habitats",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that move birds",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Moves the bird only when it is rightmost in its habitat and another "
            "habitat has an open slot. Target habitat is chosen as the habitat with "
            "the fewest played birds, which favours widening engines over deepening."
        ),
    ),
    "repeat_brown_power": PowerHandlerMetadata(
        handler_key="repeat_brown_power",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: powers that repeat another brown power",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that repeat other powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Repeats the nearest other brown power in the same habitat, scanning in "
            "activation order. Repeat powers cannot target other repeat powers, which "
            "bounds recursion but forbids a legal chain."
        ),
    ),
    "trade_food_with_supply": PowerHandlerMetadata(
        handler_key="trade_food_with_supply",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: trade food with the supply",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that trade food",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Spends the most abundant surplus food to gain the food type most needed "
            "by the current hand. Skipped when the needed type is already the most "
            "abundant type."
        ),
    ),
    "draw_bonus_cards_keep_one": PowerHandlerMetadata(
        handler_key="draw_bonus_cards_keep_one",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: draw bonus cards and keep one",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that draw bonus cards",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Draws the stated number of bonus cards and keeps the one scoring highest "
            "against the current board, discarding the rest. Greedy on current board "
            "state rather than projected end-game board."
        ),
    ),
    "draw_cards_player_select": PowerHandlerMetadata(
        handler_key="draw_cards_player_select",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: draw cards for all players to select",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers affecting all players",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Draws player_count + 1 cards, gives the acting player the two "
            "highest-value cards and deals the remainder to opponents in turn order. "
            "Opponent selection is not modelled as a choice."
        ),
    ),
    "draw_tray_cards": PowerHandlerMetadata(
        handler_key="draw_tray_cards",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: draw the face-up bird tray",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that take tray cards",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes="Takes every face-up tray card into hand, then refills the tray from the deck.",
    ),
    "all_players_draw_cards": PowerHandlerMetadata(
        handler_key="all_players_draw_cards",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: all players draw cards powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers affecting all players",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Every player draws the stated number of cards from the deck. Previously "
            "misclassified as a self-only draw, which hid the cost of handing cards "
            "to opponents."
        ),
    ),
    "each_player_gains_birdfeeder_food": PowerHandlerMetadata(
        handler_key="each_player_gains_birdfeeder_food",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: each player gains birdfeeder food",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers affecting all players",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Every player takes one preferred die from the birdfeeder, acting player "
            "first. The 'starting with the player of your choice' ordering choice is "
            "not modelled."
        ),
    ),
    "fewest_birds_draw_cards": PowerHandlerMetadata(
        handler_key="fewest_birds_draw_cards",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: fewest-birds-in-habitat powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers with player comparisons",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Only players tied for the fewest birds in the named habitat draw. "
            "Previously misclassified as an unconditional self-draw."
        ),
    ),
    "fewest_birds_gain_food": PowerHandlerMetadata(
        handler_key="fewest_birds_gain_food",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: fewest-birds-in-habitat powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers with player comparisons",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Only players tied for the fewest birds in the named habitat take a "
            "birdfeeder die. Previously misclassified as an unconditional self-gain."
        ),
    ),
    "play_additional_bird": PowerHandlerMetadata(
        handler_key="play_additional_bird",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: play an additional bird powers",
        rulebook="rulebook_pdfs/WS_Core_Rulebook.pdf",
        rulebook_page=10,
        source_section="Bird powers that play additional birds",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_power_handlers.py",
        notes=(
            "Plays the affordable hand bird with the highest victory points into the "
            "named habitat, paying full food and egg costs. Chained white powers are "
            "resolved up to a bounded recursion depth."
        ),
    ),
}

MAX_CHAINED_POWER_DEPTH = 3


def audit_power_coverage(catalog: ContentCatalog) -> PowerAuditResult:
    """Audit handler-key and implementation coverage for loaded bird powers."""

    handler_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    unsupported_power_cards: list[dict[str, str | int | None]] = []
    powered_card_count = 0
    no_power_count = 0
    classified_power_count = 0
    implemented_power_count = 0

    for bird in catalog.birds:
        handler_key = bird.power.handler_key or classify_power_handler_key(
            bird.power.text,
            bird.power.color,
        )
        metadata = POWER_HANDLER_REGISTRY.get(handler_key or "")
        has_power = bird.power.color != PowerColor.NONE and bool(bird.power.text)
        if has_power:
            powered_card_count += 1
        else:
            no_power_count += 1

        counted_handler_key = handler_key or "unclassified"
        handler_counts[counted_handler_key] += 1
        status = (
            metadata.implementation_status
            if metadata is not None
            else bird.power.implementation_status
        )
        status_counts[status.value] += 1

        if not has_power:
            continue
        if metadata is not None:
            classified_power_count += 1
        if metadata is not None and metadata.implementation_status in IMPLEMENTED_POWER_STATUSES:
            implemented_power_count += 1
            continue

        unsupported_power_cards.append(
            {
                "common_name": bird.common_name,
                "power_color": bird.power.color.value,
                "handler_key": handler_key,
                "implementation_status": status.value,
                "source_row": bird.source_row,
            }
        )

    handler_source_references = {
        key: {
            "implementation_status": metadata.implementation_status.value,
            "rulebook": metadata.rulebook,
            "page": metadata.rulebook_page,
            "section": metadata.source_section,
            "module_path": metadata.module_path,
            "test_reference": metadata.test_reference,
        }
        for key, metadata in sorted(POWER_HANDLER_REGISTRY.items())
    }

    return PowerAuditResult(
        total_birds=len(catalog.birds),
        powered_card_count=powered_card_count,
        no_power_count=no_power_count,
        classified_power_count=classified_power_count,
        implemented_power_count=implemented_power_count,
        unclassified_power_count=powered_card_count - classified_power_count,
        unsupported_power_count=len(unsupported_power_cards),
        handler_counts=dict(sorted(handler_counts.items())),
        status_counts=dict(sorted(status_counts.items())),
        unsupported_power_cards=sorted(
            unsupported_power_cards,
            key=lambda card: (str(card["common_name"]), str(card["handler_key"])),
        ),
        handler_source_references=handler_source_references,
    )


def classify_power_handler_key(power_text: str | None, power_color: PowerColor) -> str | None:
    """Map common source power text to a stable handler key."""

    if power_color == PowerColor.NONE or not power_text:
        return "no_power"

    lowered = power_text.lower()
    if power_color == PowerColor.PINK:
        return "pink_reaction"

    # Structural powers are matched before the generic food/card templates because
    # their text also contains draw/gain phrasing.
    if "play an additional bird" in lowered:
        return "play_additional_bird"
    if "bonus card" in lowered and "keep" in lowered:
        return "draw_bonus_cards_keep_one"
    if "repeat a brown power" in lowered:
        return "repeat_brown_power"
    if "move it to another habitat" in lowered:
        return "move_bird_habitat"
    if lowered.startswith("trade") and "from the supply" in lowered:
        return "trade_food_with_supply"
    if "equal to the number of players" in lowered:
        return "draw_cards_player_select"
    if "face-up [card] in the bird tray" in lowered:
        return "draw_tray_cards"

    # Multi-player powers must be matched before the single-player templates they
    # resemble, otherwise they resolve as pure self-benefit and hide the cost of
    # handing resources to opponents.
    if lowered.startswith("all players") or lowered.startswith("each player"):
        if "[egg]" in lowered:
            return "all_players_lay_eggs"
        if "birdfeeder" in lowered or "[die]" in lowered:
            return "each_player_gains_birdfeeder_food"
        if DRAW_CARDS_PATTERN.search(lowered):
            return "all_players_draw_cards"
        if GAIN_FOOD_PATTERN.search(lowered):
            return "all_players_gain_food"
    if lowered.startswith("player(s) with the fewest"):
        if DRAW_CARDS_PATTERN.search(lowered):
            return "fewest_birds_draw_cards"
        if "birdfeeder" in lowered or "[die]" in lowered:
            return "fewest_birds_gain_food"

    if "predator" in lowered or "roll all dice" in lowered or "roll any" in lowered:
        return "predator_hunt"
    if "discard 1 [egg]" in lowered and DRAW_CARDS_PATTERN.search(lowered):
        return "discard_egg_draw_cards"
    if "discard 1 [egg]" in lowered and "gain 1 [wild]" in lowered:
        return "discard_egg_gain_wild_food"
    if "discard 1 [egg]" in lowered and "gain 2 [wild]" in lowered:
        return "discard_egg_gain_wild_food"
    if "discard 1" in lowered and "tuck" in lowered:
        return "discard_to_tuck"
    if "look at a [card] from the deck" in lowered and "tuck" in lowered:
        return "deck_search_tuck_by_wingspan"
    if "tuck 1 [card]" in lowered:
        return "tuck_card"
    if "cache 1" in lowered:
        return "cache_food"
    if "lay 1 [egg]" in lowered:
        return "lay_egg"
    if lowered.startswith("all players") and "gain 1 [" in lowered:
        return "all_players_gain_food"
    if lowered.startswith("all players") and "lay 1 [egg]" in lowered:
        return "all_players_lay_eggs"
    if "birdfeeder" in lowered or "gain 1 [die]" in lowered:
        return "gain_food_from_birdfeeder"
    if DRAW_CARDS_PATTERN.search(lowered) and "discard 1 [card]" in lowered:
        return "draw_cards_then_discard"
    if GAIN_FOOD_PATTERN.search(lowered):
        return "gain_food_from_supply"
    if DRAW_CARDS_PATTERN.search(lowered):
        return "draw_card"
    return None
