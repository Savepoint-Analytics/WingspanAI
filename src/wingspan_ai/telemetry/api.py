"""Draft FastAPI ingestion service for simulation events."""

from __future__ import annotations

from wingspan_ai.telemetry.events import EventBatch, SimulationEvent

EVENT_STORE: list[SimulationEvent] = []


def create_app():
    """Create the FastAPI app.

    FastAPI is imported lazily so core simulator tests do not require service
    dependencies before the ingestion service is actively used.
    """

    try:
        from fastapi import FastAPI
    except ImportError as error:
        raise RuntimeError(
            "FastAPI is required for the ingestion service. "
            "Install the api optional dependencies before running this app."
        ) from error

    app = FastAPI(title="Wingspan AI Telemetry API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/events")
    def ingest_events(batch: EventBatch) -> dict[str, int]:
        EVENT_STORE.extend(batch.events)
        return {"accepted": len(batch.events)}

    @app.get("/events")
    def list_events() -> list[SimulationEvent]:
        return EVENT_STORE

    return app


try:
    app = create_app()
except RuntimeError:
    app = None
