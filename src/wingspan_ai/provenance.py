"""Record which code version produced an artifact.

Why this exists
---------------
Batch manifests recorded a `schema_version` but nothing about the code that
generated the run. That made staleness unanswerable from the artifact itself: on
2026-09-03 a 322 MB archive could not be shown to be either reproducible or
superseded without reconstructing the working tree by hand, because the version
that produced it had never been committed and had since been edited over.

`dirty` is the load-bearing field. A clean commit means the run is reproducible
by checking that commit out; a dirty tree means it is not reproducible at all,
which is exactly when the artifact must be preserved rather than regenerated.
"""

from __future__ import annotations

import subprocess

#: Keep provenance collection from ever stalling a simulation batch.
GIT_TIMEOUT_SECONDS = 5.0


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def code_provenance() -> dict[str, object]:
    """Return the current commit, branch, and whether the tree has edits.

    Every field is None when the code is not in a git checkout, or when git is
    unavailable. Provenance is best-effort and must never fail a batch.
    """

    commit = _git("rev-parse", "HEAD")
    if commit is None:
        return {"git_commit": None, "git_branch": None, "dirty": None, "reproducible": None}

    status = _git("status", "--porcelain")
    dirty = None if status is None else bool(status)
    return {
        "git_commit": commit,
        "git_branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": dirty,
        # A dirty tree cannot be recovered from the commit alone, so the run
        # behind this artifact cannot be reproduced from version control.
        "reproducible": None if dirty is None else not dirty,
    }
