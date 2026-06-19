"""SQLite-backed store for WorldFacts and ContradictionEvents."""

from __future__ import annotations

import json
import sqlite3
import time as _time_mod
from pathlib import Path
from typing import Any

from agentcrdt.fact import ContradictionEvent, WorldFact


class WorldStore:
    """Persistent store backed by a single SQLite database file.

    Supports context-manager usage::

        with WorldStore("world.db") as store:
            store.set_fact(fact)
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS facts (
        id TEXT PRIMARY KEY,
        domain TEXT NOT NULL,
        entity TEXT NOT NULL,
        attribute TEXT NOT NULL,
        value TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 0,
        agent_id TEXT NOT NULL DEFAULT '',
        timestamp REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        rule TEXT NOT NULL,
        facts_involved TEXT NOT NULL,
        agent_a TEXT NOT NULL,
        agent_b TEXT NOT NULL,
        timestamp REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS fact_history (
        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
        fact_id TEXT NOT NULL,
        domain TEXT NOT NULL,
        entity TEXT NOT NULL,
        attribute TEXT NOT NULL,
        value TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 0,
        agent_id TEXT NOT NULL DEFAULT '',
        timestamp REAL NOT NULL,
        recorded_at REAL NOT NULL
    );
    """

    def __init__(self, path: str | Path) -> None:
        """Open (or create) a WorldStore at *path*."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()

    def __enter__(self) -> WorldStore:
        """Support ``with WorldStore(...) as store:`` usage."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Close the store on context-manager exit."""
        self.close()

    def set_fact(self, fact: WorldFact) -> None:
        """Store or update a fact using LWW semantics (higher version wins, then timestamp)."""
        existing = self.get_fact(fact.id)
        if existing is not None:
            # LWW: higher version wins; on tie, higher timestamp wins
            if fact.version < existing.version:
                return
            if fact.version == existing.version and fact.timestamp <= existing.timestamp:
                return
        value_json = json.dumps(fact.value)
        self._conn.execute(
            "INSERT OR REPLACE INTO facts VALUES (?,?,?,?,?,?,?,?)",
            (
                fact.id,
                fact.domain,
                fact.entity,
                fact.attribute,
                value_json,
                fact.version,
                fact.agent_id,
                fact.timestamp,
            ),
        )
        # Log to history
        self._conn.execute(
            "INSERT INTO fact_history (fact_id, domain, entity, attribute,"
            " value, version, agent_id, timestamp, recorded_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                fact.id,
                fact.domain,
                fact.entity,
                fact.attribute,
                value_json,
                fact.version,
                fact.agent_id,
                fact.timestamp,
                _time_mod.time(),
            ),
        )
        self._conn.commit()

    def get_fact(self, fact_id: str) -> WorldFact | None:
        """Return a single :class:`WorldFact` by id, or ``None`` if not found."""
        row = self._conn.execute("SELECT * FROM facts WHERE id=?", (fact_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["value"] = json.loads(d["value"])
        return WorldFact.from_dict(d)

    def get_fact_by_key(self, domain: str, entity: str, attribute: str) -> WorldFact | None:
        """Return a fact looked up by its natural key ``(domain, entity, attribute)``.

        Convenience alternative to :meth:`get_fact` when you don't have the
        SHA-256 ``fact_id`` at hand.

        Args:
            domain:    Fact domain, e.g. ``"life"``.
            entity:    Entity name, e.g. ``"king"``.
            attribute: Attribute name, e.g. ``"alive"``.

        Returns:
            The matching :class:`WorldFact`, or ``None`` if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM facts WHERE domain=? AND entity=? AND attribute=?",
            (domain, entity, attribute),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["value"] = json.loads(d["value"])
        return WorldFact.from_dict(d)

    def list_facts(self, domain: str | None = None) -> list[WorldFact]:
        """Return all stored facts, optionally filtered by *domain*."""
        if domain:
            rows = self._conn.execute(
                "SELECT * FROM facts WHERE domain=? ORDER BY timestamp", (domain,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM facts ORDER BY timestamp").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["value"] = json.loads(d["value"])
            result.append(WorldFact.from_dict(d))
        return result

    def add_event(self, event: ContradictionEvent) -> None:
        """Persist a :class:`ContradictionEvent`."""
        self._conn.execute(
            "INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?)",
            (
                event.id,
                event.rule,
                json.dumps(event.facts_involved),
                event.agent_a,
                event.agent_b,
                event.timestamp,
            ),
        )
        self._conn.commit()

    def list_events(self) -> list[ContradictionEvent]:
        """Return all stored contradiction events ordered by timestamp."""
        rows = self._conn.execute("SELECT * FROM events ORDER BY timestamp").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["facts_involved"] = json.loads(d["facts_involved"])
            e = ContradictionEvent(
                rule=d["rule"],
                facts_involved=d["facts_involved"],
                agent_a=d["agent_a"],
                agent_b=d["agent_b"],
                timestamp=d["timestamp"],
            )
            result.append(e)
        return result

    def list_fact_history(self, fact_id: str) -> list[dict[str, Any]]:
        """Return all historical rows for a fact_id ordered by recorded_at ASC."""
        rows = self._conn.execute(
            "SELECT * FROM fact_history WHERE fact_id=? ORDER BY recorded_at ASC",
            (fact_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_fact_history_by_entity_attr(self, entity: str, attribute: str) -> list[dict[str, Any]]:
        """Return all historical rows for entity+attribute, ordered by recorded_at ASC."""
        rows = self._conn.execute(
            "SELECT * FROM fact_history WHERE entity=? AND attribute=? ORDER BY recorded_at ASC",
            (entity, attribute),
        ).fetchall()
        return [dict(r) for r in rows]

    def list_fact_history_by_entity(self, entity: str) -> list[dict[str, Any]]:
        """Return all historical rows for an entity, ordered by recorded_at ASC."""
        rows = self._conn.execute(
            "SELECT * FROM fact_history WHERE entity=? ORDER BY recorded_at ASC",
            (entity,),
        ).fetchall()
        return [dict(r) for r in rows]
