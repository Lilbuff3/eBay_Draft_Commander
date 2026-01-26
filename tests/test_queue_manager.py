"""
Test Suite for Queue Manager
Tests job queue, state persistence, pause/resume, and error recovery.
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path

# Add project to path
# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.queue_manager import QueueManager, QueueJob, JobStatus


def test_add_jobs():
    """Test adding jobs to queue"""
    print("Test: Adding Jobs...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        qm = QueueManager(Path(tmpdir))
        
        # Create test folders
        folder1 = Path(tmpdir) / "inbox" / "item1"
        folder2 = Path(tmpdir) / "inbox" / "item2"
        folder1.mkdir(parents=True)
        folder2.mkdir(parents=True)
        
        # Add jobs
        job1 = qm.add_folder(str(folder1))
        job2 = qm.add_folder(str(folder2))
        
        assert len(qm.jobs) == 2, f"Expected 2 jobs, got {len(qm.jobs)}"
        assert job1.status == JobStatus.PENDING
        assert job2.folder_name == "item2"
        
        print("  ✅ Pass: Jobs added correctly")


def test_add_batch():
    """Test batch adding"""
    print("Test: Batch Adding...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        qm = QueueManager(Path(tmpdir))
        
        folders = []
        for i in range(5):
            f = Path(tmpdir) / f"item{i}"
            f.mkdir()
            folders.append(str(f))
        
        jobs = qm.add_batch(folders)
        
        assert len(jobs) == 5
        assert qm.get_stats()['pending'] == 5
        
        print("  ✅ Pass: Batch add works")


def test_state_persistence():
    """Test saving and loading queue state"""
    print("Test: State Persistence...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        qm1 = QueueManager(Path(tmpdir))
        
        folder = Path(tmpdir) / "test_item"
        folder.mkdir()
        
        job = qm1.add_folder(str(folder))
        job.status = JobStatus.COMPLETED
        job.listing_id = "123456789"
        qm1.save_state()
        
        # Create new manager - should load state
        qm2 = QueueManager(Path(tmpdir))
        
        assert len(qm2.jobs) == 1
        assert qm2.jobs[0].listing_id == "123456789"
        
        print("  ✅ Pass: State persistence works")


def test_retry_failed():
    """Test retrying failed jobs"""
    print("Test: Retry Failed...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        qm = QueueManager(Path(tmpdir))
        
        folder = Path(tmpdir) / "failed_item"
        folder.mkdir()
        
        job = qm.add_folder(str(folder))
        job.status = JobStatus.FAILED
        job.error_message = "Test error"
        job.attempts = 1
        
        qm.retry_failed()
        
        assert job.status == JobStatus.PENDING
        assert job.error_message is None
        
        print("  ✅ Pass: Retry failed works")


def test_clear_completed():
    """Test clearing completed jobs"""
    print("Test: Clear Completed...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        qm = QueueManager(Path(tmpdir))
        
        for i in range(3):
            f = Path(tmpdir) / f"item{i}"
            f.mkdir()
            qm.add_folder(str(f))
        
        qm.jobs[0].status = JobStatus.COMPLETED
        qm.jobs[1].status = JobStatus.FAILED
        
        qm.clear_completed()
        
        assert len(qm.jobs) == 2  # Only pending and failed remain
        assert qm.get_stats()['completed'] == 0
        
        print("  ✅ Pass: Clear completed works")


def test_stats():
    """Test queue statistics"""
    print("Test: Queue Stats...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        qm = QueueManager(Path(tmpdir))
        
        for i in range(4):
            f = Path(tmpdir) / f"item{i}"
            f.mkdir()
            qm.add_folder(str(f))
        
        qm.jobs[0].status = JobStatus.COMPLETED
        qm.jobs[1].status = JobStatus.FAILED
        qm.jobs[2].status = JobStatus.PROCESSING
        
        stats = qm.get_stats()
        
        assert stats['total'] == 4
        assert stats['completed'] == 1
        assert stats['failed'] == 1
        assert stats['processing'] == 1
        assert stats['pending'] == 1
        
        print("  ✅ Pass: Stats calculated correctly")


def test_mock_processing():
    """Test processing with a mock processor"""
    print("Test: Mock Processing...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        qm = QueueManager(Path(tmpdir))
        
        folder = Path(tmpdir) / "process_test"
        folder.mkdir()
        
        qm.add_folder(str(folder))
        
        # Mock processor that returns success
        def mock_processor(path):
            return {
                "success": True,
                "listing_id": "MOCK123",
                "status": "published",
                "timing": {"total": 1.5}
            }
        
        qm.set_processor(mock_processor)
        
        # Process synchronously for testing
        qm._process_job(qm.jobs[0])
        
        assert qm.jobs[0].status == JobStatus.COMPLETED
        assert qm.jobs[0].listing_id == "MOCK123"
        
        print("  ✅ Pass: Mock processing works")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("QUEUE MANAGER TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        test_add_jobs,
        test_add_batch,
        test_state_persistence,
        test_retry_failed,
        test_clear_completed,
        test_stats,
        test_mock_processing
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
