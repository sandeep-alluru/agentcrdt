"""FastAPI REST wrapper for agentcrdt."""
from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field
except ImportError as exc:
    raise ImportError("API server requires: pip install 'agentcrdt[api]'") from exc

from agentcrdt import __version__
from agentcrdt.fact import WorldFact
from agentcrdt.merger import WorldMerger
from agentcrdt.store import WorldStore

app = FastAPI(
    title="agentcrdt API",
    description="Semantic-causal CRDT for agent-mutable world state.",
    version=__version__,
)


class FactRequest(BaseModel):
    """Request body for ``POST /fact``."""

    domain: str
    entity: str
    attribute: str
    value: Any
    version: int = 0
    agent_id: str = ""
    db: str = Field("agentcrdt.db")


class MergeRequest(BaseModel):
    """Request body for ``POST /merge``."""

    other_db: str
    db: str = Field("agentcrdt.db")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return service health and version."""
    return {"status": "ok", "version": __version__}


@app.post("/fact")
async def set_fact(request: FactRequest) -> Any:
    """Store or update a world fact using LWW CRDT semantics."""
    fact = WorldFact(
        domain=request.domain,
        entity=request.entity,
        attribute=request.attribute,
        value=request.value,
        version=request.version,
        agent_id=request.agent_id,
    )
    with WorldStore(request.db) as store:
        store.set_fact(fact)
    return fact.to_dict()


@app.get("/facts")
async def list_facts(db: str = "agentcrdt.db", domain: str | None = None) -> Any:
    """List all world facts, optionally filtered by domain."""
    with WorldStore(db) as store:
        facts = store.list_facts(domain=domain)
    return {"facts": [f.to_dict() for f in facts]}


@app.post("/merge")
async def merge(request: MergeRequest) -> Any:
    """Merge a remote store into the local store."""
    with WorldStore(request.db) as local, WorldStore(request.other_db) as remote:
        result = WorldMerger().merge(local, remote)
    return result.to_dict()


@app.get("/events")
async def list_events(db: str = "agentcrdt.db") -> Any:
    """List all contradiction events."""
    with WorldStore(db) as store:
        evts = store.list_events()
    return {"events": [e.to_dict() for e in evts]}
