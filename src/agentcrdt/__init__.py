"""agentcrdt — Semantic-causal CRDT for agent-mutable world state."""
from __future__ import annotations

import importlib.metadata

from agentcrdt.fact import ContradictionEvent, WorldFact
from agentcrdt.merger import MergeResult, WorldMerger
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore

__version__ = importlib.metadata.version("agentcrdt")

__all__ = [
    "ContradictionEvent",
    "MergeResult",
    "RuleEngine",
    "SemanticRule",
    "WorldFact",
    "WorldMerger",
    "WorldStore",
]
