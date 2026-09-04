"""Code-provenance recording for simulation artifacts.

These pin the property that made provenance necessary: an artifact produced from
a dirty tree must be marked unreproducible, because the code that generated it
exists nowhere in version control.
"""

from __future__ import annotations

import subprocess

import pytest

from wingspan_ai import provenance
from wingspan_ai.provenance import code_provenance


def _fake_git(responses: dict[tuple[str, ...], tuple[int, str]]):
    def runner(command, **kwargs):
        args = tuple(command[1:])
        returncode, stdout = responses.get(args, (1, ""))
        return subprocess.CompletedProcess(command, returncode, stdout, "")

    return runner


CLEAN = {
    ("rev-parse", "HEAD"): (0, "abc123\n"),
    ("rev-parse", "--abbrev-ref", "HEAD"): (0, "main\n"),
    ("status", "--porcelain"): (0, "\n"),
}


def test_clean_tree_is_reproducible(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_git(CLEAN))
    result = code_provenance()
    assert result["git_commit"] == "abc123"
    assert result["git_branch"] == "main"
    assert result["dirty"] is False
    assert result["reproducible"] is True


def test_dirty_tree_is_not_reproducible(monkeypatch):
    responses = dict(CLEAN)
    responses[("status", "--porcelain")] = (0, " M flows/round_robin.py\n?? new.py\n")
    monkeypatch.setattr(subprocess, "run", _fake_git(responses))
    result = code_provenance()
    assert result["dirty"] is True
    assert result["reproducible"] is False


def test_outside_a_git_checkout_every_field_is_none(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _fake_git({}))
    assert code_provenance() == {
        "git_commit": None,
        "git_branch": None,
        "dirty": None,
        "reproducible": None,
    }


@pytest.mark.parametrize("failure", [OSError("git missing"), subprocess.TimeoutExpired("git", 5)])
def test_provenance_never_raises(monkeypatch, failure):
    """A batch must never fail because provenance could not be collected."""

    def explode(*args, **kwargs):
        raise failure

    monkeypatch.setattr(subprocess, "run", explode)
    assert code_provenance()["git_commit"] is None


def test_git_calls_are_bounded_by_a_timeout(monkeypatch):
    seen = []

    def runner(command, **kwargs):
        seen.append(kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(subprocess, "run", runner)
    code_provenance()
    assert seen and all(t == provenance.GIT_TIMEOUT_SECONDS for t in seen)
