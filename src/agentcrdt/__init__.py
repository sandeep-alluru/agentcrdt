"""agentcrdt — Semantic-causal CRDT for agent-mutable world state."""
from __future__ import annotations

import importlib.metadata

from agentcrdt.conflict_report import ConflictSummary, conflict_report, conflicts_for_entity
from agentcrdt.fact import ContradictionEvent, WorldFact
from agentcrdt.history import FactHistory, FactVersion
from agentcrdt.merger import MergeResult, WorldMerger
from agentcrdt.rules import RuleEngine, SemanticRule
from agentcrdt.store import WorldStore
from agentcrdt.watch import ChangeWatcher

__version__ = importlib.metadata.version("agentcrdt")

__all__ = [
    "ChangeWatcher",
    "ConflictSummary",
    "ContradictionEvent",
    "FactHistory",
    "FactVersion",
    "MergeResult",
    "RuleEngine",
    "SemanticRule",
    "WorldFact",
    "WorldMerger",
    "WorldStore",
    "conflict_report",
    "conflicts_for_entity",
]
