"""Tests for agentcrdt.history module."""
import time

import pytest

from agentcrdt.fact import WorldFact
from agentcrdt.history import FactHistory, FactVersion
from agentcrdt.store import WorldStore


def _store(tmp_path) -> WorldStore:
    return WorldStore(tmp_path / "test.db")


def test_get_history_empty(tmp_path):
    store = _store(tmp_path)
    history = FactHistory(store)
    versions = history.get_history("king", "alive")
    assert versions == []
    store.close()


def test_get_history_single_version(tmp_path):
    store = _store(tmp_path)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    store.set_fact(f)
    history = FactHistory(store)
    versions = history.get_history("king", "alive")
    assert len(versions) == 1
    assert versions[0].fact.value is True
    # Single version has no superseding fact
    assert versions[0].superseded_by is None
    store.close()


def test_get_history_multiple_versions(tmp_path):
    store = _store(tmp_path)
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, timestamp=1.0)
    f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False, version=2, timestamp=2.0)
    store.set_fact(f1)
    store.set_fact(f2)
    history = FactHistory(store)
    versions = history.get_history("king", "alive")
    # Should have 2 history entries
    assert len(versions) == 2
    store.close()


def test_get_history_superseded_by_direction(tmp_path):
    """superseded_by must point to the NEWER fact (the one that replaced it)."""
    store = _store(tmp_path)
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, timestamp=1.0)
    f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False, version=2, timestamp=2.0)
    store.set_fact(f1)
    store.set_fact(f2)
    history = FactHistory(store)
    # get_history returns newest-first
    versions = history.get_history("king", "alive")
    assert len(versions) == 2
    # versions[0] is the newest (version=2) — it was NOT superseded
    newest = versions[0]
    oldest = versions[1]
    assert newest.superseded_by is None
    # oldest (version=1) WAS superseded by the newer fact (superseded_by is not None)
    assert oldest.superseded_by is not None
    store.close()


def test_get_history_version_index(tmp_path):
    """version_index: 0 = oldest, len-1 = newest."""
    store = _store(tmp_path)
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, timestamp=1.0)
    f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False, version=2, timestamp=2.0)
    f3 = WorldFact(domain="life", entity="king", attribute="alive", value=None, version=3, timestamp=3.0)
    store.set_fact(f1)
    store.set_fact(f2)
    store.set_fact(f3)
    history = FactHistory(store)
    # Returns newest-first
    versions = history.get_history("king", "alive")
    assert len(versions) == 3
    # Newest (version=3) should have version_index = 2 (len-1)
    assert versions[0].version_index == 2
    # Middle (version=2) should have version_index = 1
    assert versions[1].version_index == 1
    # Oldest (version=1) should have version_index = 0
    assert versions[2].version_index == 0
    store.close()


def test_get_at_time(tmp_path):
    store = _store(tmp_path)
    t_base = time.time()
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, timestamp=t_base)
    store.set_fact(f1)
    time.sleep(0.05)
    f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False, version=2, timestamp=t_base + 1.0)
    store.set_fact(f2)

    history = FactHistory(store)
    # Query at a time between the two inserts
    mid_time = time.time()
    fact_at_mid = history.get_at_time("king", "alive", mid_time)
    assert fact_at_mid is not None
    store.close()


def test_get_at_time_before_any(tmp_path):
    store = _store(tmp_path)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, timestamp=100.0)
    store.set_fact(f)
    history = FactHistory(store)
    fact = history.get_at_time("king", "alive", 0.0)
    assert fact is None
    store.close()


def test_diff_entity(tmp_path):
    store = _store(tmp_path)
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    f2 = WorldFact(domain="possession", entity="king", attribute="crown", value="gold", version=1)
    store.set_fact(f1)
    store.set_fact(f2)
    history = FactHistory(store)
    diff = history.diff_entity("king")
    assert "alive" in diff
    assert "crown" in diff
    store.close()


def test_fact_version_dataclass(tmp_path):
    store = _store(tmp_path)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    store.set_fact(f)
    history = FactHistory(store)
    versions = history.get_history("king", "alive")
    v = versions[0]
    assert isinstance(v, FactVersion)
    # Single version: version_index = 0 (oldest = newest = 0)
    assert v.version_index == 0
    store.close()
