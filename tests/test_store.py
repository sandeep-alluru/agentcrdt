"""Tests for WorldStore SQLite persistence."""
from __future__ import annotations

from pathlib import Path

import pytest

from agentcrdt.fact import ContradictionEvent, WorldFact
from agentcrdt.store import WorldStore


@pytest.fixture
def store(tmp_path: Path) -> WorldStore:
    """Fresh WorldStore in a temp dir."""
    s = WorldStore(tmp_path / "test.db")
    yield s
    s.close()


def _make_fact(
    domain: str = "life",
    entity: str = "king",
    attribute: str = "alive",
    value: object = True,
    version: int = 0,
    agent_id: str = "",
    timestamp: float | None = None,
) -> WorldFact:
    f = WorldFact(domain=domain, entity=entity, attribute=attribute, value=value,
                  version=version, agent_id=agent_id)
    if timestamp is not None:
        f.timestamp = timestamp
    return f


class TestWorldStoreCreation:
    """Tests for store creation and file system behaviour."""

    def test_creates_sqlite_file(self, tmp_path: Path) -> None:
        """WorldStore must create the database file at the given path."""
        db_path = tmp_path / "world.db"
        assert not db_path.exists()
        with WorldStore(db_path):
            assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """WorldStore must create missing parent directories."""
        db_path = tmp_path / "nested" / "deep" / "world.db"
        with WorldStore(db_path):
            assert db_path.exists()

    def test_context_manager(self, tmp_path: Path) -> None:
        """WorldStore must work as a context manager."""
        with WorldStore(tmp_path / "ctx.db") as store:
            fact = _make_fact()
            store.set_fact(fact)
            assert store.get_fact(fact.id) is not None


class TestSetAndGetFact:
    """Tests for set_fact and get_fact."""

    def test_set_and_retrieve_fact(self, store: WorldStore) -> None:
        """A fact stored with set_fact must be retrievable by its id."""
        fact = _make_fact(value=True)
        store.set_fact(fact)
        retrieved = store.get_fact(fact.id)
        assert retrieved is not None
        assert retrieved.id == fact.id
        assert retrieved.value is True

    def test_get_nonexistent_returns_none(self, store: WorldStore) -> None:
        """get_fact must return None for an unknown id."""
        assert store.get_fact("nonexistent-id") is None

    def test_boolean_value_preserved(self, store: WorldStore) -> None:
        """Boolean values must round-trip through JSON storage correctly."""
        fact = _make_fact(value=False)
        store.set_fact(fact)
        retrieved = store.get_fact(fact.id)
        assert retrieved is not None
        assert retrieved.value is False

    def test_none_value_preserved(self, store: WorldStore) -> None:
        """None values must survive JSON serialisation."""
        fact = _make_fact(value=None)
        store.set_fact(fact)
        retrieved = store.get_fact(fact.id)
        assert retrieved is not None
        assert retrieved.value is None

    def test_string_value_preserved(self, store: WorldStore) -> None:
        """String values must be preserved as strings."""
        fact = _make_fact(value="active")
        store.set_fact(fact)
        retrieved = store.get_fact(fact.id)
        assert retrieved is not None
        assert retrieved.value == "active"

    def test_float_value_preserved(self, store: WorldStore) -> None:
        """Float values must be preserved."""
        fact = _make_fact(value=3.14)
        store.set_fact(fact)
        retrieved = store.get_fact(fact.id)
        assert retrieved is not None
        assert retrieved.value == pytest.approx(3.14)


class TestLWWSemantics:
    """Tests for Last-Write-Wins CRDT semantics."""

    def test_higher_version_wins(self, store: WorldStore) -> None:
        """A fact with a higher version must overwrite one with a lower version."""
        fact_v0 = _make_fact(value=True, version=0, timestamp=1000.0)
        fact_v1 = _make_fact(value=False, version=1, timestamp=999.0)  # older ts but higher v
        store.set_fact(fact_v0)
        store.set_fact(fact_v1)
        retrieved = store.get_fact(fact_v0.id)
        assert retrieved is not None
        assert retrieved.value is False
        assert retrieved.version == 1

    def test_lower_version_is_ignored(self, store: WorldStore) -> None:
        """A fact with a lower version must not overwrite a higher-version fact."""
        fact_v2 = _make_fact(value=False, version=2)
        fact_v1 = _make_fact(value=True, version=1)
        store.set_fact(fact_v2)
        store.set_fact(fact_v1)  # should be rejected
        retrieved = store.get_fact(fact_v2.id)
        assert retrieved is not None
        assert retrieved.value is False
        assert retrieved.version == 2

    def test_same_version_higher_timestamp_wins(self, store: WorldStore) -> None:
        """On version tie, the fact with the higher timestamp wins."""
        fact_old = _make_fact(value="old", version=1, timestamp=1000.0)
        fact_new = _make_fact(value="new", version=1, timestamp=2000.0)
        store.set_fact(fact_old)
        store.set_fact(fact_new)
        retrieved = store.get_fact(fact_old.id)
        assert retrieved is not None
        assert retrieved.value == "new"

    def test_same_version_lower_timestamp_is_rejected(self, store: WorldStore) -> None:
        """On version tie, a fact with a lower/equal timestamp is rejected."""
        fact_new = _make_fact(value="new", version=1, timestamp=2000.0)
        fact_old = _make_fact(value="old", version=1, timestamp=1000.0)
        store.set_fact(fact_new)
        store.set_fact(fact_old)  # should be rejected
        retrieved = store.get_fact(fact_new.id)
        assert retrieved is not None
        assert retrieved.value == "new"

    def test_same_version_same_timestamp_not_overwritten(self, store: WorldStore) -> None:
        """On exact tie (same version and timestamp), the existing value is kept."""
        fact = _make_fact(value="first", version=1, timestamp=1000.0)
        fact2 = _make_fact(value="second", version=1, timestamp=1000.0)
        store.set_fact(fact)
        store.set_fact(fact2)
        retrieved = store.get_fact(fact.id)
        assert retrieved is not None
        assert retrieved.value == "first"


class TestListFacts:
    """Tests for list_facts."""

    def test_empty_store_returns_empty_list(self, store: WorldStore) -> None:
        """An empty store must return an empty list."""
        assert store.list_facts() == []

    def test_list_all_facts(self, store: WorldStore) -> None:
        """list_facts() must return all stored facts."""
        f1 = _make_fact(domain="life", entity="king", attribute="alive", value=True)
        f2 = _make_fact(domain="possession", entity="sword", attribute="owner", value="knight")
        store.set_fact(f1)
        store.set_fact(f2)
        facts = store.list_facts()
        assert len(facts) == 2
        ids = {f.id for f in facts}
        assert f1.id in ids
        assert f2.id in ids

    def test_domain_filter(self, store: WorldStore) -> None:
        """list_facts(domain=...) must only return facts in that domain."""
        f_life = _make_fact(domain="life", entity="king", attribute="alive", value=True)
        f_poss = _make_fact(domain="possession", entity="sword", attribute="owner", value="knight")
        store.set_fact(f_life)
        store.set_fact(f_poss)
        life_facts = store.list_facts(domain="life")
        assert len(life_facts) == 1
        assert life_facts[0].domain == "life"

    def test_domain_filter_no_match(self, store: WorldStore) -> None:
        """list_facts with an unknown domain must return an empty list."""
        fact = _make_fact()
        store.set_fact(fact)
        assert store.list_facts(domain="nonexistent") == []


class TestEvents:
    """Tests for ContradictionEvent persistence."""

    def test_add_and_list_events(self, store: WorldStore) -> None:
        """An event stored with add_event must appear in list_events."""
        evt = ContradictionEvent(
            rule="test-rule",
            facts_involved=["fact1", "fact2"],
            agent_a="agent-1",
            agent_b="agent-2",
        )
        store.add_event(evt)
        events = store.list_events()
        assert len(events) == 1
        assert events[0].rule == "test-rule"
        assert set(events[0].facts_involved) == {"fact1", "fact2"}

    def test_empty_events_list(self, store: WorldStore) -> None:
        """list_events on an empty store must return an empty list."""
        assert store.list_events() == []

    def test_duplicate_event_deduped(self, store: WorldStore) -> None:
        """Adding the same event twice must not create duplicates."""
        evt = ContradictionEvent(
            rule="test-rule",
            facts_involved=["f1"],
            agent_a="a",
            agent_b="b",
            timestamp=1000.0,
        )
        store.add_event(evt)
        store.add_event(evt)
        assert len(store.list_events()) == 1
