"""Registry metadata for bird power handlers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from wingspan_ai.content.schemas import PowerImplementationStatus


class PowerHandlerMetadata(BaseModel):
    """Traceable status for one executable or planned power handler."""

    model_config = ConfigDict(extra="forbid")

    handler_key: str
    implementation_status: PowerImplementationStatus
    source_reference: str
    module_path: str | None = None
    test_reference: str | None = None
    notes: str | None = None


POWER_HANDLER_REGISTRY: dict[str, PowerHandlerMetadata] = {
    "no_power": PowerHandlerMetadata(
        handler_key="no_power",
        implementation_status=PowerImplementationStatus.NO_OP_FOR_V1,
        source_reference="Core rulebook: birds without powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Cards with no power require no transition-time handler.",
    ),
    "gain_food_from_birdfeeder": PowerHandlerMetadata(
        handler_key="gain_food_from_birdfeeder",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: brown powers and forest activation",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="High-priority base economy handler for common gain-food powers.",
    ),
    "draw_card": PowerHandlerMetadata(
        handler_key="draw_card",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: brown powers and wetland activation",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="High-priority card-flow handler for early engine experiments.",
    ),
    "lay_egg": PowerHandlerMetadata(
        handler_key="lay_egg",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: white, brown, and pink egg powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Covers simple lay-one-egg templates with deterministic target selection.",
    ),
    "tuck_card": PowerHandlerMetadata(
        handler_key="tuck_card",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: brown tuck powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Covers simple tuck-one-card templates and tuck-then-draw variants.",
    ),
    "cache_food": PowerHandlerMetadata(
        handler_key="cache_food",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: cache food powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="Covers simple cache-one-food templates.",
    ),
    "pink_reaction": PowerHandlerMetadata(
        handler_key="pink_reaction",
        implementation_status=PowerImplementationStatus.HEURISTIC_RESOLUTION,
        source_reference="Core rulebook: pink opponent-turn powers",
        module_path="wingspan_ai.rules.base_game",
        test_reference="tests/test_base_game_rules.py",
        notes="First deterministic hooks for lay-egg, food-gain, cache, and tuck reactions.",
    ),
}
