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
        implementation_status=PowerImplementationStatus.NOT_IMPLEMENTED,
        source_reference="Core rulebook: brown powers and forest activation",
        notes="High-priority base economy handler for common gain-food powers.",
    ),
    "draw_card": PowerHandlerMetadata(
        handler_key="draw_card",
        implementation_status=PowerImplementationStatus.NOT_IMPLEMENTED,
        source_reference="Core rulebook: brown powers and wetland activation",
        notes="High-priority card-flow handler for early engine experiments.",
    ),
}
