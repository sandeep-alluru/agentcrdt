"""MAST multi-agent silent divergence + merge conflict gates.

Public cases (Track B research 20260807T041224Z):
  * What ICLR 2026 Taught Us About Multi-Agent Failures
  * AdaMAST adaptive failure taxonomies
  * AgentPulse multi-agent failure detection
  * Matrix: MAST multi-agent failures was **no** until this ship

Pre-fix hole: LWW merge keeps one value when two agents disagree; no
ContradictionEvent → consumers treat contested state as single truth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentcrdt.closed_loop import (
    ClosedLoopError,
    assert_multi_agent_ok,
    detect_silent_divergences,
    gate_merge_result,
    gate_multi_agent,
)
from agentcrdt.fact import ContradictionEvent, WorldFact
from agentcrdt.merger import MergeResult, WorldMerger
from agentcrdt.store import WorldStore


def _fact(
    domain: str,
    entity: str,
    attribute: str,
    value: object,
    *,
    agent: str,
    version: int = 1,
    ts: float = 1.0,
) -> WorldFact:
    return WorldFact(
        domain=domain,
        entity=entity,
        attribute=attribute,
        value=value,
        version=version,
        agent_id=agent,
        timestamp=ts,
    )


def test_empty_store_fails_loud(tmp_path: Path) -> None:
    store = WorldStore(tmp_path / "empty.db")
    try:
        out = gate_multi_agent(store)
        assert out.ok is False
        assert out.verdict == "FAIL_LOUD"
        assert out.human_required is True
    finally:
        store.close()


def test_agreed_agents_pass(tmp_path: Path) -> None:
    store = WorldStore(tmp_path / "ok.db")
    try:
        store.set_fact(_fact("life", "king", "alive", True, agent="a1", version=1, ts=1.0))
        store.set_fact(_fact("life", "king", "alive", True, agent="a2", version=2, ts=2.0))
        out = gate_multi_agent(store)
        assert out.ok is True
        assert out.verdict == "PASS"
        assert out.divergence_count == 0
    finally:
        store.close()


def test_silent_divergence_two_agents_fails(tmp_path: Path) -> None:
    """Agent A says alive=True, agent B says alive=False - LWW no event."""
    store = WorldStore(tmp_path / "div.db")
    try:
        store.set_fact(_fact("life", "king", "alive", True, agent="alice", version=1, ts=1.0))
        store.set_fact(_fact("life", "king", "alive", False, agent="bob", version=2, ts=2.0))
        divs = detect_silent_divergences(store)
        assert len(divs) == 1
        assert "alice" in divs[0].agents
        assert "bob" in divs[0].agents
        assert divs[0].key == "life.king.alive"

        out = gate_multi_agent(store)
        assert out.ok is False
        assert out.verdict == "FAIL"
        assert out.exit_code == 1
        assert out.human_required is True
        assert out.divergence_count == 1
        assert "life.king.alive" in out.contested_keys
        assert "MAST" in out.reason or "silent" in out.reason.lower()
        payload = out.to_dict()
        assert payload["divergence_count"] == 1
    finally:
        store.close()


def test_divergence_covered_by_event_passes(tmp_path: Path) -> None:
    """If ContradictionEvent records the conflict, not 'silent'."""
    store = WorldStore(tmp_path / "evt.db")
    try:
        f1 = _fact("life", "king", "alive", True, agent="alice", version=1, ts=1.0)
        f2 = _fact("life", "king", "alive", False, agent="bob", version=2, ts=2.0)
        store.set_fact(f1)
        store.set_fact(f2)
        store.add_event(
            ContradictionEvent(
                rule="life.unique",
                facts_involved=[f1.id],
                agent_a="alice",
                agent_b="bob",
                timestamp=3.0,
            )
        )
        # Silent detector skips covered fact_ids
        assert detect_silent_divergences(store) == []
        # But unresolved events still fail gate (max=0)
        out = gate_multi_agent(store, max_unresolved_events=0)
        assert out.ok is False
        assert out.conflict_count == 1
        assert out.human_required is True

        out_ok = gate_multi_agent(store, max_unresolved_events=1)
        assert out_ok.ok is True
    finally:
        store.close()


def test_single_agent_versioning_not_divergence(tmp_path: Path) -> None:
    store = WorldStore(tmp_path / "solo.db")
    try:
        store.set_fact(_fact("status", "task", "state", "open", agent="solo", version=1, ts=1.0))
        store.set_fact(_fact("status", "task", "state", "done", agent="solo", version=2, ts=2.0))
        assert detect_silent_divergences(store) == []
        out = gate_multi_agent(store)
        assert out.ok is True
    finally:
        store.close()


def test_gate_merge_result_conflicts() -> None:
    clean = MergeResult(merged_count=3, conflicts=[])
    assert gate_merge_result(clean).ok is True

    bad = MergeResult(
        merged_count=2,
        conflicts=[
            ContradictionEvent(
                rule="r",
                facts_involved=["a"],
                agent_a="x",
                agent_b="y",
                timestamp=1.0,
            )
        ],
    )
    out = gate_merge_result(bad, max_conflicts=0)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.conflict_count == 1
    assert out.human_required is True


def test_gate_merge_result_empty_fails_loud() -> None:
    out = gate_merge_result(MergeResult(merged_count=0), min_merged=1)
    assert out.verdict == "FAIL_LOUD"


def test_assert_multi_agent_ok_raises(tmp_path: Path) -> None:
    store = WorldStore(tmp_path / "raise.db")
    try:
        store.set_fact(_fact("life", "queen", "alive", True, agent="a", version=1, ts=1.0))
        store.set_fact(_fact("life", "queen", "alive", False, agent="b", version=2, ts=2.0))
        with pytest.raises(ClosedLoopError) as ei:
            assert_multi_agent_ok(store)
        assert "MAST" in str(ei.value) or "FAIL" in str(ei.value)
    finally:
        store.close()


def test_e2e_merge_then_gate(tmp_path: Path) -> None:
    """Two stores diverge; merge LWW; gate_multi_agent catches silent conflict."""
    local = WorldStore(tmp_path / "local.db")
    remote = WorldStore(tmp_path / "remote.db")
    try:
        local.set_fact(
            _fact("alliance", "t1", "valid", True, agent="agent-local", version=1, ts=1.0)
        )
        remote.set_fact(
            _fact("alliance", "t1", "valid", False, agent="agent-remote", version=2, ts=2.0)
        )
        result = WorldMerger().merge(local, remote)
        assert result.merged_count >= 1
        # WorldMerger without RuleEngine records no ContradictionEvents
        out = gate_multi_agent(local)
        assert out.ok is False
        assert out.divergence_count >= 1
    finally:
        local.close()
        remote.close()
