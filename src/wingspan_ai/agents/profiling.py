"""Decision-tree profiling: where the milliseconds inside one decision go.

Why this module exists
----------------------
Until 2026-09-17 the project timed a decision as one number
(``action_selection_elapsed_ms``). That is enough to say an arm is slow, not
enough to say *why*: the 40% of search time that turned out to be the
opponent model was found by hand once, and the question will come back for
every agent that is meant to ship. Production needs value per millisecond,
and value per millisecond needs the millisecond side broken down by node.

Design
------
A ``DecisionProfiler`` is active for the duration of one decision. Code
anywhere below it records nodes with ``profiling.node("name", ...)``, a
context manager that looks up the active profiler in a context variable and
is a no-op when none is active (a couple of hundred nanoseconds), so the
instrumentation can live in hot paths permanently.

Two kinds of node, because a depth-3 search visits thousands of branches per
decision and a tree with one entry per branch would swamp the telemetry:

- **structural** nodes (``aggregate=False``) become one tree entry each,
  with their own children — root candidates, determinization samples;
- **aggregated** nodes (``aggregate=True``, the default) are merged into one
  entry per name under the same parent, carrying ``count`` and total time —
  search branches, opponent turns, terminal evaluations, apply_action.

Every node records ``elapsed_ns``, the parent, and free metadata:
``candidate_count``, ``input_count``, ``output_count``, ``cache_hit``,
``score_delta``, ``chosen``. The trace serializes as a nested tree
(``mode="tree"``) or as a compact per-name summary (``mode="summary"``); the
runner attaches whichever the batch asked for to ``agent_decision_summary``.

This layer knows nothing about Wingspan. It is part of the reusable
board-game template: any agent for any game reports its decision tree the
same way, and ``analysis/decision_profile_report.py`` reads it the same way.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any

PROFILE_MODES = ("off", "summary", "tree")
DEFAULT_PROFILE_MODE = "summary"

_active: ContextVar[DecisionProfiler | None] = ContextVar("decision_profiler", default=None)


@dataclass
class ProfileNode:
    """One node of a decision trace; aggregated nodes fold repeats into ``count``."""

    node_id: int
    name: str
    parent_id: int | None
    aggregate: bool
    elapsed_ns: int = 0
    count: int = 0
    #: Calls that reported ``cache_hit=True`` / ``False`` via ``node.set``.
    cache_hits: int = 0
    cache_misses: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[ProfileNode] = field(default_factory=list)
    _by_name: dict[str, ProfileNode] = field(default_factory=dict, repr=False)

    def set(self, **metadata: Any) -> None:
        """Attach or update metadata on the node from inside its block."""

        self.metadata.update(metadata)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "elapsed_ms": round(self.elapsed_ns / 1e6, 3),
            "count": self.count,
        }
        if self.cache_hits or self.cache_misses:
            payload["cache_hits"] = self.cache_hits
            payload["cache_misses"] = self.cache_misses
        if self.metadata:
            payload["metadata"] = _json_safe(self.metadata)
        if self.children:
            payload["children"] = [child.to_payload() for child in self.children]
        return payload


@dataclass
class DecisionProfiler:
    """Records one decision's node tree. Activate with ``profiling.activate``."""

    decision_type: str
    root: ProfileNode = field(init=False)
    _stack: list[ProfileNode] = field(default_factory=list, repr=False)
    _next_id: int = field(default=1, repr=False)
    _started_ns: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        self.root = ProfileNode(node_id=0, name=self.decision_type, parent_id=None, aggregate=False)
        self._stack = [self.root]
        self._started_ns = perf_counter_ns()

    def _open(self, name: str, aggregate: bool, metadata: dict[str, Any]) -> ProfileNode:
        parent = self._stack[-1]
        if aggregate:
            node = parent._by_name.get(name)
            if node is None:
                node = ProfileNode(
                    node_id=self._next_id, name=name, parent_id=parent.node_id, aggregate=True
                )
                self._next_id += 1
                parent._by_name[name] = node
                parent.children.append(node)
        else:
            node = ProfileNode(
                node_id=self._next_id, name=name, parent_id=parent.node_id, aggregate=False
            )
            self._next_id += 1
            parent.children.append(node)
        if metadata:
            node.metadata.update(metadata)
        self._stack.append(node)
        return node

    def _close(self, node: ProfileNode, elapsed_ns: int) -> None:
        node.elapsed_ns += elapsed_ns
        node.count += 1
        hit = node.metadata.pop("cache_hit", None)
        if hit is True:
            node.cache_hits += 1
        elif hit is False:
            node.cache_misses += 1
        popped = self._stack.pop()
        assert popped is node, "profiler nodes must close in LIFO order"

    def finish(self) -> DecisionTrace:
        self.root.elapsed_ns = perf_counter_ns() - self._started_ns
        self.root.count = 1
        return DecisionTrace(self.root)


@dataclass(frozen=True)
class DecisionTrace:
    """A finished decision tree with its serializations."""

    root: ProfileNode

    @property
    def total_ms(self) -> float:
        return self.root.elapsed_ns / 1e6

    def tree_payload(self) -> dict[str, Any]:
        return self.root.to_payload()

    def summary_payload(self) -> dict[str, Any]:
        """Per-name totals across the whole tree: count, ms, share of the decision."""

        totals: dict[str, dict[str, float]] = {}

        def walk(node: ProfileNode, depth: int) -> None:
            for child in node.children:
                entry = totals.setdefault(
                    child.name,
                    {
                        "count": 0,
                        "elapsed_ms": 0.0,
                        "self_ms": 0.0,
                        "depth": depth,
                        "cache_hits": 0,
                        "cache_misses": 0,
                    },
                )
                entry["count"] += child.count
                entry["cache_hits"] += child.cache_hits
                entry["cache_misses"] += child.cache_misses
                entry["elapsed_ms"] += child.elapsed_ns / 1e6
                # Self time excludes children, so shares add up across nesting.
                entry["self_ms"] += (
                    child.elapsed_ns - sum(grand.elapsed_ns for grand in child.children)
                ) / 1e6
                walk(child, depth + 1)

        walk(self.root, 1)
        total = max(self.total_ms, 1e-9)
        accounted = sum(entry["self_ms"] for entry in totals.values())
        return {
            "decision_type": self.root.name,
            "total_ms": round(self.total_ms, 3),
            "unprofiled_ms": round(max(self.total_ms - accounted, 0.0), 3),
            "nodes": {
                name: {
                    "count": int(entry["count"]),
                    "elapsed_ms": round(entry["elapsed_ms"], 3),
                    "self_ms": round(entry["self_ms"], 3),
                    "share": round(entry["self_ms"] / total, 4),
                    "depth": int(entry["depth"]),
                    **(
                        {
                            "cache_hits": int(entry["cache_hits"]),
                            "cache_misses": int(entry["cache_misses"]),
                        }
                        if entry["cache_hits"] or entry["cache_misses"]
                        else {}
                    ),
                }
                for name, entry in sorted(totals.items(), key=lambda kv: -kv[1]["self_ms"])
            },
        }

    def payload(self, mode: str) -> dict[str, Any] | None:
        if mode == "off":
            return None
        payload = self.summary_payload()
        if mode == "tree":
            payload["tree"] = self.tree_payload()
        return payload


@contextlib.contextmanager
def activate(decision_type: str) -> Iterator[DecisionProfiler]:
    """Make a profiler active for the block; nested activations stack."""

    profiler = DecisionProfiler(decision_type)
    token = _active.set(profiler)
    try:
        yield profiler
    finally:
        _active.reset(token)


def active() -> DecisionProfiler | None:
    return _active.get()


class _NullNode:
    __slots__ = ()

    def set(self, **metadata: Any) -> None:
        return None


_NULL_NODE = _NullNode()


class _NodeContext:
    """Context manager for one profiled block; a no-op when nothing is active."""

    __slots__ = ("_profiler", "_node", "_name", "_aggregate", "_metadata", "_start")

    def __init__(self, name: str, aggregate: bool, metadata: dict[str, Any]) -> None:
        self._profiler = _active.get()
        self._name = name
        self._aggregate = aggregate
        self._metadata = metadata
        self._node: ProfileNode | None = None
        self._start = 0

    def __enter__(self) -> ProfileNode | _NullNode:
        if self._profiler is None:
            return _NULL_NODE
        self._node = self._profiler._open(self._name, self._aggregate, self._metadata)
        self._start = perf_counter_ns()
        return self._node

    def __exit__(self, *exc: object) -> None:
        if self._node is not None and self._profiler is not None:
            self._profiler._close(self._node, perf_counter_ns() - self._start)


def node(name: str, *, aggregate: bool = True, **metadata: Any) -> _NodeContext:
    """Profile a block as ``name`` under the current node.

    ``aggregate=True`` (default) folds repeated calls into one entry with a
    count — use it for anything called many times per decision. Structural
    nodes that should appear individually (samples, root candidates) pass
    ``aggregate=False``. Metadata keys are free; the report understands
    ``candidate_count``, ``input_count``, ``output_count``, ``cache_hit``,
    ``score_delta`` and ``chosen``.
    """

    return _NodeContext(name, aggregate, metadata)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_safe(v) for v in value]
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    return str(value)
