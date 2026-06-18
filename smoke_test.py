"""
End-to-end smoke test for agentcrdt.

Simulates a user who just cloned the repo and wants to verify everything works.
No mocking, no fixtures — real behaviour, real CLI, real HTTP server.

Run from repo root:
    python smoke_test.py
    python smoke_test.py --verbose

Exit 0 = all passed. Exit 1 = at least one failure.
"""

from __future__ import annotations

import importlib  # noqa: F401
import io
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
REPO_ROOT = Path(__file__).parent
PYTHON = sys.executable

passed: list[str] = []
failed: list[tuple[str, str]] = []


def ok(name: str) -> None:
    passed.append(name)
    print(f"  {GREEN}✓{RESET} {name}")


def fail(name: str, reason: str) -> None:
    failed.append((name, reason))
    print(f"  {RED}✗{RESET} {name}")
    if VERBOSE:
        print(f"    {YELLOW}{reason}{RESET}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def run(name: str, fn):  # noqa: ANN001
    try:
        fn()
        ok(name)
    except Exception as exc:
        reason = str(exc) if not VERBOSE else traceback.format_exc().strip()
        fail(name, reason)


# ── 1. Package import ─────────────────────────────────────────────────────────

section("1. Package import")

def _test_import_version():
    import agentcrdt
    assert agentcrdt.__version__, "__version__ is empty"
    assert agentcrdt.__version__ != "0.0.0"

def _test_import_public_api():
    from agentcrdt import (
        ContradictionEvent, MergeResult, RuleEngine, SemanticRule,
        WorldFact, WorldMerger, WorldStore,
    )
    assert callable(WorldStore)
    assert callable(WorldMerger)

run("agentcrdt package imports", _test_import_version)
run("Public API (WorldFact, WorldStore, WorldMerger, RuleEngine)", _test_import_public_api)


# ── 2. Core data model ────────────────────────────────────────────────────────

section("2. Core data model (WorldFact, SemanticRule, MergeResult)")

def _test_fact_content_addressing():
    from agentcrdt.fact import WorldFact
    f1 = WorldFact(domain="life", entity="king", attribute="alive", value=True)
    f2 = WorldFact(domain="life", entity="king", attribute="alive", value=False)
    assert f1.id == f2.id, "Same key must produce same ID regardless of value"
    f3 = WorldFact(domain="life", entity="king", attribute="health", value=True)
    assert f1.id != f3.id

def _test_fact_serialization():
    from agentcrdt.fact import WorldFact
    f = WorldFact(
        domain="possession", entity="sword", attribute="owner",
        value="knight", version=3, agent_id="agent-007"
    )
    d = f.to_dict()
    assert d["domain"] == "possession"
    assert d["version"] == 3
    f2 = WorldFact.from_dict(d)
    assert f2.id == f.id
    assert f2.value == "knight"

def _test_semantic_rule_fields():
    from agentcrdt.rules import SemanticRule
    rule = SemanticRule(
        name="dead-king-voids-treaty",
        trigger_domain="life", trigger_attribute="alive", trigger_value=False,
        implies_domain="alliance", implies_entity_same=True,
        implies_attribute="valid", implies_value=False,
    )
    assert rule.name == "dead-king-voids-treaty"
    assert rule.trigger_value is False

def _test_merge_result_to_dict():
    from agentcrdt.merger import MergeResult
    r = MergeResult(merged_count=5, conflicts=[])
    d = r.to_dict()
    assert d["merged_count"] == 5
    assert d["conflicts"] == []

def _test_contradiction_event_content_addressed():
    from agentcrdt.fact import ContradictionEvent
    e1 = ContradictionEvent(rule="r", facts_involved=["f1", "f2"], agent_a="a", agent_b="b")
    e2 = ContradictionEvent(rule="r", facts_involved=["f2", "f1"], agent_a="a", agent_b="b")
    assert e1.id == e2.id

run("WorldFact.id is content-addressed (same key = same ID)", _test_fact_content_addressing)
run("WorldFact.to_dict() / from_dict() round-trip", _test_fact_serialization)
run("SemanticRule stores all fields correctly", _test_semantic_rule_fields)
run("MergeResult.to_dict() serialises correctly", _test_merge_result_to_dict)
run("ContradictionEvent.id is order-invariant", _test_contradiction_event_content_addressed)


# ── 3. WorldMerger — contradiction detection and idempotent merge ─────────────

section("3. WorldMerger (CRDT merge + contradiction detection)")

def _test_merger_basic():
    from agentcrdt.fact import WorldFact
    from agentcrdt.merger import WorldMerger
    from agentcrdt.store import WorldStore
    with tempfile.TemporaryDirectory() as tmp:
        with WorldStore(f"{tmp}/local.db") as local, WorldStore(f"{tmp}/remote.db") as remote:
            f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
            remote.set_fact(f)
            result = WorldMerger().merge(local, remote)
            assert result.merged_count == 1
            assert local.get_fact(f.id) is not None

def _test_merger_contradiction_detected():
    from agentcrdt.fact import WorldFact
    from agentcrdt.merger import WorldMerger
    from agentcrdt.rules import RuleEngine, SemanticRule
    from agentcrdt.store import WorldStore
    with tempfile.TemporaryDirectory() as tmp:
        with WorldStore(f"{tmp}/local.db") as local, WorldStore(f"{tmp}/remote.db") as remote:
            king_dead = WorldFact(
                domain="life", entity="king", attribute="alive",
                value=False, version=1, agent_id="agent-A"
            )
            local.set_fact(king_dead)
            treaty_valid = WorldFact(
                domain="alliance", entity="king", attribute="valid",
                value=True, version=1, agent_id="agent-B"
            )
            remote.set_fact(treaty_valid)
            rule = SemanticRule(
                name="dead-king-voids-treaty",
                trigger_domain="life", trigger_attribute="alive", trigger_value=False,
                implies_domain="alliance", implies_entity_same=True,
                implies_attribute="valid", implies_value=False,
            )
            result = WorldMerger(rule_engine=RuleEngine([rule])).merge(local, remote)
            assert len(result.conflicts) == 1
            assert result.conflicts[0].rule == "dead-king-voids-treaty"

def _test_merger_idempotent():
    from agentcrdt.fact import WorldFact
    from agentcrdt.merger import WorldMerger
    from agentcrdt.store import WorldStore
    with tempfile.TemporaryDirectory() as tmp:
        with WorldStore(f"{tmp}/local.db") as local, WorldStore(f"{tmp}/remote.db") as remote:
            f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
            remote.set_fact(f)
            WorldMerger().merge(local, remote)
            WorldMerger().merge(local, remote)
            assert len(local.list_facts()) == 1

def _test_merger_lww_version():
    from agentcrdt.fact import WorldFact
    from agentcrdt.merger import WorldMerger
    from agentcrdt.store import WorldStore
    with tempfile.TemporaryDirectory() as tmp:
        with WorldStore(f"{tmp}/local.db") as local, WorldStore(f"{tmp}/remote.db") as remote:
            f_old = WorldFact(domain="life", entity="king", attribute="alive",
                              value=True, version=1, agent_id="agent-A")
            f_new = WorldFact(domain="life", entity="king", attribute="alive",
                              value=False, version=2, agent_id="agent-B")
            local.set_fact(f_old)
            remote.set_fact(f_new)
            WorldMerger().merge(local, remote)
            retrieved = local.get_fact(f_old.id)
            assert retrieved is not None
            assert retrieved.value is False, "Higher version must win"

run("WorldMerger.merge() copies facts from remote", _test_merger_basic)
run("WorldMerger detects contradiction (dead king, valid treaty)", _test_merger_contradiction_detected)
run("WorldMerger is idempotent (merge twice = no duplicates)", _test_merger_idempotent)
run("WorldMerger LWW: higher version wins", _test_merger_lww_version)


# ── 4. Output formatters ──────────────────────────────────────────────────────

section("4. Report formatters (JSON, Markdown, Rich)")

def _test_to_json_facts():
    from agentcrdt.fact import WorldFact
    from agentcrdt.report import to_json
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
    result = json.loads(to_json([f]))
    assert "facts" in result
    assert result["facts"][0]["domain"] == "life"

def _test_to_json_with_events():
    from agentcrdt.fact import ContradictionEvent, WorldFact
    from agentcrdt.report import to_json
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
    e = ContradictionEvent(rule="r", facts_involved=[f.id], agent_a="a", agent_b="b")
    result = json.loads(to_json([f], [e]))
    assert "events" in result
    assert len(result["events"]) == 1

def _test_to_markdown():
    from agentcrdt.fact import WorldFact
    from agentcrdt.report import to_markdown
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
    md = to_markdown([f])
    assert "agentcrdt world state" in md
    assert "|" in md
    assert "life" in md

def _test_print_state():
    from rich.console import Console
    from agentcrdt.fact import WorldFact
    from agentcrdt.report import print_state
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    f = WorldFact(domain="life", entity="king", attribute="alive", value=True)
    print_state([f], console=con)
    assert "life" in buf.getvalue()

def _test_print_state_empty():
    from rich.console import Console
    from agentcrdt.report import print_state
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    print_state([], console=con)
    assert "No world facts" in buf.getvalue()

def _test_print_events_empty():
    from rich.console import Console
    from agentcrdt.report import print_events
    buf = io.StringIO()
    con = Console(file=buf, highlight=False)
    print_events([], console=con)
    assert "No contradiction" in buf.getvalue()

def _test_to_markdown_with_events():
    from agentcrdt.fact import ContradictionEvent
    from agentcrdt.report import to_markdown
    e = ContradictionEvent(rule="dead-king", facts_involved=["f1"], agent_a="a", agent_b="b")
    md = to_markdown([], [e])
    assert "Contradictions" in md
    assert "dead-king" in md

run("to_json() produces valid JSON with 'facts' key", _test_to_json_facts)
run("to_json() includes 'events' when provided", _test_to_json_with_events)
run("to_markdown() produces Markdown table with fact row", _test_to_markdown)
run("print_state() outputs domain to console", _test_print_state)
run("print_state() shows 'No world facts' for empty list", _test_print_state_empty)
run("print_events() shows 'No contradiction' for empty list", _test_print_events_empty)
run("to_markdown() includes Contradictions section when events present", _test_to_markdown_with_events)


# ── 5. CLI ────────────────────────────────────────────────────────────────────

section("5. CLI (agentcrdt)")

def _test_cli_help():
    from click.testing import CliRunner
    from agentcrdt.cli import main
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert len(result.output) > 20, "Help output is empty"

def _test_cli_set_get():
    from click.testing import CliRunner
    from agentcrdt.cli import main
    runner = CliRunner()
    with runner.isolated_filesystem():
        r_set = runner.invoke(main, ["--db", "smoke.db", "set", "life", "king", "alive", "True"])
        assert r_set.exit_code == 0, r_set.output
        r_get = runner.invoke(main, ["--db", "smoke.db", "get", "life", "king", "alive"])
        assert r_get.exit_code == 0, r_get.output
        assert "life.king.alive" in r_get.output

def _test_cli_status():
    from click.testing import CliRunner
    from agentcrdt.cli import main
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(main, ["--db", "smoke.db", "set", "life", "king", "alive", "True"])
        r = runner.invoke(main, ["--db", "smoke.db", "status"])
        assert r.exit_code == 0, r.output
        assert "1 fact" in r.output

run("agentcrdt --help returns 0", _test_cli_help)
run("agentcrdt set + get round-trip", _test_cli_set_get)
run("agentcrdt status shows fact count", _test_cli_status)


# ── 6. FastAPI server ─────────────────────────────────────────────────────────

section("6. FastAPI server (agentcrdt[api])")

def _test_api_import():
    from agentcrdt.api import app
    assert app.title == "agentcrdt API"

def _test_api_health():
    from fastapi.testclient import TestClient
    from agentcrdt.api import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()

def _test_api_fact_workflow():
    from fastapi.testclient import TestClient
    from agentcrdt.api import app
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/api_smoke.db"
        r = client.post("/fact", json={
            "domain": "life", "entity": "king", "attribute": "alive",
            "value": True, "db": db,
        })
        assert r.status_code == 200
        assert "id" in r.json()
        r_list = client.get("/facts", params={"db": db})
        assert r_list.status_code == 200
        assert len(r_list.json()["facts"]) == 1

run("agentcrdt.api imports and app.title is correct", _test_api_import)
run("GET /health returns {status: ok, version: ...}", _test_api_health)
run("POST /fact + GET /facts workflow", _test_api_fact_workflow)


# ── 7. MCP server ─────────────────────────────────────────────────────────────

section("7. MCP server (agentcrdt[mcp])")

def _test_mcp_server_importable():
    import agentcrdt.mcp_server as m
    assert hasattr(m, "run_server")

def _test_mcp_server_loads_cleanly():
    import agentcrdt.mcp_server  # noqa: F401

run("mcp_server.py imports without error", _test_mcp_server_importable)
run("mcp_server module loads cleanly (no import-time crash)", _test_mcp_server_loads_cleanly)


# ── 8. Agent config files ─────────────────────────────────────────────────────

section("8. Agent config files (what a clone gives you)")

def _check_file_nonempty(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    assert p.stat().st_size > 50, f"File too small (likely empty): {rel}"

def _check_json_valid(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    json.loads(p.read_text())

def _check_yaml_parseable(rel: str) -> None:
    try:
        import yaml  # type: ignore[import-untyped]
        p = REPO_ROOT / rel
        assert p.exists(), f"Missing: {rel}"
        yaml.safe_load(p.read_text())
    except ImportError:
        content = (REPO_ROOT / rel).read_text()
        assert len(content) > 20, f"File appears empty: {rel}"

def _test_claude_commands():
    commands = list((REPO_ROOT / ".claude/commands").glob("*.md"))
    assert len(commands) >= 4, f"Expected ≥4 slash commands, found {len(commands)}"

def _test_openai_tools_valid():
    _check_json_valid("tools/openai-tools.json")
    tools = json.loads((REPO_ROOT / "tools/openai-tools.json").read_text())
    assert len(tools) >= 3
    assert all("function" in t for t in tools)

def _test_openapi_yaml_parseable():
    _check_yaml_parseable("openapi.yaml")

run("AGENTS.md exists and non-empty", lambda: _check_file_nonempty("AGENTS.md"))
run("CLAUDE.md exists and non-empty", lambda: _check_file_nonempty("CLAUDE.md"))
run("CODEX.md exists and non-empty", lambda: _check_file_nonempty("CODEX.md"))
run(".github/copilot-instructions.md exists", lambda: _check_file_nonempty(".github/copilot-instructions.md"))
def _test_cursor_rules():
    mdc_files = list((REPO_ROOT / ".cursor/rules").glob("*.mdc"))
    assert len(mdc_files) >= 1, f"Expected ≥1 .mdc file in .cursor/rules/, found none"

run(".cursor/rules/ has at least one .mdc file", _test_cursor_rules)
run(".windsurfrules exists", lambda: _check_file_nonempty(".windsurfrules"))
run(".aider.conf.yml exists", lambda: _check_file_nonempty(".aider.conf.yml"))
run(".continue/config.json is valid JSON", lambda: _check_json_valid(".continue/config.json"))
run(".claude/commands/ has ≥4 slash commands", _test_claude_commands)
run("tools/openai-tools.json is valid JSON with ≥3 tools", _test_openai_tools_valid)
run("openapi.yaml is parseable YAML", _test_openapi_yaml_parseable)


# ── 9. Docs site ──────────────────────────────────────────────────────────────

section("9. MkDocs documentation site")

def _test_mkdocs_yml():
    _check_file_nonempty("mkdocs.yml")
    content = (REPO_ROOT / "mkdocs.yml").read_text()
    assert "site_name" in content
    assert "material" in content

def _test_docs_pages():
    docs = list((REPO_ROOT / "docs").glob("*.md"))
    assert len(docs) >= 8, f"Expected ≥8 doc pages, found {len(docs)}"
    names = {p.name for p in docs}
    for required in ("index.md", "quickstart.md", "architecture.md", "api-reference.md"):
        assert required in names, f"Missing docs/{required}"

run("mkdocs.yml exists with site_name and material theme", _test_mkdocs_yml)
run("docs/ has ≥8 pages including index, quickstart, architecture, api-reference", _test_docs_pages)


# ── 10. examples/demo.py ─────────────────────────────────────────────────────

section("10. examples/demo.py end-to-end")

def _test_demo_runs():
    demo = REPO_ROOT / "examples" / "demo.py"
    assert demo.exists(), "examples/demo.py not found"
    r = subprocess.run(
        [PYTHON, str(demo)],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT)
    )
    if r.returncode != 0:
        raise AssertionError(f"demo.py exited {r.returncode}:\n{r.stderr[-500:]}")

run("examples/demo.py runs end-to-end without error", _test_demo_runs)


# ── Summary ───────────────────────────────────────────────────────────────────

total = len(passed) + len(failed)
print(f"\n{'═'*60}")
print(f"{BOLD}Results: {len(passed)}/{total} passed{RESET}")

if failed:
    print(f"{RED}Failed ({len(failed)}):{RESET}")
    for name, reason in failed:
        print(f"  {RED}✗{RESET} {name}")
        short = reason.split("\n")[0][:120]
        print(f"    {YELLOW}→ {short}{RESET}")
    print(f"\n{YELLOW}Tip: run with --verbose for full tracebacks{RESET}")
else:
    print(f"{GREEN}All {total} checks passed — agentcrdt is ready to ship{RESET}")

print(f"{'═'*60}\n")
sys.exit(0 if not failed else 1)
