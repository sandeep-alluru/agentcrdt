"""Conflict reporting — summarize ContradictionEvents from a WorldStore."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentcrdt.fact import ContradictionEvent
from agentcrdt.store import WorldStore


@dataclass
class ConflictSummary:
    total_conflicts: int
    by_rule: dict[str, int]
    by_entity: dict[str, int]
    most_contested_entities: list[str]
    conflict_timeline: list[dict]
    resolution_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_conflicts": self.total_conflicts,
            "by_rule": self.by_rule,
            "by_entity": self.by_entity,
            "most_contested_entities": self.most_contested_entities,
            "conflict_timeline": self.conflict_timeline,
            "resolution_rate": self.resolution_rate,
        }


def conflict_report(store: WorldStore) -> ConflictSummary:
    """Generate a summary of all ContradictionEvents in the store."""
    events = store.list_events()
    total = len(events)

    by_rule: dict[str, int] = {}
    by_entity: dict[str, int] = {}
    timeline: list[dict] = []

    facts_index = {f.id: f for f in store.list_facts()}

    for event in events:
        by_rule[event.rule] = by_rule.get(event.rule, 0) + 1

        # Try to extract entity from involved facts
        entities_in_event: list[str] = []
        for fid in event.facts_involved:
            f = facts_index.get(fid)
            if f:
                entities_in_event.append(f.entity)
                by_entity[f.entity] = by_entity.get(f.entity, 0) + 1

        timeline.append({
            "timestamp": event.timestamp,
            "rule": event.rule,
            "entity": entities_in_event[0] if entities_in_event else "unknown",
            "values": event.facts_involved,
        })

    # Sort most contested entities by count
    most_contested = sorted(by_entity, key=lambda e: by_entity[e], reverse=True)[:5]

    # resolution_rate: fraction of conflicts that are auto-resolved (vs needing human review)
    # We approximate: events where agent_a and agent_b are non-empty are "auto" resolved
    auto_resolved = sum(
        1 for e in events if e.agent_a and e.agent_b
    )
    resolution_rate = auto_resolved / total if total > 0 else 0.0

    return ConflictSummary(
        total_conflicts=total,
        by_rule=by_rule,
        by_entity=by_entity,
        most_contested_entities=most_contested,
        conflict_timeline=sorted(timeline, key=lambda x: x["timestamp"]),
        resolution_rate=resolution_rate,
    )


def conflicts_for_entity(store: WorldStore, entity: str) -> list[ContradictionEvent]:
    """Get all conflicts for a specific entity."""
    facts_for_entity = {f.id for f in store.list_facts() if f.entity == entity}
    return [
        e for e in store.list_events()
        if any(fid in facts_for_entity for fid in e.facts_involved)
    ]
