from unittest import TestCase

from wingspan_ai.content.schemas import PowerImplementationStatus
from wingspan_ai.rules.power_registry import POWER_HANDLER_REGISTRY


class PowerRegistryTests(TestCase):
    def test_power_registry_tracks_source_and_status(self) -> None:
        handler = POWER_HANDLER_REGISTRY["no_power"]

        self.assertEqual(handler.implementation_status, PowerImplementationStatus.NO_OP_FOR_V1)
        self.assertIn("rulebook", handler.source_reference.lower())
