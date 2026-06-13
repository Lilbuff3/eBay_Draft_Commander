"""
Unit test suite guard: never let tests touch the real data/ directory.

QueueManager resolves its database location via get_data_dir() when no
base_path is given. A test that forgets to pass base_path (or to patch
get_data_dir) would otherwise write job rows into the production
data/commander.db. This autouse fixture redirects the symbol that
QueueManager actually uses to a per-test tmp directory.

Tests that patch get_data_dir themselves simply override this (both point
at tmp dirs), and tests passing base_path are isolated by QueueManager
honoring base_path for its data path.
"""
import pytest


@pytest.fixture(autouse=True)
def _isolate_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "backend.app.services.queue_manager.get_data_dir", lambda: data_dir
    )
    yield data_dir
