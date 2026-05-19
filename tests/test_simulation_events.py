from unittest import TestCase

from wingspan_ai.telemetry.events import EventBatch, EventName, SimulationEvent


class SimulationEventTests(TestCase):
    def test_simulation_event_envelope_validates_required_fields(self) -> None:
        event = SimulationEvent(
            event_name=EventName.ACTION_SELECTED,
            simulation_run_id="run_1",
            game_id="game_1",
            ruleset_id="core_base_game_v1",
            player_id="player_1",
            agent_id="random_legal",
            round_number=1,
            turn_number=1,
            round_turn_number=1,
            random_seed=11,
            payload={"action": {"action_type": "draw_cards"}},
        )

        self.assertEqual(event.event_version, "1.0")
        self.assertEqual(event.round_turn_number, 1)
        self.assertFalse(event.private_state_included)
        self.assertEqual(event.payload["action"]["action_type"], "draw_cards")

    def test_event_batch_accepts_events(self) -> None:
        event = SimulationEvent(
            event_name=EventName.GAME_STARTED,
            simulation_run_id="run_1",
            game_id="game_1",
        )

        batch = EventBatch(events=[event])

        self.assertEqual(batch.events, [event])
