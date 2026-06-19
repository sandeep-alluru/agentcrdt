"""Tests for agentcrdt.watch module."""
import time

import pytest

from agentcrdt.fact import WorldFact
from agentcrdt.store import WorldStore
from agentcrdt.watch import ChangeWatcher


def _store(tmp_path) -> WorldStore:
    return WorldStore(tmp_path / "test.db")


def test_check_empty_store(tmp_path):
    store = _store(tmp_path)
    watcher = ChangeWatcher(store)
    changed = watcher.check()
    assert changed == []
    store.close()


def test_check_detects_new_fact(tmp_path):
    store = _store(tmp_path)
    watcher = ChangeWatcher(store)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    store.set_fact(f)
    changed = watcher.check()
    assert len(changed) == 1
    assert changed[0].entity == "king"
    store.close()


def test_check_no_duplicate_on_second_call(tmp_path):
    store = _store(tmp_path)
    watcher = ChangeWatcher(store)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    store.set_fact(f)
    watcher.check()  # consume the change
    changed = watcher.check()  # no new changes
    assert changed == []
    store.close()


def test_check_detects_update(tmp_path):
    store = _store(tmp_path)
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1, timestamp=1.0)
    store.set_fact(f1)
    watcher = ChangeWatcher(store)
    f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False, version=2, timestamp=2.0)
    store.set_fact(f2)
    changed = watcher.check()
    assert len(changed) == 1
    assert changed[0].value is False
    store.close()


def test_on_change_callback_fires(tmp_path):
    store = _store(tmp_path)
    watcher = ChangeWatcher(store)
    fired = []

    @watcher.on_change(entity="king")
    def handler(fact: WorldFact) -> None:
        fired.append(fact)

    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    store.set_fact(f)
    watcher.check()
    assert len(fired) == 1
    store.close()


def test_on_change_callback_filters_entity(tmp_path):
    store = _store(tmp_path)
    watcher = ChangeWatcher(store)
    fired = []

    @watcher.on_change(entity="queen")
    def handler(fact: WorldFact) -> None:
        fired.append(fact)

    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    store.set_fact(f)
    watcher.check()
    assert fired == []
    store.close()


def test_on_change_wildcard_entity(tmp_path):
    store = _store(tmp_path)
    watcher = ChangeWatcher(store)
    fired = []

    @watcher.on_change()  # wildcard
    def handler(fact: WorldFact) -> None:
        fired.append(fact)

    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    f2 = WorldFact(domain="life", entity="queen", attribute="alive", value=True, version=1)
    store.set_fact(f1)
    store.set_fact(f2)
    watcher.check()
    assert len(fired) == 2
    store.close()


def test_snapshot(tmp_path):
    store = _store(tmp_path)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True, version=1)
    store.set_fact(f)
    watcher = ChangeWatcher(store)
    snap = watcher.snapshot()
    assert "king::alive" in snap
    store.close()
