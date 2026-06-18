"""Tests for the agentcrdt Click CLI using CliRunner."""
from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from agentcrdt.cli import main


@pytest.fixture
def runner() -> CliRunner:
    """Return a Click CliRunner."""
    return CliRunner()


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Return a path to a temp database file."""
    return str(tmp_path / "cli_test.db")


class TestHelp:
    """Tests for --help flags."""

    def test_main_help(self, runner: CliRunner) -> None:
        """agentcrdt --help must exit 0 and mention CRDT."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "CRDT" in result.output or "world state" in result.output.lower()

    def test_set_help(self, runner: CliRunner) -> None:
        """agentcrdt set --help must exit 0."""
        result = runner.invoke(main, ["set", "--help"])
        assert result.exit_code == 0

    def test_get_help(self, runner: CliRunner) -> None:
        """agentcrdt get --help must exit 0."""
        result = runner.invoke(main, ["get", "--help"])
        assert result.exit_code == 0

    def test_merge_help(self, runner: CliRunner) -> None:
        """agentcrdt merge --help must exit 0."""
        result = runner.invoke(main, ["merge", "--help"])
        assert result.exit_code == 0

    def test_events_help(self, runner: CliRunner) -> None:
        """agentcrdt events --help must exit 0."""
        result = runner.invoke(main, ["events", "--help"])
        assert result.exit_code == 0

    def test_status_help(self, runner: CliRunner) -> None:
        """agentcrdt status --help must exit 0."""
        result = runner.invoke(main, ["status", "--help"])
        assert result.exit_code == 0


class TestSetCommand:
    """Tests for the 'set' subcommand."""

    def test_set_stores_fact(self, runner: CliRunner, db_path: str) -> None:
        """set must store a fact and print confirmation."""
        result = runner.invoke(
            main, ["--db", db_path, "set", "life", "king", "alive", "True"]
        )
        assert result.exit_code == 0
        assert "life.king.alive" in result.output

    def test_set_boolean_value(self, runner: CliRunner, db_path: str) -> None:
        """set must parse Python literals correctly."""
        result = runner.invoke(
            main, ["--db", db_path, "set", "life", "king", "alive", "False"]
        )
        assert result.exit_code == 0

    def test_set_string_value(self, runner: CliRunner, db_path: str) -> None:
        """set with a plain string value must succeed."""
        result = runner.invoke(
            main, ["--db", db_path, "set", "possession", "sword", "owner", "knight"]
        )
        assert result.exit_code == 0
        assert "possession.sword.owner" in result.output

    def test_set_with_version(self, runner: CliRunner, db_path: str) -> None:
        """set --version flag must be accepted."""
        result = runner.invoke(
            main,
            ["--db", db_path, "set", "life", "king", "alive", "True", "--version", "2"],
        )
        assert result.exit_code == 0

    def test_set_with_agent_id(self, runner: CliRunner, db_path: str) -> None:
        """set --agent-id flag must be accepted."""
        result = runner.invoke(
            main,
            ["--db", db_path, "set", "life", "king", "alive", "True", "--agent-id", "my-agent"],
        )
        assert result.exit_code == 0


class TestGetCommand:
    """Tests for the 'get' subcommand."""

    def test_get_existing_fact(self, runner: CliRunner, db_path: str) -> None:
        """get must return the stored value."""
        runner.invoke(main, ["--db", db_path, "set", "life", "king", "alive", "True"])
        result = runner.invoke(main, ["--db", db_path, "get", "life", "king", "alive"])
        assert result.exit_code == 0
        assert "life.king.alive" in result.output

    def test_get_nonexistent_exits_1(self, runner: CliRunner, db_path: str) -> None:
        """get for a missing fact must exit with code 1."""
        result = runner.invoke(
            main, ["--db", db_path, "get", "nonexistent", "entity", "attr"]
        )
        assert result.exit_code == 1


class TestMergeCommand:
    """Tests for the 'merge' subcommand."""

    def test_merge_two_dbs(self, runner: CliRunner, tmp_path: Path) -> None:
        """merge must transfer facts from the other DB."""
        local_db = str(tmp_path / "local.db")
        remote_db = str(tmp_path / "remote.db")
        runner.invoke(
            main, ["--db", remote_db, "set", "life", "king", "alive", "True"]
        )
        result = runner.invoke(main, ["--db", local_db, "merge", remote_db])
        assert result.exit_code == 0
        assert "Merged" in result.output
        assert "1" in result.output


class TestEventsCommand:
    """Tests for the 'events' subcommand."""

    def test_events_empty_store(self, runner: CliRunner, db_path: str) -> None:
        """events on an empty store must show 'No contradiction events.'."""
        result = runner.invoke(main, ["--db", db_path, "events"])
        assert result.exit_code == 0
        assert "No contradiction" in result.output


class TestStatusCommand:
    """Tests for the 'status' subcommand."""

    def test_status_empty_store(self, runner: CliRunner, db_path: str) -> None:
        """status on an empty store must show 0 facts and 0 events."""
        result = runner.invoke(main, ["--db", db_path, "status"])
        assert result.exit_code == 0
        assert "0 fact" in result.output

    def test_status_after_set(self, runner: CliRunner, db_path: str) -> None:
        """status after adding a fact must show 1 fact."""
        runner.invoke(main, ["--db", db_path, "set", "life", "king", "alive", "True"])
        result = runner.invoke(main, ["--db", db_path, "status"])
        assert result.exit_code == 0
        assert "1 fact" in result.output


class TestVersionOption:
    """Tests for --version option."""

    def test_version_option(self, runner: CliRunner) -> None:
        """--version must output the package version string."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output or "version" in result.output.lower()
