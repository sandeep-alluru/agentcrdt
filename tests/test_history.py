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
    assert v.version_index == 0
    store.close()
