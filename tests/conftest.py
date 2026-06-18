"""Shared pytest fixtures for agentcrdt tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from agentcrdt.rules import SemanticRule
from agentcrdt.store import WorldStore


@pytest.fixture
def tmp_store(tmp_path: Path) -> WorldStore:
    """Return a fresh :class:`WorldStore` in a temporary directory."""
    store = WorldStore(tmp_path / "test.db")
    yield store
    store.close()


@pytest.fixture
def king_alive_rule() -> SemanticRule:
    """Return a SemanticRule: if alliance.treaty.valid=True then life.king.alive must be True."""
    return SemanticRule(
        name="dead-king-voids-treaty",
        trigger_domain="alliance",
        trigger_attribute="valid",
        trigger_value=True,
        implies_domain="life",
        implies_entity_same=False,  # different entity: treaty vs king
        implies_attribute="alive",
        implies_value=True,
    )


@pytest.fixture
def king_dead_treaty_rule() -> SemanticRule:
    """Return the canonical contradiction rule used in merger tests.

    When life.king.alive=False, alliance.treaty-1.valid must be False.
    """
    return SemanticRule(
        name="dead-king-voids-treaty",
        trigger_domain="life",
        trigger_attribute="alive",
        trigger_value=False,
        implies_domain="alliance",
        implies_entity_same=False,
        implies_attribute="valid",
        implies_value=False,
    )
