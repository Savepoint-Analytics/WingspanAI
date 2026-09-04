"""Round robins must inherit the object-storage auto-detect, not override it.

Why this exists
---------------
`flows/simulation_batch.py` uploads a batch's artifacts whenever object storage
is configured, and `flows/README.md` documented exactly that. But
`flows/round_robin.py` hardcoded `upload_artifacts=False`, silently overriding
it, and round robins produce nearly all of the project's data. 1.7 GB
accumulated on local disk with no durable copy while the bucket held only smoke
tests, and nothing failed, because no test asserted the documented behaviour.

These tests pin the contract without needing live services.
"""

from __future__ import annotations

import inspect
from unittest import TestCase
from unittest.mock import patch

from flows import round_robin
from flows.round_robin import run_round_robin
from flows.simulation_batch import run_simulation_batch


class UploadDefaultTests(TestCase):
    def test_round_robin_default_defers_to_storage_configuration(self) -> None:
        """None means "upload if storage is configured"; False disables it outright."""

        default = inspect.signature(run_round_robin).parameters["upload_artifacts"].default
        self.assertIsNone(
            default,
            "run_round_robin must not hardcode a value that overrides the "
            "auto-detect in run_simulation_batch",
        )

    def test_batch_default_defers_to_storage_configuration(self) -> None:
        default = inspect.signature(run_simulation_batch).parameters["upload_artifacts"].default
        self.assertIsNone(default)

    def test_default_is_forwarded_unchanged_to_each_cell(self) -> None:
        """The value must reach run_simulation_batch, not be reinterpreted en route."""

        self.assertIsNone(self._first_cell_upload_value())

    def test_explicit_false_still_disables_upload(self) -> None:
        """Opting out must remain possible for offline or throwaway runs."""

        self.assertIs(self._first_cell_upload_value(upload_artifacts=False), False)

    def _first_cell_upload_value(self, **overrides):
        """Run far enough to capture the first cell's kwargs, then abort.

        Aborting keeps this a contract test: it asserts what round robin forwards
        without depending on the shape of the summaries built afterwards.
        """

        captured: dict = {}

        class _Abort(Exception):
            pass

        def capture(**kwargs):
            captured.update(kwargs)
            raise _Abort

        with patch.object(round_robin, "run_simulation_batch", side_effect=capture):
            with self.assertRaises(_Abort):
                run_round_robin(
                    seeds=[1],
                    player_count=2,
                    roster=["random_legal", "greedy_immediate"],
                    batch_kind="smoke",
                    **overrides,
                )

        self.assertIn("upload_artifacts", captured)
        return captured["upload_artifacts"]
