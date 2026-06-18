"""WorldMerger — merge two WorldStores with CRDT semantics + semantic rule checking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentcrdt.fact import ContradictionEvent
from agentcrdt.rules import RuleEngine
from agentcrdt.store import WorldStore


@dataclass
class MergeResult:
    """Summary of a completed merge operation."""

    merged_count: int
    conflicts: list[ContradictionEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON output."""
        return {
            "merged_count": self.merged_count,
            "conflicts": [c.to_dict() for c in self.conflicts],
        }


class WorldMerger:
    """Merge a remote :class:`WorldStore` into a local one using CRDT semantics.

    Uses Last-Write-Wins (LWW) per fact key.  After merging, optionally runs
    the provided :class:`~agentcrdt.rules.RuleEngine` to detect semantic
    contradictions and records them as :class:`~agentcrdt.fact.ContradictionEvent`
    objects.
    """

    def __init__(self, rule_engine: RuleEngine | None = None) -> None:
        """Initialise with an optional rule engine for contradiction detection."""
        self.rule_engine = rule_engine

    def merge(self, local: WorldStore, remote: WorldStore) -> MergeResult:
        """Merge *remote* into *local* using LWW CRDT semantics.

        Args:
            local:  The target store (modified in-place).
            remote: The source store (read-only).

        Returns:
            A :class:`MergeResult` with the number of facts merged and any
            contradiction events detected by the rule engine.
        """
        merged = 0
        remote_facts = remote.list_facts()
        for fact in remote_facts:
            local.set_fact(fact)
            merged += 1

        conflicts: list[ContradictionEvent] = []
        if self.rule_engine is not None:
            all_facts = {f.id: f for f in local.list_facts()}
            conflicts = self.rule_engine.check(all_facts)
            for evt in conflicts:
                local.add_event(evt)

        return MergeResult(merged_count=merged, conflicts=conflicts)
