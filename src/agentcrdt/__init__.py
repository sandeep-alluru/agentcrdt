"""agentcrdt - Semantic-causal CRDT for agent-mutable world state."""

from __future__ import annotations

import importlib.metadata

from agentcrdt.closed_loop import (
    ClosedLoopError,
    GateOutcome,
    ValueDivergence,
    assert_multi_agent_ok,
    assert_mutable_write,
    assert_world_state_ok,
    detect_silent_divergences,
    gate_merge_result,
    gate_multi_agent,
    gate_world_state,
    is_constant_domain,
    refuse_constant_write,
    set_fact_if_mutable,
)
from agentcrdt.collusion import (
    AgentTraceEvent,
    CollusionReport,
    CollusionSignal,
    assert_no_covert_collusion,
    detect_covert_collusion,
    gate_covert_collusion,
)
from agentcrdt.comm_attack import (
    AgentMessage,
    CommAttackReport,
    CommAttackSignal,
    analyze_comm_attacks,
    assert_comm_integrity,
    detect_comm_injection_phrases,
    gate_comm_integrity,
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
    "AgentMessage",
    "AgentTraceEvent",
    "ChangeWatcher",
    "ClosedLoopError",
    "CollusionReport",
    "CollusionSignal",
    "CommAttackReport",
    "CommAttackSignal",
    "ConflictSummary",
    "ContradictionEvent",
    "FactHistory",
    "FactVersion",
    "GateOutcome",
    "MergeResult",
    "RuleEngine",
    "SemanticRule",
    "ValueDivergence",
    "WorldFact",
    "WorldMerger",
    "WorldStore",
    "analyze_comm_attacks",
    "assert_comm_integrity",
    "assert_multi_agent_ok",
    "assert_mutable_write",
    "assert_no_covert_collusion",
    "assert_world_state_ok",
    "conflict_report",
    "conflicts_for_entity",
    "detect_comm_injection_phrases",
    "detect_covert_collusion",
    "detect_silent_divergences",
    "gate_comm_integrity",
    "gate_covert_collusion",
    "gate_merge_result",
    "gate_multi_agent",
    "gate_world_state",
    "is_constant_domain",
    "refuse_constant_write",
    "set_fact_if_mutable",
]
