"""WorldFact and ContradictionEvent — content-addressed primitives of agentcrdt."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


def _sha16(text: str) -> str:
    """Return the first 16 hex chars of SHA-256 of text."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@dataclass
class WorldFact:
    """An immutable, content-addressed fact about world state.

    The ``id`` field is derived from ``domain|entity|attribute`` so two
    agents recording the same fact key always get the same ID.
    """

    domain: str  # "life", "alliance", "possession", "knowledge"
    entity: str  # "king", "treaty-1"
    attribute: str  # "alive", "valid", "owner"
    value: Any  # bool, str, float, None
    version: int = 0
    agent_id: str = ""
    timestamp: float = field(default_factory=time.time)
    id: str = field(init=False)  # SHA-256[:16] of "domain|entity|attribute"

    def __post_init__(self) -> None:
        """Compute content-addressed id."""
        self.id = _sha16(f"{self.domain}|{self.entity}|{self.attribute}")

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "id": self.id,
            "domain": self.domain,
            "entity": self.entity,
            "attribute": self.attribute,
            "value": self.value,
            "version": self.version,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorldFact:
        """Deserialise from a plain dict produced by ``to_dict``."""
        f = cls(
            domain=d["domain"],
            entity=d["entity"],
            attribute=d["attribute"],
            value=d["value"],
            version=d.get("version", 0),
            agent_id=d.get("agent_id", ""),
            timestamp=d.get("timestamp", 0.0),
        )
        return f

    def __repr__(self) -> str:
        key = f"{self.domain}.{self.entity}.{self.attribute}"
        return f"WorldFact({self.id!r}: {key}={self.value!r})"


@dataclass
class ContradictionEvent:
    """Fired when two agents hold semantically incompatible world facts.

    The ``id`` is content-addressed from the rule name, sorted fact IDs,
    and the two agent IDs so identical contradictions dedup correctly.
    """

    rule: str
    facts_involved: list[str]
    agent_a: str
    agent_b: str
    timestamp: float = field(default_factory=time.time)
    id: str = field(init=False)

    def __post_init__(self) -> None:
        """Compute content-addressed id."""
        payload = (
            f"{self.rule}|{'|'.join(sorted(self.facts_involved))}|{self.agent_a}|{self.agent_b}"
        )
        self.id = _sha16(payload)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "id": self.id,
            "rule": self.rule,
            "facts_involved": self.facts_involved,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "timestamp": self.timestamp,
        }
