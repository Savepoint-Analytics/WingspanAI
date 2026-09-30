"""Worktree reaping, which decides whether stale checkouts pile up beside the repo.

``launch_arm.py`` creates a detached worktree per arm so the code under test is
frozen at one commit while the main tree keeps moving. Nothing of value lives
there -- runners write to ``MAIN/artifacts/<root>`` -- so a finished worktree is
pure clutter, and seven of them accumulated because removal was a printed
reminder rather than a step. These pin the completion rule the reaper uses.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import analysis.launch_arm as launch_arm


class ArmCompletionTests(TestCase):
    def check(self, logs: dict[str, str]) -> bool:
        with TemporaryDirectory() as tmp:
            launch = Path(tmp) / "artifacts" / "some_arm" / "launch"
            launch.mkdir(parents=True)
            for name, body in logs.items():
                (launch / name).write_text(body)
            with patch.object(launch_arm, "MAIN", Path(tmp)):
                return launch_arm.arm_is_complete("some_arm")

    def test_complete_when_every_runner_log_has_the_marker(self) -> None:
        self.assertTrue(
            self.check({"a.log": "start\nGROUP COMPLETE\n", "b.log": "GROUP COMPLETE\n"})
        )

    def test_incomplete_when_one_runner_log_is_missing_the_marker(self) -> None:
        self.assertFalse(
            self.check({"a.log": "GROUP COMPLETE\n", "b.log": "still going\n"})
        )

    def test_incomplete_when_there_are_no_runner_logs(self) -> None:
        """An arm that never started must not be reaped as finished."""

        self.assertFalse(self.check({}))

    def test_queue_logs_do_not_count_as_runner_logs(self) -> None:
        """``queue.log`` never carries the marker; counting it would never complete."""

        self.assertFalse(self.check({"queue.log": "launched", "queue_runner.log": ""}))
        self.assertTrue(
            self.check({"queue.log": "launched", "a.log": "GROUP COMPLETE\n"})
        )

    def test_missing_launch_directory_is_not_complete(self) -> None:
        with TemporaryDirectory() as tmp, patch.object(launch_arm, "MAIN", Path(tmp)):
            self.assertFalse(launch_arm.arm_is_complete("never_existed"))


class ArmWorktreeListingTests(TestCase):
    PORCELAIN = (
        "worktree /repo/WingspanAI\nHEAD abc\nbranch refs/heads/main\n\n"
        "worktree /repo/WingspanAI-arm-rr_one\nHEAD def\ndetached\n\n"
        "worktree /repo/WingspanAI-arm-rr_two\nHEAD 123\ndetached\n\n"
        "worktree /repo/unrelated-checkout\nHEAD 456\ndetached\n"
    )

    def test_lists_only_arm_worktrees_and_strips_the_prefix(self) -> None:
        with (
            patch.object(launch_arm, "MAIN", Path("/repo/WingspanAI")),
            patch.object(launch_arm, "git", return_value=self.PORCELAIN),
        ):
            found = launch_arm.arm_worktrees()
        self.assertEqual([root for _path, root in found], ["rr_one", "rr_two"])

    def test_never_returns_the_main_tree(self) -> None:
        """Reaping the main checkout would be catastrophic."""

        with (
            patch.object(launch_arm, "MAIN", Path("/repo/WingspanAI")),
            patch.object(launch_arm, "git", return_value=self.PORCELAIN),
        ):
            paths = [path for path, _root in launch_arm.arm_worktrees()]
        self.assertNotIn(Path("/repo/WingspanAI"), paths)
        self.assertNotIn(Path("/repo/unrelated-checkout"), paths)
