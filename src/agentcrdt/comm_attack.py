"""COMM-ATTACK — multi-agent communication integrity (arXiv 2608.06830).

Public case: *When Coordination Becomes a Threat: Communication Attacks in
LLM-Controlled Multi-Robot Systems*. LLM planners coordinate embodied agents
over message channels; attackers inject via:

  * **External Entry Point Attack** — untrusted external sender enters the mesh
  * **Privileged In-System Attack** — compromised or spoofed privileged channel

Architectures: DMAS (peer mesh), HMAS-1 / HMAS-2 (hierarchical).

Product role in agentcrdt (COVERT-COLLUSION / MAST twin):
  Gate **message-layer** integrity. Collusion detectors see tool/payload
  behaviour; multi-agent value gates see CRDT divergences; this gate refuses
  coordination when the *communication graph* is poisoned.

Non-Ornament:
  Call ``gate_comm_integrity`` before executing multi-agent coordination
  plans that depend on inter-agent messages.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from agentcrdt.closed_loop import ClosedLoopError, GateOutcome

Architecture = Literal["dmas", "hmas1", "hmas2", "unknown"]

# Roles that may originate privileged / planner-plane messages.
DEFAULT_PRIVILEGED_ROLES: frozenset[str] = frozenset(
    {
        "planner",
        "coordinator",
        "supervisor",
        "leader",
        "privileged",
        "root",
        "admin",
        "orchestrator",
    }
)

# Roles treated as external to the multi-agent system.
DEFAULT_EXTERNAL_ROLES: frozenset[str] = frozenset(
    {
        "external",
        "outsider",
        "internet",
        "public",
        "untrusted",
        "attacker",
        "entry_point",
    }
)

# Content phrases that re-task peers (injection class).
DEFAULT_COMM_INJECTION_PHRASES: frozenset[str] = frozenset(
    {
        "ignore previous instructions",
        "ignore prior plan",
        "disregard coordinator",
        "new goal:",
        "reassign target",
        "abort mission and",
        "override safety",
        "skip authentication",
        "exfiltrate",
        "send credentials",
        "attack ally",
        "disable peer",
        "drop package at",
    }
)

DEFAULT_PRIVILEGED_CHANNELS: frozenset[str] = frozenset(
    {
        "privileged",
        "control",
        "planner",
        "supervisor",
        "hmas_control",
        "command",
        "admin",
    }
)


@dataclass(frozen=True)
class AgentMessage:
    """One inter-agent coordination message.

    Attributes:
        msg_id: Stable message id.
        sender: Sending agent id.
        receiver: Target agent id (or ``broadcast`` / ``*``).
        content: Message body (natural language or structured text).
        channel: Logical channel name (peer, control, …).
        role: Declared sender role (peer, planner, external, …).
        architecture: Optional architecture tag for this hop.
    """

    msg_id: str
    sender: str
    receiver: str
    content: str = ""
    channel: str = "peer"
    role: str = "peer"
    architecture: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "msg_id": self.msg_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "content": self.content,
            "channel": self.channel,
            "role": self.role,
            "architecture": self.architecture,
        }


@dataclass(frozen=True)
class CommAttackSignal:
    """One communication-attack finding."""

    kind: str  # external_entry | privileged_spoof | content_injection | unknown_sender
    msg_id: str
    detail: str
    score: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "msg_id": self.msg_id,
            "detail": self.detail,
            "score": self.score,
        }


@dataclass(frozen=True)
class CommAttackReport:
    """Aggregate communication integrity analysis."""

    message_count: int
    agent_count: int
    signals: tuple[CommAttackSignal, ...]
    external_entry_count: int
    privileged_spoof_count: int
    injection_count: int
    architecture: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def has_attack(self) -> bool:
        return bool(self.signals)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_count": self.message_count,
            "agent_count": self.agent_count,
            "signals": [s.to_dict() for s in self.signals],
            "external_entry_count": self.external_entry_count,
            "privileged_spoof_count": self.privileged_spoof_count,
            "injection_count": self.injection_count,
            "architecture": self.architecture,
            "has_attack": self.has_attack,
            "details": dict(self.details),
        }


def _canon(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_").replace("-", "_")


def _as_message(item: Any, index: int = 0) -> AgentMessage:
    if isinstance(item, AgentMessage):
        return item
    if not isinstance(item, dict):
        raise TypeError(f"message must be AgentMessage or dict, got {type(item)!r}")
    mid = str(item.get("msg_id") or item.get("id") or f"msg_{index}").strip()
    sender = str(item.get("sender") or item.get("from") or item.get("agent_id") or "").strip()
    receiver = str(
        item.get("receiver") or item.get("to") or item.get("target") or "broadcast"
    ).strip()
    if not sender:
        raise ValueError(f"message {mid!r} missing sender")
    return AgentMessage(
        msg_id=mid,
        sender=sender,
        receiver=receiver,
        content=str(item.get("content") or item.get("body") or item.get("text") or ""),
        channel=str(item.get("channel") or item.get("bus") or "peer"),
        role=str(item.get("role") or item.get("sender_role") or "peer"),
        architecture=str(item.get("architecture") or item.get("arch") or ""),
    )


def detect_comm_injection_phrases(
    text: str,
    *,
    phrases: Iterable[str] | None = None,
) -> list[str]:
    """Return coordination-injection phrases found in *text*."""
    blob = (text or "").lower()
    if not blob:
        return []
    found: list[str] = []
    for p in phrases if phrases is not None else DEFAULT_COMM_INJECTION_PHRASES:
        pl = p.lower()
        if pl and pl in blob:
            found.append(p)
    return found


def is_privileged_role(role: str) -> bool:
    return _canon(role) in DEFAULT_PRIVILEGED_ROLES


def is_external_role(role: str) -> bool:
    return _canon(role) in DEFAULT_EXTERNAL_ROLES


def is_privileged_channel(channel: str) -> bool:
    c = _canon(channel)
    if c in DEFAULT_PRIVILEGED_CHANNELS:
        return True
    return c.startswith("priv") or c.endswith("_control") or "privileged" in c


def analyze_comm_attacks(
    messages: Sequence[Any] | None,
    *,
    system_agents: Sequence[str] | None = None,
    trusted_external_senders: Sequence[str] | None = None,
    privileged_senders: Sequence[str] | None = None,
    architecture: str = "dmas",
    injection_phrases: Iterable[str] | None = None,
) -> CommAttackReport:
    """Detect External Entry Point and Privileged In-System attack signals.

    Does not gate; use :func:`gate_comm_integrity`.
    """
    parsed = [_as_message(m, i) for i, m in enumerate(messages or [])]
    arch = _canon(architecture) or "dmas"
    system = {_canon(a) for a in (system_agents or []) if str(a).strip()}
    if not system:
        # infer system agents from non-external roles
        system = {
            _canon(m.sender) for m in parsed if not is_external_role(m.role) and _canon(m.sender)
        }
    trusted_ext = {_canon(a) for a in (trusted_external_senders or []) if str(a).strip()}
    priv_senders = {_canon(a) for a in (privileged_senders or []) if str(a).strip()}
    # privileged senders default: system agents with privileged role messages
    if not priv_senders:
        priv_senders = {
            _canon(m.sender)
            for m in parsed
            if is_privileged_role(m.role) and _canon(m.sender) in system
        }

    signals: list[CommAttackSignal] = []
    n_ext = n_priv = n_inj = 0

    for m in parsed:
        sid = _canon(m.sender)
        role = _canon(m.role)
        ch = _canon(m.channel)

        # External Entry Point Attack
        externalish = is_external_role(role) or (system and sid not in system)
        if externalish and sid not in trusted_ext:
            n_ext += 1
            signals.append(
                CommAttackSignal(
                    kind="external_entry",
                    msg_id=m.msg_id,
                    detail=(
                        f"sender={m.sender!r} role={m.role!r} not in trusted "
                        f"external entry points — External Entry Point Attack "
                        f"(arXiv 2608.06830)"
                    ),
                    score=1.0,
                )
            )

        # Privileged In-System Attack: privileged channel/role without auth
        uses_priv_plane = is_privileged_channel(ch) or is_privileged_role(role)
        if uses_priv_plane and sid not in priv_senders and sid not in trusted_ext:
            n_priv += 1
            signals.append(
                CommAttackSignal(
                    kind="privileged_spoof",
                    msg_id=m.msg_id,
                    detail=(
                        f"sender={m.sender!r} role={m.role!r} channel={m.channel!r} "
                        f"uses privileged plane without grant — Privileged "
                        f"In-System Attack (arXiv 2608.06830)"
                    ),
                    score=1.0,
                )
            )

        # Content injection in coordination messages
        hits = detect_comm_injection_phrases(m.content, phrases=injection_phrases)
        if hits:
            n_inj += 1
            signals.append(
                CommAttackSignal(
                    kind="content_injection",
                    msg_id=m.msg_id,
                    detail=f"phrases={hits[:4]} in msg from {m.sender!r}",
                    score=1.0,
                )
            )

    agents = {_canon(m.sender) for m in parsed} | {
        _canon(m.receiver) for m in parsed if m.receiver not in {"*", "broadcast", ""}
    }

    return CommAttackReport(
        message_count=len(parsed),
        agent_count=len({a for a in agents if a}),
        signals=tuple(signals),
        external_entry_count=n_ext,
        privileged_spoof_count=n_priv,
        injection_count=n_inj,
        architecture=arch,
        details={
            "system_agents": sorted(system),
            "trusted_external": sorted(trusted_ext),
            "privileged_senders": sorted(priv_senders),
        },
    )


def gate_comm_integrity(
    messages: Sequence[Any] | None,
    *,
    system_agents: Sequence[str] | None = None,
    trusted_external_senders: Sequence[str] | None = None,
    privileged_senders: Sequence[str] | None = None,
    architecture: str = "dmas",
    claim_coordinated: bool = False,
    require_messages: bool = True,
    refuse_external_entry: bool = True,
    refuse_privileged_spoof: bool = True,
    refuse_content_injection: bool = True,
    max_signals: int = 0,
    injection_phrases: Iterable[str] | None = None,
) -> GateOutcome:
    """Refuse multi-agent coordination when communication channel is attacked.

    Public case: arXiv 2608.06830 — External Entry Point and Privileged
    In-System attacks against LLM-controlled multi-robot / multi-agent systems
    under DMAS / HMAS architectures.

    Rules:

    1. ``claim_coordinated`` with zero messages → **FAIL_LOUD**
    2. Empty inventory when required → **FAIL_LOUD**
    3. External Entry Point (untrusted external sender) → **FAIL**
    4. Privileged In-System spoof (non-privileged on control plane) → **FAIL**
    5. Content injection phrases in messages → **FAIL**
    6. Signal count above ``max_signals`` (default 0) → **FAIL**
    7. Clean internal mesh → **PASS**
    """
    if not messages:
        if claim_coordinated or require_messages:
            return GateOutcome(
                ok=False,
                verdict="FAIL_LOUD",
                reason=(
                    "COMM-ATTACK: empty message inventory — cannot authorize "
                    "multi-agent coordination without communication log "
                    f"(claim_coordinated={claim_coordinated}; arXiv 2608.06830)"
                ),
                exit_code=2,
                human_required=True,
            )
        return GateOutcome(
            ok=True,
            verdict="PASS",
            reason="COMM-ATTACK: no messages required",
            exit_code=0,
        )

    try:
        report = analyze_comm_attacks(
            messages,
            system_agents=system_agents,
            trusted_external_senders=trusted_external_senders,
            privileged_senders=privileged_senders,
            architecture=architecture,
            injection_phrases=injection_phrases,
        )
    except (TypeError, ValueError) as exc:
        return GateOutcome(
            ok=False,
            verdict="FAIL_LOUD",
            reason=f"COMM-ATTACK: invalid messages: {exc}",
            exit_code=2,
            human_required=True,
        )

    filtered: list[CommAttackSignal] = []
    for s in report.signals:
        if s.kind == "external_entry" and not refuse_external_entry:
            continue
        if s.kind == "privileged_spoof" and not refuse_privileged_spoof:
            continue
        if s.kind == "content_injection" and not refuse_content_injection:
            continue
        filtered.append(s)

    if len(filtered) > max_signals:
        kinds = sorted({s.kind for s in filtered})
        return GateOutcome(
            ok=False,
            verdict="FAIL",
            reason=(
                f"COMM-ATTACK: {len(filtered)} communication attack signal(s) "
                f"kinds={kinds} architecture={report.architecture} — refuse "
                f"coordination under External Entry / Privileged In-System "
                f"threat class (arXiv 2608.06830)"
            ),
            exit_code=1,
            human_required=True,
            fact_count=report.message_count,
            conflict_count=len(filtered),
            contested_keys=tuple(s.msg_id for s in filtered[:12]),
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"COMM-ATTACK ok: messages={report.message_count} "
            f"agents={report.agent_count} architecture={report.architecture} "
            f"signals=0"
        ),
        exit_code=0,
        fact_count=report.message_count,
        human_required=False,
    )


def assert_comm_integrity(
    messages: Sequence[Any] | None,
    **kwargs: Any,
) -> GateOutcome:
    """Raise :class:`ClosedLoopError` unless :func:`gate_comm_integrity` is ok."""
    outcome = gate_comm_integrity(messages, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
