"""Tests verifying queue_manager.py cleanup: isinstance check, save_state removal, ScannerService caching."""

import inspect
from backend.app.services.queue_manager import QueueManager


class TestNeedsReviewIsinstance:
    """Fix 1: _process_job should use isinstance(e, NeedsReviewException) not type(e).__name__."""

    def test_uses_isinstance_not_type_name(self):
        source = inspect.getsource(QueueManager._process_job)
        assert "isinstance(e, NeedsReviewException)" in source, (
            "_process_job should use isinstance(e, NeedsReviewException)"
        )
        assert "type(e).__name__ == 'NeedsReviewException'" not in source, (
            "_process_job should not use fragile type(e).__name__ string comparison"
        )


class TestSaveStateRemoved:
    """Fix 2: save_state() should be removed entirely."""

    def test_no_save_state_attribute(self):
        assert not hasattr(QueueManager, "save_state"), (
            "QueueManager should not have a save_state method"
        )


class TestScannerServiceCached:
    """Fix 3: _watch_inbox should instantiate ScannerService once outside the loop."""

    def test_scanner_service_instantiated_once(self):
        source = inspect.getsource(QueueManager._watch_inbox)
        count = source.count("ScannerService(")
        assert count == 1, (
            f"ScannerService( should appear exactly once in _watch_inbox, found {count}"
        )
        # Verify the instantiation is before the while loop, not inside it
        while_pos = source.index("while True:")
        scanner_pos = source.index("ScannerService(")
        assert scanner_pos < while_pos, (
            "ScannerService instantiation should be before the while loop"
        )
