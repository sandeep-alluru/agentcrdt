"""agentcrdt — Semantic-causal CRDT for agent-mutable world state."""

from __future__ import annotations

import importlib.metadata

from agentcrdt.closed_loop import (
    ClosedLoopError,
    GateOutcome,
    assert_mutable_write,
    assert_world_state_ok,
    gate_world_state,
    is_constant_domain,
    refuse_constant_write,
    set_fact_if_mutable,
)
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
    "ClosedLoopError",
    "ConflictSummary",
    "ContradictionEvent",
    "FactHistory",
    "FactVersion",
    "GateOutcome",
    "MergeResult",
    "RuleEngine",
    "SemanticRule",
    "WorldFact",
    "WorldMerger",
    "WorldStore",
    "assert_mutable_write",
    "assert_world_state_ok",
    "conflict_report",
    "conflicts_for_entity",
    "gate_world_state",
    "is_constant_domain",
    "refuse_constant_write",
    "set_fact_if_mutable",
]
