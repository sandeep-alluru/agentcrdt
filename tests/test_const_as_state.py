"""CONST-AS-STATE — refuse constant/recipe domains as CRDT world state.

Farm: POLYMATTER_RECIPE cached as multi-writer CRDT (silent LWW of constants).
Public: multi-agent coordination (FedCritic / History Matters) needs real
shared *world* state, not code constants.
"""

from __future__ import annotations

import pytest

from agentcrdt.closed_loop import (
    ClosedLoopError,
    assert_mutable_write,
    assert_world_state_ok,
    gate_world_state,
    is_constant_domain,
    refuse_constant_write,
    set_fact_if_mutable,
)
from agentcrdt.fact import WorldFact
from agentcrdt.store import WorldStore


def _mutable(**kw: object) -> WorldFact:
    defaults: dict = {
        "domain": "life",
        "entity": "king",
        "attribute": "alive",
        "value": True,
        "agent_id": "a1",
    }
    defaults.update(kw)
    return WorldFact(**defaults)  # type: ignore[arg-type]


def _recipe(**kw: object) -> WorldFact:
    defaults: dict = {
        "domain": "polymatter_recipe",
        "entity": "ep5",
        "attribute": "mix",
        "value": {"ratio": 0.3},
        "agent_id": "pipeline",
    }
    defaults.update(kw)
    return WorldFact(**defaults)  # type: ignore[arg-type]


def test_constant_domains_detected() -> None:
    assert is_constant_domain("polymatter_recipe") is True
    assert is_constant_domain("recipe") is True
    assert is_constant_domain("constant") is True
    assert is_constant_domain("config") is True
    assert is_constant_domain("life") is False
    assert is_constant_domain("alliance") is False
    assert is_constant_domain("") is True
    assert is_constant_domain("recipe_v2") is True


def test_refuse_polymatter_recipe_write() -> None:
    out = refuse_constant_write(_recipe())
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.exit_code == 1
    assert out.refused_writes == 1
    assert "CONST-AS-STATE" in out.reason
    assert "polymatter_recipe" in out.constant_domains


def test_allow_life_domain_write() -> None:
    out = refuse_constant_write(_mutable())
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.mutable_count == 1


def test_set_fact_if_mutable_writes_only_allowed(tmp_path: object) -> None:
    from pathlib import Path

    db = Path(tmp_path) / "w.db"  # type: ignore[arg-type]
    store = WorldStore(db)
    try:
        ok = set_fact_if_mutable(store, _mutable(entity="queen"))
        assert ok.ok is True
        denied = set_fact_if_mutable(store, _recipe())
        assert denied.ok is False
        facts = store.list_facts()
        assert len(facts) == 1
        assert facts[0].domain == "life"
    finally:
        store.close()


def test_gate_empty_fails_loud(tmp_path: object) -> None:
    from pathlib import Path

    store = WorldStore(Path(tmp_path) / "e.db")  # type: ignore[arg-type]
    try:
        out = gate_world_state(store)
        assert out.verdict == "FAIL_LOUD"
        assert out.exit_code == 2
    finally:
        store.close()


def test_gate_constant_only_fails() -> None:
    facts = [_recipe(), _recipe(entity="ep6", domain="recipe")]
    out = gate_world_state(facts)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.mutable_count == 0
    assert out.constant_count == 2
    assert "constant-only" in out.reason.lower() or "CONST-AS-STATE" in out.reason


def test_gate_mutable_only_passes() -> None:
    facts = [
        _mutable(),
        _mutable(entity="knight", attribute="alive", value=False),
    ]
    out = gate_world_state(facts)
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.mutable_count == 2
    assert out.constant_count == 0


def test_gate_mixed_fails_by_default() -> None:
    facts = [_mutable(), _recipe()]
    out = gate_world_state(facts)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.mutable_count == 1
    assert out.constant_count == 1


def test_gate_mixed_allowed_when_flag_set() -> None:
    facts = [_mutable(), _recipe()]
    out = gate_world_state(facts, allow_mixed=True)
    assert out.ok is True
    assert out.constant_count == 1


def test_assert_world_state_raises() -> None:
    with pytest.raises(ClosedLoopError, match="CONST-AS-STATE|FAIL"):
        assert_world_state_ok([_recipe()])


def test_assert_mutable_write_raises() -> None:
    with pytest.raises(ClosedLoopError, match="CONST-AS-STATE|FAIL"):
        assert_mutable_write(_recipe(domain="config"))


def test_extra_constant_domain() -> None:
    f = _mutable(domain="house_style")
    out = refuse_constant_write(f, extra_constant_domains=["house_style"])
    assert out.ok is False
    assert "house_style" in out.constant_domains


def test_to_dict_fields() -> None:
    payload = gate_world_state([_recipe()]).to_dict()
    assert payload["ok"] is False
    assert payload["constant_count"] >= 1
    assert isinstance(payload["constant_domains"], list)
