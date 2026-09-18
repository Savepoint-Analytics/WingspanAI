"""Decision-tree profiling: nodes, aggregation, self time, no-op cost, telemetry."""

from time import perf_counter_ns, sleep
from unittest import TestCase

from wingspan_ai.agents import GreedyBaselineAgent, PotentialPointsAgent, profiling
from wingspan_ai.content import make_sample_catalog
from wingspan_ai.simulation.runner import run_single_game


class ProfilerTests(TestCase):
    def test_structural_and_aggregated_nodes_build_a_tree(self) -> None:
        with profiling.activate("select_action") as profiler:
            with profiling.node("determinize", output_count=3):
                pass
            for index in range(2):
                with profiling.node("score_sample", aggregate=False, sample_index=index):
                    for _ in range(5):
                        with profiling.node("terminal_value"):
                            pass
        trace = profiler.finish()
        tree = trace.tree_payload()
        self.assertEqual(tree["name"], "select_action")
        names = [child["name"] for child in tree["children"]]
        self.assertEqual(names, ["determinize", "score_sample", "score_sample"])
        sample = tree["children"][1]
        self.assertEqual(sample["metadata"], {"sample_index": 0})
        self.assertEqual(sample["children"][0]["name"], "terminal_value")
        self.assertEqual(sample["children"][0]["count"], 5)
        summary = trace.summary_payload()
        self.assertEqual(summary["nodes"]["terminal_value"]["count"], 10)
        self.assertEqual(summary["nodes"]["score_sample"]["count"], 2)
        self.assertEqual(summary["nodes"]["determinize"]["depth"], 1)
        self.assertEqual(summary["nodes"]["terminal_value"]["depth"], 2)

    def test_self_time_excludes_children_and_shares_add_up(self) -> None:
        with profiling.activate("select_action") as profiler:
            with profiling.node("outer", aggregate=False):
                sleep(0.01)
                with profiling.node("inner"):
                    sleep(0.01)
        summary = profiler.finish().summary_payload()
        outer, inner = summary["nodes"]["outer"], summary["nodes"]["inner"]
        self.assertGreater(outer["elapsed_ms"], inner["elapsed_ms"])
        # Each figure is rounded to 3 decimals independently, so allow one unit.
        self.assertAlmostEqual(
            outer["self_ms"], outer["elapsed_ms"] - inner["elapsed_ms"], delta=0.002
        )
        accounted = sum(n["self_ms"] for n in summary["nodes"].values()) + summary["unprofiled_ms"]
        self.assertAlmostEqual(accounted, summary["total_ms"], places=2)

    def test_node_is_a_cheap_no_op_without_an_active_profiler(self) -> None:
        self.assertIsNone(profiling.active())
        with profiling.node("anything", candidate_count=3) as node:
            node.set(chosen=True)  # the null node accepts metadata silently
        started = perf_counter_ns()
        for _ in range(20000):
            with profiling.node("hot"):
                pass
        per_call_ns = (perf_counter_ns() - started) / 20000
        self.assertLess(per_call_ns, 3000)

    def test_modes(self) -> None:
        with profiling.activate("x") as profiler:
            with profiling.node("a"):
                pass
        trace = profiler.finish()
        self.assertIsNone(trace.payload("off"))
        self.assertNotIn("tree", trace.payload("summary"))
        self.assertIn("tree", trace.payload("tree"))


class ProfileTelemetryTests(TestCase):
    def test_runner_attaches_profiles_to_decisions_and_setup(self) -> None:
        catalog = make_sample_catalog()
        result = run_single_game(
            catalog,
            [
                PotentialPointsAgent(agent_id="pp", search_depth=1, final_search_turns=0),
                GreedyBaselineAgent(agent_id="g"),
            ],
            random_seed=2,
            max_turns=4,
            decision_profile_mode="tree",
        )
        decisions = [e for e in result.events if e.event_name == "agent_decision_summary"]
        pp = next(e for e in decisions if e.agent_id == "pp")
        profile = pp.payload["decision_profile"]
        self.assertEqual(profile["decision_type"], "select_action")
        self.assertIn("evaluate_actions", profile["nodes"])
        self.assertIn("tree", profile)
        self.assertAlmostEqual(
            profile["total_ms"], pp.payload["action_selection_elapsed_ms"], delta=5.0
        )
        setup = next(e for e in result.events if e.event_name == "setup_selection_applied")
        self.assertEqual(
            setup.payload["decision_profile"]["decision_type"], "choose_initial_selection"
        )
        off = run_single_game(
            catalog,
            [GreedyBaselineAgent(agent_id="a"), GreedyBaselineAgent(agent_id="b")],
            random_seed=2,
            max_turns=2,
            decision_profile_mode="off",
        )
        first = next(e for e in off.events if e.event_name == "agent_decision_summary")
        self.assertIsNone(first.payload["decision_profile"])
        with self.assertRaises(ValueError):
            run_single_game(
                catalog,
                [GreedyBaselineAgent(agent_id="a")],
                random_seed=1,
                decision_profile_mode="loud",
            )


class CacheAccountingTests(TestCase):
    def test_cache_hits_are_counted_per_node(self) -> None:
        with profiling.activate("x") as profiler:
            for hit in (True, False, True):
                with profiling.node("lookup") as node:
                    node.set(cache_hit=hit)
        summary = profiler.finish().summary_payload()
        self.assertEqual(summary["nodes"]["lookup"]["cache_hits"], 2)
        self.assertEqual(summary["nodes"]["lookup"]["cache_misses"], 1)
