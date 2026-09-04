"""Experiment-level content filters over loaded game catalogs.

Strategy comparisons should be able to state exactly which rule coverage they
depend on. Filtering the catalog before a batch runs is preferable to filtering
results afterwards: an unsupported power that never enters the deck cannot
distort the economy loop, the tray, or opponent decisions.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from wingspan_ai.content.schemas import ContentCatalog, PowerColor, PowerImplementationStatus
from wingspan_ai.rules.power_registry import (
    IMPLEMENTED_POWER_STATUSES,
    POWER_HANDLER_REGISTRY,
    classify_power_handler_key,
)

MINIMUM_PLAYABLE_BIRD_COUNT = 40


@dataclass(frozen=True)
class CatalogFilterResult:
    """A filtered catalog plus the provenance needed for batch manifests."""

    catalog: ContentCatalog
    original_bird_count: int
    retained_bird_count: int
    excluded_bird_count: int
    allowed_statuses: tuple[str, ...]
    excluded_handler_keys: tuple[str, ...]
    excluded_bird_names: tuple[str, ...]

    @property
    def retention_rate(self) -> float:
        if not self.original_bird_count:
            return 1.0
        return self.retained_bird_count / self.original_bird_count

    def as_manifest_payload(self) -> dict[str, object]:
        """Return a JSON-serializable summary for batch manifests."""

        return {
            "original_bird_count": self.original_bird_count,
            "retained_bird_count": self.retained_bird_count,
            "excluded_bird_count": self.excluded_bird_count,
            "retention_rate": round(self.retention_rate, 4),
            "allowed_statuses": list(self.allowed_statuses),
            "excluded_handler_keys": list(self.excluded_handler_keys),
            "excluded_bird_names": list(self.excluded_bird_names),
        }


def resolve_bird_power_status(bird) -> PowerImplementationStatus:
    """Return the effective implementation status for one bird's power.

    Registry metadata wins over the status stored on the card, because the
    registry is the source of truth for what the rules engine can actually
    resolve at transition time.
    """

    if bird.power.color == PowerColor.NONE or not bird.power.text:
        return PowerImplementationStatus.NO_OP_FOR_V1
    handler_key = bird.power.handler_key or classify_power_handler_key(
        bird.power.text,
        bird.power.color,
    )
    metadata = POWER_HANDLER_REGISTRY.get(handler_key or "")
    if metadata is None:
        return bird.power.implementation_status
    return metadata.implementation_status


def filter_catalog_by_power_status(
    catalog: ContentCatalog,
    allowed_statuses: Iterable[PowerImplementationStatus | str] | None = None,
    *,
    excluded_handler_keys: Iterable[str] | None = None,
    minimum_bird_count: int = MINIMUM_PLAYABLE_BIRD_COUNT,
) -> CatalogFilterResult:
    """Drop birds whose powers fall outside the allowed implementation statuses.

    Passing ``allowed_statuses=None`` and no excluded handler keys is a no-op,
    which keeps the unfiltered path the default for batches that want the full
    deck.
    """

    resolved_statuses = (
        frozenset(IMPLEMENTED_POWER_STATUSES)
        if allowed_statuses is None
        else frozenset(PowerImplementationStatus(str(status)) for status in allowed_statuses)
    )
    resolved_excluded_keys = frozenset(excluded_handler_keys or ())

    retained = []
    excluded_names: list[str] = []
    excluded_keys: set[str] = set()
    for bird in catalog.birds:
        handler_key = bird.power.handler_key or classify_power_handler_key(
            bird.power.text,
            bird.power.color,
        )
        status = resolve_bird_power_status(bird)
        if status in resolved_statuses and (handler_key or "") not in resolved_excluded_keys:
            retained.append(bird)
            continue
        excluded_names.append(bird.common_name)
        excluded_keys.add(handler_key or "unclassified")

    if len(retained) < minimum_bird_count:
        raise ValueError(
            f"power-status filter retained only {len(retained)} birds, which is below the "
            f"minimum of {minimum_bird_count} needed for a playable base game; "
            "widen allowed_statuses or lower minimum_bird_count deliberately"
        )

    filtered_catalog = catalog.model_copy(update={"birds": retained})
    return CatalogFilterResult(
        catalog=filtered_catalog,
        original_bird_count=len(catalog.birds),
        retained_bird_count=len(retained),
        excluded_bird_count=len(excluded_names),
        allowed_statuses=tuple(sorted(status.value for status in resolved_statuses)),
        excluded_handler_keys=tuple(sorted(excluded_keys)),
        excluded_bird_names=tuple(sorted(excluded_names)),
    )
