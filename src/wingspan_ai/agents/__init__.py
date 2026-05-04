"""Agent policies and strategy archetypes."""

from wingspan_ai.agents.greedy import GreedyBaselineAgent
from wingspan_ai.agents.random_legal import RandomLegalAgent

__all__ = ["GreedyBaselineAgent", "RandomLegalAgent"]
