"""CLI for agentcrdt."""

from __future__ import annotations

import click

from agentcrdt.fact import WorldFact, _sha16
from agentcrdt.merger import WorldMerger
from agentcrdt.report import print_events, print_state
from agentcrdt.store import WorldStore


def _open(db: str) -> WorldStore:
    """Open a :class:`WorldStore` at the given path."""
    return WorldStore(db)


@click.group()
@click.version_option(package_name="agentcrdt")
@click.option(
    "--db",
    default="agentcrdt.db",
    show_default=True,
    envvar="AGENTCRDT_DB",
    help="Path to the agentcrdt SQLite database.",
)
@click.pass_context
def main(ctx: click.Context, db: str) -> None:
    """Semantic-causal CRDT for agent-mutable world state."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@main.command("set")
@click.argument("domain")
@click.argument("entity")
@click.argument("attr")
@click.argument("value")
@click.option("--version", default=0, type=int, help="CRDT version vector.")
@click.option("--agent-id", default="", type=str, help="Originating agent identifier.")
@click.pass_context
def set_cmd(
    ctx: click.Context,
    domain: str,
    entity: str,
    attr: str,
    value: str,
    version: int,
    agent_id: str,
) -> None:
    """Set a world fact."""
    import ast

    try:
        parsed = ast.literal_eval(value)
    except Exception:  # pragma: no cover
        parsed = value
    fact = WorldFact(
        domain=domain,
        entity=entity,
        attribute=attr,
        value=parsed,
        version=version,
        agent_id=agent_id,
    )
    with _open(ctx.obj["db"]) as store:
        store.set_fact(fact)
    click.echo(f"Set {fact.id}  {domain}.{entity}.{attr}={parsed!r}")


@main.command("get")
@click.argument("domain")
@click.argument("entity")
@click.argument("attr")
@click.pass_context
def get_cmd(ctx: click.Context, domain: str, entity: str, attr: str) -> None:
    """Get a world fact."""
    fact_id = _sha16(f"{domain}|{entity}|{attr}")
    with _open(ctx.obj["db"]) as store:
        f = store.get_fact(fact_id)
    if f is None:
        click.echo("Not found.", err=True)
        raise SystemExit(1)
    click.echo(
        f"{f.domain}.{f.entity}.{f.attribute}={f.value!r}  v{f.version}  agent={f.agent_id!r}"
    )


@main.command("merge")
@click.argument("other_db")
@click.pass_context
def merge_cmd(ctx: click.Context, other_db: str) -> None:
    """Merge another store into this one."""
    with _open(ctx.obj["db"]) as local, _open(other_db) as remote:
        result = WorldMerger().merge(local, remote)
    click.echo(f"Merged {result.merged_count} facts. Contradictions: {len(result.conflicts)}")


@main.command("events")
@click.pass_context
def events_cmd(ctx: click.Context) -> None:
    """List contradiction events."""
    with _open(ctx.obj["db"]) as store:
        evts = store.list_events()
    print_events(evts)


@main.command("status")
@click.pass_context
def status_cmd(ctx: click.Context) -> None:
    """Show current world state."""
    with _open(ctx.obj["db"]) as store:
        facts = store.list_facts()
        evts = store.list_events()
    click.echo(f"{len(facts)} fact(s), {len(evts)} contradiction event(s)")
    print_state(facts)
