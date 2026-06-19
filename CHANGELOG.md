# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `FactHistory` and `FactVersion` for tracking all historical versions of each world fact
- `WorldStore.list_fact_history_by_entity_attr()` and `list_fact_history_by_entity()` for history queries
- `fact_history` SQLite table added to WorldStore schema
- `ConflictSummary`, `conflict_report()`, and `conflicts_for_entity()` for conflict analytics
- `ChangeWatcher` with `on_change()` decorator, `check()`, and `snapshot()` for reactive change detection
- Tests: `tests/test_history.py`, `tests/test_conflict_report.py`, `tests/test_watch.py`

## [0.1.0] - 2026-06-17

### Added
- Initial release

[Unreleased]: https://github.com/sandeep-alluru/agentcrdt/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeep-alluru/agentcrdt/releases/tag/v0.1.0
