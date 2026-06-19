"""Fact history tracking — all historical versions of each fact."""
from __future__ import annotations

import json
from dataclasses import dataclass

from agentcrdt.fact import WorldFact
from agentcrdt.store import WorldStore


@dataclass
class FactVersion:
    fact: WorldFact
    superseded_by: str | None   # ID of fact that replaced this (None if current)
    version_index: int


class FactHistory:
    def __init__(self, store: WorldStore) -> None:
        self._store = store

    def get_history(self, entity: str, attribute: str) -> list[FactVersion]:
        """Return all versions of a fact, newest first."""
        rows = self._store.list_fact_history_by_entity_attr(entity, attribute)
        versions: list[FactVersion] = []
        for i, row in enumerate(rows):
            fact = WorldFact.from_dict({
                "domain": row["domain"],
                "entity": row["entity"],
                "attribute": row["attribute"],
                "value": json.loads(row["value"]),
                "version": row["version"],
                "agent_id": row["agent_id"],
                "timestamp": row["timestamp"],
            })
            superseded_by = rows[i - 1]["fact_id"] if i > 0 else None
            versions.append(FactVersion(
                fact=fact,
                superseded_by=superseded_by,
                version_index=len(rows) - 1 - i,
            ))
        return versions

    def get_at_time(self, entity: str, attribute: str, timestamp: float) -> WorldFact | None:
        """Return the fact that was current at a given timestamp."""
        rows = self._store.list_fact_history_by_entity_attr(entity, attribute)
        # Find the last row recorded at or before the given timestamp
        candidate = None
        for row in rows:
            if row["recorded_at"] <= timestamp:
                candidate = row
        if candidate is None:
            return None
        return WorldFact.from_dict({
            "domain": candidate["domain"],
            "entity": candidate["entity"],
            "attribute": candidate["attribute"],
            "value": json.loads(candidate["value"]),
            "version": candidate["version"],
            "agent_id": candidate["agent_id"],
            "timestamp": candidate["timestamp"],
        })

    def diff_entity(self, entity: str) -> dict[str, list[FactVersion]]:
        """Return full history of all attributes for an entity."""
        rows = self._store.list_fact_history_by_entity(entity)
        attributes: set[str] = set()
        for row in rows:
            attributes.add(row["attribute"])
        result: dict[str, list[FactVersion]] = {}
        for attr in sorted(attributes):
            result[attr] = self.get_history(entity, attr)
        return result
