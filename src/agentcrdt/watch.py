"""Change watching — subscribe to WorldStore mutations."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agentcrdt.fact import WorldFact
from agentcrdt.store import WorldStore


class ChangeWatcher:
    """Watch a WorldStore for changes to specific entities or attributes."""

    def __init__(self, store: WorldStore) -> None:
        self._store = store
        self._callbacks: list[tuple[str | None, str | None, Callable[..., Any]]] = []
        # Snapshot: "entity::attribute" -> WorldFact
        self._last_snapshot: dict[str, WorldFact] = self._take_snapshot()

    def on_change(self, entity: str | None = None, attribute: str | None = None) -> Callable[..., Any]:
        """Decorator: register a callback for when a matching fact changes."""

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            self._callbacks.append((entity, attribute, fn))
            return fn

        return decorator

    def check(self) -> list[WorldFact]:
        """Check for new facts since last check. Returns changed facts and fires callbacks."""
        current = self._take_snapshot()
        changed: list[WorldFact] = []

        for key, fact in current.items():
            old_fact = self._last_snapshot.get(key)
            if old_fact is None or (
                fact.version != old_fact.version
                or fact.timestamp != old_fact.timestamp
                or fact.value != old_fact.value
            ):
                changed.append(fact)

        self._last_snapshot = current

        for fact in changed:
            self._fire(fact)

        return changed

    def snapshot(self) -> dict[str, WorldFact]:
        """Return current fact snapshot (entity::attribute -> fact)."""
        return dict(self._last_snapshot)

    def _take_snapshot(self) -> dict[str, WorldFact]:
        facts = self._store.list_facts()
        return {f"{f.entity}::{f.attribute}": f for f in facts}

    def _fire(self, fact: WorldFact) -> None:
        for entity_filter, attr_filter, callback in self._callbacks:
            entity_match = entity_filter is None or entity_filter == fact.entity
            attr_match = attr_filter is None or attr_filter == fact.attribute
            if entity_match and attr_match:
                callback(fact)
