"""COVERT-COLLUSION — black-box multi-agent coordination (arXiv 2608.02698)."""

from __future__ import annotations

import pytest

from agentcrdt.closed_loop import ClosedLoopError
from agentcrdt.collusion import (
    AgentTraceEvent,
    assert_no_covert_collusion,
    detect_covert_collusion,
    gate_covert_collusion,
)


def test_empty_fails_loud() -> None:
    out = gate_covert_collusion([])
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"


def test_single_agent_fails_loud() -> None:
    events = [
        AgentTraceEvent("a1", "search", 1.0, payload_fp="x"),
        AgentTraceEvent("a1", "search", 2.0, payload_fp="y"),
    ]
    out = gate_covert_collusion(events, min_agents=2)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"


def test_independent_agents_pass() -> None:
    events = [
        AgentTraceEvent("a", "search", 10.0, payload_fp="pa"),
        AgentTraceEvent("b", "fetch", 50.0, payload_fp="pb"),
        AgentTraceEvent("c", "write", 90.0, payload_fp="pc"),
    ]
    out = gate_covert_collusion(events)
    assert out.ok is True
    assert out.verdict == "PASS"


def test_shared_payload_fails() -> None:
    events = [
        AgentTraceEvent("a", "bid", 1.0, payload_fp="SECRETCODE99"),
        AgentTraceEvent("b", "bid", 5.0, payload_fp="SECRETCODE99"),
        AgentTraceEvent("c", "bid", 9.0, payload_fp="SECRETCODE99"),
    ]
    out = gate_covert_collusion(events)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "shared_payload" in out.reason or "COVERT" in out.reason


def test_side_channel_fails() -> None:
    events = [
        AgentTraceEvent("a", "review", 1.0, side_channel="boost-me"),
        AgentTraceEvent("b", "review", 2.0, side_channel="boost-me"),
    ]
    out = gate_covert_collusion(events)
    assert out.ok is False
    assert "side_channel" in out.reason or "COVERT" in out.reason


def test_sync_timing_fails() -> None:
    # Two agents fire same tool in tight window twice
    events = [
        AgentTraceEvent("a", "grab", 100.0),
        AgentTraceEvent("b", "grab", 100.2),
        AgentTraceEvent("a", "grab", 200.0),
        AgentTraceEvent("b", "grab", 200.3),
    ]
    out = gate_covert_collusion(events, sync_window=1.0)
    assert out.ok is False
    assert out.verdict == "FAIL"


def test_detect_report() -> None:
    r = detect_covert_collusion(
        [
            {"agent_id": "x", "tool": "t", "ts": 1, "payload_fp": "Z"},
            {"agent_id": "y", "tool": "t", "ts": 2, "payload_fp": "Z"},
        ]
    )
    assert r.has_collusion is True
    assert r.shared_payload_groups >= 1
    assert r.to_dict()["agent_count"] == 2


def test_assert_raises() -> None:
    with pytest.raises(ClosedLoopError):
        assert_no_covert_collusion([])


def test_arxiv_collusion_fixture() -> None:
    """End-to-end: quiet coordination via shared rare payload + timing."""
    # Pre-fix class: agents look fine individually but share stego payload
    collude = [
        AgentTraceEvent("agent-1", "market_bid", 1000.0, payload_fp="stego-0xDEAD"),
        AgentTraceEvent("agent-2", "market_bid", 1000.4, payload_fp="stego-0xDEAD"),
        AgentTraceEvent("agent-3", "market_bid", 1001.0, payload_fp="stego-0xDEAD"),
        AgentTraceEvent("agent-1", "market_bid", 2000.0, payload_fp="stego-0xDEAD"),
        AgentTraceEvent("agent-2", "market_bid", 2000.5, payload_fp="stego-0xDEAD"),
    ]
    refuse = gate_covert_collusion(collude)
    assert refuse.ok is False
    assert refuse.human_required is True
    assert "2608.02698" in refuse.reason or "COVERT" in refuse.reason

    # Independent agents with diverse payloads/tools
    clean = [
        AgentTraceEvent("agent-1", "search", 1.0, payload_fp="q1"),
        AgentTraceEvent("agent-2", "summarize", 100.0, payload_fp="s2"),
        AgentTraceEvent("agent-3", "write", 200.0, payload_fp="w3"),
    ]
    ok = gate_covert_collusion(clean)
    assert ok.ok is True
