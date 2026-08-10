"""COVERT-COLLUSION — black-box multi-agent coordination (arXiv 2608.02698).

Public case: *Steganalysis of Adaptive Covert Collusion in Tool-Using Agent
Populations*. Side-by-side agents on shared infrastructure can quietly
coordinate (market rig, mutual review boost, joint data grab) while each
trace looks well-behaved. Detectors must be black-box, trace-only.

Product role in agentcrdt (MAST-MULTI twin):
  Gate multi-agent **behavioural** collusion signals that do not surface as
  value divergences: shared rare payload fingerprints, synchronized tool
  timing, and identical side-channel codes across agents.

Non-Ornament:
  Call ``gate_covert_collusion`` on multi-agent tool/event traces before
  treating independent agents as independent. Pair with ``gate_multi_agent``.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from agentcrdt.closed_loop import ClosedLoopError, GateOutcome


@dataclass(frozen=True)
class AgentTraceEvent:
    """One black-box behavioural event from an agent (tool/timing/payload)."""

    agent_id: str
    tool: str
    timestamp: float
    payload_fp: str = ""
    side_channel: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "tool": self.tool,
            "timestamp": self.timestamp,
            "payload_fp": self.payload_fp,
            "side_channel": self.side_channel,
            "meta": dict(self.meta),
        }


@dataclass(frozen=True)
class CollusionSignal:
    """One detected collusion pattern."""

    kind: str  # shared_payload | sync_timing | side_channel_code
    agents: tuple[str, ...]
    detail: str
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "agents": list(self.agents),
            "detail": self.detail,
            "score": self.score,
        }


@dataclass(frozen=True)
class CollusionReport:
    """Aggregate collusion analysis over a population of agent events."""

    event_count: int
    agent_count: int
    signals: tuple[CollusionSignal, ...]
    shared_payload_groups: int
    sync_pairs: int
    side_channel_groups: int

    @property
    def collusion_score(self) -> float:
        if not self.signals:
            return 0.0
        return min(1.0, sum(s.score for s in self.signals) / max(len(self.signals), 1))

    @property
    def has_collusion(self) -> bool:
        return bool(self.signals)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "agent_count": self.agent_count,
            "signals": [s.to_dict() for s in self.signals],
            "shared_payload_groups": self.shared_payload_groups,
            "sync_pairs": self.sync_pairs,
            "side_channel_groups": self.side_channel_groups,
            "collusion_score": self.collusion_score,
            "has_collusion": self.has_collusion,
        }


def _as_event(item: AgentTraceEvent | dict[str, Any], index: int = 0) -> AgentTraceEvent:
    if isinstance(item, AgentTraceEvent):
        return item
    if not isinstance(item, dict):
        raise TypeError(f"event must be AgentTraceEvent or dict, got {type(item)!r}")
    aid = str(item.get("agent_id") or item.get("agent") or f"agent_{index}").strip()
    tool = str(item.get("tool") or item.get("name") or item.get("action") or "").strip()
    if not tool:
        raise ValueError(f"event for {aid!r} missing tool")
    ts = item.get("timestamp", item.get("ts", item.get("t")))
    if ts is None:
        raise ValueError(f"event for {aid!r} missing timestamp")
    fp = str(item.get("payload_fp") or item.get("fingerprint") or item.get("payload") or "")
    side = str(item.get("side_channel") or item.get("code") or item.get("channel") or "")
    raw_meta = item.get("meta")
    meta: dict[str, Any] = dict(raw_meta) if isinstance(raw_meta, dict) else {}
    return AgentTraceEvent(
        agent_id=aid,
        tool=tool,
        timestamp=float(ts),
        payload_fp=fp,
        side_channel=side,
        meta=meta,
    )


def detect_covert_collusion(
    events: Sequence[AgentTraceEvent | dict[str, Any]],
    *,
    sync_window: float = 1.0,
    min_agents_shared_payload: int = 2,
    min_payload_rarity: int = 3,
    min_side_channel_agents: int = 2,
) -> CollusionReport:
    """Black-box collusion detector over tool/timing/payload traces.

    Signals (paper-inspired, behavioural only):

    1. **shared_payload** — same non-empty ``payload_fp`` appears for
       ≥ ``min_agents_shared_payload`` distinct agents, and the fingerprint
       is rare overall (count of events with that fp ≤ population / rarity).
    2. **sync_timing** — two agents fire the same tool within ``sync_window``
       seconds more than once (pair-level).
    3. **side_channel_code** — identical non-empty ``side_channel`` token used
       by ≥ ``min_side_channel_agents`` agents.
    """
    parsed = [_as_event(e, i) for i, e in enumerate(events)]
    agents = {e.agent_id for e in parsed}
    signals: list[CollusionSignal] = []

    # 1) shared rare payloads
    by_fp: dict[str, set[str]] = defaultdict(set)
    fp_counts: dict[str, int] = defaultdict(int)
    for e in parsed:
        if not e.payload_fp:
            continue
        by_fp[e.payload_fp].add(e.agent_id)
        fp_counts[e.payload_fp] += 1
    shared_groups = 0
    n = max(len(parsed), 1)
    for fp, agent_set in by_fp.items():
        if len(agent_set) < min_agents_shared_payload:
            continue
        # rare: appears in fewer than n/min_payload_rarity events, or absolute small
        if (
            fp_counts[fp] > max(min_payload_rarity, n // max(min_payload_rarity, 1))
            and fp_counts[fp] > len(agents) * 2
        ):
            # common payload — skip (not covert)
            continue
        shared_groups += 1
        signals.append(
            CollusionSignal(
                kind="shared_payload",
                agents=tuple(sorted(agent_set)),
                detail=f"payload_fp={fp[:48]} agents={len(agent_set)} count={fp_counts[fp]}",
                score=min(1.0, len(agent_set) / max(len(agents), 1)),
            )
        )

    # 2) sync timing same tool
    by_tool: dict[str, list[AgentTraceEvent]] = defaultdict(list)
    for e in parsed:
        by_tool[e.tool].append(e)
    sync_pairs = 0
    seen_pairs: set[tuple[str, str, str]] = set()
    for tool, evs in by_tool.items():
        ordered = sorted(evs, key=lambda x: x.timestamp)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                if b.timestamp - a.timestamp > sync_window:
                    break
                if a.agent_id == b.agent_id:
                    continue
                pair = (*tuple(sorted((a.agent_id, b.agent_id))), tool)
                key = (pair[0], pair[1], tool)
                if key in seen_pairs:
                    continue
                # require at least 2 sync hits for this pair+tool to reduce noise
                hits = 0
                for x in ordered:
                    for y in ordered:
                        if (
                            x.agent_id == pair[0]
                            and y.agent_id == pair[1]
                            and abs(x.timestamp - y.timestamp) <= sync_window
                        ):
                            hits += 1
                if hits < 2:
                    continue
                seen_pairs.add(key)
                sync_pairs += 1
                signals.append(
                    CollusionSignal(
                        kind="sync_timing",
                        agents=(pair[0], pair[1]),
                        detail=f"tool={tool} window={sync_window}s hits~={hits}",
                        score=min(1.0, hits / 4.0),
                    )
                )

    # 3) side channel codes
    by_side: dict[str, set[str]] = defaultdict(set)
    for e in parsed:
        if not e.side_channel:
            continue
        by_side[e.side_channel].add(e.agent_id)
    side_groups = 0
    for code, agent_set in by_side.items():
        if len(agent_set) < min_side_channel_agents:
            continue
        side_groups += 1
        signals.append(
            CollusionSignal(
                kind="side_channel_code",
                agents=tuple(sorted(agent_set)),
                detail=f"code={code[:48]} agents={len(agent_set)}",
                score=min(1.0, len(agent_set) / max(len(agents), 1)),
            )
        )

    return CollusionReport(
        event_count=len(parsed),
        agent_count=len(agents),
        signals=tuple(signals),
        shared_payload_groups=shared_groups,
        sync_pairs=sync_pairs,
        side_channel_groups=side_groups,
    )


def gate_covert_collusion(
    events: Sequence[AgentTraceEvent | dict[str, Any]] | None,
    *,
    require_events: bool = True,
    min_agents: int = 2,
    max_signals: int = 0,
    sync_window: float = 1.0,
    refuse_shared_payload: bool = True,
    refuse_sync_timing: bool = True,
    refuse_side_channel: bool = True,
) -> GateOutcome:
    """Refuse multi-agent populations with covert collusion signals.

    Rules:

    * No events when required → **FAIL_LOUD**
    * Fewer than ``min_agents`` → **FAIL_LOUD** (need a population)
    * Any signal kind over budget (default 0) → **FAIL**
    * Clean independent traces → **PASS**
    """
    if not events:
        if require_events:
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=(
                    "COVERT-COLLUSION: no agent trace events — cannot run "
                    "black-box steganalysis without behavioural inventory "
                    "(arXiv 2608.02698)"
                ),
                exit_code=2,
                human_required=True,
            )
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason="COVERT-COLLUSION: no events required",
            exit_code=0,
        )

    try:
        report = detect_covert_collusion(events, sync_window=sync_window)
    except (TypeError, ValueError) as exc:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=f"COVERT-COLLUSION: invalid events: {exc}",
            exit_code=2,
            human_required=True,
        )

    if report.agent_count < min_agents:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=(
                f"COVERT-COLLUSION: agent_count={report.agent_count} < "
                f"min_agents={min_agents} — population-level detector needs "
                "multi-agent traces"
            ),
            exit_code=2,
            human_required=True,
            fact_count=report.event_count,
        )

    filtered: list[CollusionSignal] = []
    for s in report.signals:
        if s.kind == "shared_payload" and not refuse_shared_payload:
            continue
        if s.kind == "sync_timing" and not refuse_sync_timing:
            continue
        if s.kind == "side_channel_code" and not refuse_side_channel:
            continue
        filtered.append(s)

    if len(filtered) > max_signals:
        kinds = sorted({s.kind for s in filtered})
        agents = sorted({a for s in filtered for a in s.agents})
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"COVERT-COLLUSION: {len(filtered)} signal(s) kinds={kinds} "
                f"agents={agents[:8]} score={report.collusion_score:.2f} "
                f"shared_payload={report.shared_payload_groups} "
                f"sync_pairs={report.sync_pairs} side_channel={report.side_channel_groups} "
                f"— refuse treating agents as independent (arXiv 2608.02698)"
            ),
            exit_code=1,
            human_required=True,
            fact_count=report.event_count,
            divergence_count=len(filtered),
            contested_keys=tuple(kinds),
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"COVERT-COLLUSION ok: events={report.event_count} "
            f"agents={report.agent_count} signals={len(filtered)}"
        ),
        exit_code=0,
        human_required=False,
        fact_count=report.event_count,
        divergence_count=0,
    )


def assert_no_covert_collusion(
    events: Sequence[AgentTraceEvent | dict[str, Any]] | None,
    **kwargs: Any,
) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless :func:`gate_covert_collusion` is ok."""
    outcome = gate_covert_collusion(events, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
