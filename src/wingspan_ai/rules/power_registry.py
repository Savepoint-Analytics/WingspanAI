"""Registry metadata for bird power handlers."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from wingspan_ai.content.schemas import ContentCatalog, PowerColor, PowerImplementationStatus

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
}


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
    if "predator" in lowered or "roll all dice" in lowered or "roll any" in lowered:
        return "predator_hunt"
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
    if "gain 1 [" in lowered:
        return "gain_food_from_supply"
    if "draw 1 [card]" in lowered:
        return "draw_card"
    return None
