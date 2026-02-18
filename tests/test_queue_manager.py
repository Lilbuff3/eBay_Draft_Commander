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

from unittest.mock import patch
from backend.app.services.queue_manager import QueueManager, QueueJob, JobStatus

@patch('backend.app.services.queue_manager.get_data_dir')
def test_add_jobs(mock_get_data_dir):
    """Test adding jobs to queue"""
    print("Test: Adding Jobs...")
    
    tmpdir = tempfile.mkdtemp()
    try:
        # Mock get_data_dir to return tmpdir
        mock_get_data_dir.return_value = Path(tmpdir)
        
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
        
        qm.close()
        print("  ✅ Pass: Jobs added correctly")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_add_batch(mock_get_data_dir):
    """Test batch adding"""
    print("Test: Batch Adding...")
    
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))
        
        folders = []
        for i in range(5):
            f = Path(tmpdir) / f"item{i}"
            f.mkdir()
            folders.append(str(f))
        
        jobs = qm.add_batch(folders)
        
        assert len(jobs) == 5
        assert qm.get_stats()['pending'] == 5
        
        qm.close()
        print("  ✅ Pass: Batch add works")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_state_persistence(mock_get_data_dir):
    """Test saving and loading queue state"""
    print("Test: State Persistence...")
    
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm1 = QueueManager(Path(tmpdir))
        
        folder = Path(tmpdir) / "test_item"
        folder.mkdir()
        
        job = qm1.add_folder(str(folder))
        job.status = JobStatus.COMPLETED
        job.listing_id = "123456789"
        qm1.save_state()
        qm1.close()
        
        # Force release of DB connection
        import gc
        gc.collect()
        
        # Create new manager - should load state
        qm2 = QueueManager(Path(tmpdir))
        
        assert len(qm2.jobs) == 1
        assert qm2.jobs[0].listing_id == "123456789"
        
        qm2.close()
        print("  ✅ Pass: State persistence works")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_retry_failed(mock_get_data_dir):
    """Test retrying failed jobs"""
    print("Test: Retry Failed...")
    
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
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
        
        qm.close()
        print("  ✅ Pass: Retry failed works")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_clear_completed(mock_get_data_dir):
    """Test clearing completed jobs"""
    print("Test: Clear Completed...")
    
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
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
        
        qm.close()
        print("  ✅ Pass: Clear completed works")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_stats(mock_get_data_dir):
    """Test queue statistics"""
    print("Test: Queue Stats...")
    
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
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
        
        qm.close()
        print("  ✅ Pass: Stats calculated correctly")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_mock_processing(mock_get_data_dir):
    """Test processing with a mock processor"""
    print("Test: Mock Processing...")
    
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))
        
        folder = Path(tmpdir) / "process_test"
        folder.mkdir()
        
        qm.add_folder(str(folder))
        
        # Mock ProcessorService
        with patch('backend.app.services.processor_service.ProcessorService') as MockService:
            mock_instance = MockService.return_value
            mock_instance.create_listing.return_value = {
                "success": True,
                "listing_id": "MOCK123",
                "status": "published",
                "timing": {"total": 1.5}
            }
            
            # Process synchronously for testing
            qm._process_job(qm.jobs[0])
        
        assert qm.jobs[0].status == JobStatus.COMPLETED
        assert qm.jobs[0].listing_id == "MOCK123"
        
        qm.close()
        print("  ✅ Pass: Mock processing works")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


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
