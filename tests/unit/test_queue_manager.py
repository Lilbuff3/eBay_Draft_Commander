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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import patch
from backend.app.services.queue_manager import QueueManager, QueueJob, JobStatus


@patch('backend.app.services.queue_manager.get_data_dir')
def test_add_jobs(mock_get_data_dir):
    """Test adding jobs to queue"""
    print("Test: Adding Jobs...")

    tmpdir = tempfile.mkdtemp()
    try:
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

        all_jobs = qm.get_all_jobs()
        assert len(all_jobs) == 2, f"Expected 2 jobs, got {len(all_jobs)}"
        assert job1.status == JobStatus.PENDING
        assert job2.folder_name == "item2"

        print("  PASS: Jobs added correctly")
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

        print("  PASS: Batch add works")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_state_persistence(mock_get_data_dir):
    """Test saving and loading queue state via update_job()"""
    print("Test: State Persistence...")

    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm1 = QueueManager(Path(tmpdir))

        folder = Path(tmpdir) / "test_item"
        folder.mkdir()

        job = qm1.add_folder(str(folder))

        # Use update_job() to persist changes (the correct pattern)
        qm1.update_job(job.id, {
            'status': JobStatus.COMPLETED,
            'listing_id': '123456789',
        })

        # Force release of DB connection
        import gc
        gc.collect()

        # Create new manager - should load state
        qm2 = QueueManager(Path(tmpdir))

        all_jobs = qm2.get_all_jobs()
        assert len(all_jobs) == 1
        assert all_jobs[0].listing_id == "123456789"
        assert all_jobs[0].status == JobStatus.COMPLETED

        print("  PASS: State persistence works")
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

        # Set job to failed state via DB
        qm.update_job(job.id, {
            'status': JobStatus.FAILED,
            'error_message': 'Test error',
            'attempts': 1,
        })

        count = qm.retry_failed()
        assert count == 1

        # Verify the job is now pending in DB
        reloaded = qm.get_job_by_id(job.id)
        assert reloaded.status == JobStatus.PENDING
        assert reloaded.error_message is None

        print("  PASS: Retry failed works")
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

        job_ids = []
        for i in range(3):
            f = Path(tmpdir) / f"item{i}"
            f.mkdir()
            job = qm.add_folder(str(f))
            job_ids.append(job.id)

        # Set statuses via DB
        qm.update_job(job_ids[0], {'status': JobStatus.COMPLETED})
        qm.update_job(job_ids[1], {'status': JobStatus.FAILED})
        # job_ids[2] stays PENDING

        qm.clear_completed()

        all_jobs = qm.get_all_jobs()
        assert len(all_jobs) == 2  # Only pending and failed remain
        assert qm.get_stats()['completed'] == 0

        print("  PASS: Clear completed works")
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

        job_ids = []
        for i in range(4):
            f = Path(tmpdir) / f"item{i}"
            f.mkdir()
            job = qm.add_folder(str(f))
            job_ids.append(job.id)

        # Set statuses via DB
        qm.update_job(job_ids[0], {'status': JobStatus.COMPLETED})
        qm.update_job(job_ids[1], {'status': JobStatus.FAILED})
        qm.update_job(job_ids[2], {'status': JobStatus.PROCESSING})
        # job_ids[3] stays PENDING

        stats = qm.get_stats()

        assert stats['total'] == 4
        assert stats['completed'] == 1
        assert stats['failed'] == 1
        assert stats['processing'] == 1
        assert stats['pending'] == 1

        print("  PASS: Stats calculated correctly")
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

        job = qm.add_folder(str(folder))

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
            qm._process_job(job)

        # Verify result is persisted in DB
        reloaded = qm.get_job_by_id(job.id)
        assert reloaded.status == JobStatus.COMPLETED
        assert reloaded.listing_id == "MOCK123"

        print("  PASS: Mock processing works")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_update_job_persists(mock_get_data_dir):
    """Test that update_job() correctly persists to database"""
    print("Test: update_job() persistence...")

    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))

        folder = Path(tmpdir) / "update_test"
        folder.mkdir()

        job = qm.add_folder(str(folder))

        # Update multiple fields at once
        qm.update_job(job.id, {
            'user_title': 'Test Title',
            'user_price': '19.99',
            'user_description': 'A test description',
            'user_condition': 'USED_GOOD',
            'item_specifics': {'Brand': 'TestBrand', 'Color': 'Blue'},
        })

        # Reload from DB and verify
        reloaded = qm.get_job_by_id(job.id)
        assert reloaded.user_title == 'Test Title'
        assert reloaded.user_price == '19.99'
        assert reloaded.user_description == 'A test description'
        assert reloaded.user_condition == 'USED_GOOD'
        assert reloaded.item_specifics == {'Brand': 'TestBrand', 'Color': 'Blue'}

        print("  PASS: update_job() persists correctly")
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_update_job_survives_restart(mock_get_data_dir):
    """Test that user edits survive a QueueManager restart (the bug we fixed)"""
    print("Test: Edits survive restart...")

    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm1 = QueueManager(Path(tmpdir))

        folder = Path(tmpdir) / "restart_test"
        folder.mkdir()

        job = qm1.add_folder(str(folder))

        # Simulate a user edit
        qm1.update_job(job.id, {
            'user_title': 'My Custom Title',
            'user_price': '42.00',
        })

        # Simulate restart
        import gc
        gc.collect()
        qm2 = QueueManager(Path(tmpdir))

        # Edits should survive
        reloaded = qm2.get_job_by_id(job.id)
        assert reloaded.user_title == 'My Custom Title', \
            f"Expected 'My Custom Title', got '{reloaded.user_title}'"
        assert reloaded.user_price == '42.00', \
            f"Expected '42.00', got '{reloaded.user_price}'"

        print("  PASS: Edits survive restart")
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
        test_mock_processing,
        test_update_job_persists,
        test_update_job_survives_restart,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)


@patch('backend.app.services.queue_manager.get_data_dir')
def test_purge_missing_folders(mock_get_data_dir):
    """Jobs whose folder no longer exists on disk get purged; live jobs stay."""
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))

        keep = Path(tmpdir) / "still-here"
        keep.mkdir()
        gone = Path(tmpdir) / "deleted-later"
        gone.mkdir()

        kept_job = qm.add_folder(str(keep))
        dead_job = qm.add_folder(str(gone))
        shutil.rmtree(gone)

        result = qm.purge_missing_folders()

        assert result['count'] == 1
        remaining = [j.id for j in qm.get_all_jobs()]
        assert kept_job.id in remaining
        assert dead_job.id not in remaining
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


@patch('backend.app.services.queue_manager.get_data_dir')
def test_purge_missing_folders_never_touches_active(mock_get_data_dir):
    """A processing job is never purged even if its folder vanished mid-run."""
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))

        f = Path(tmpdir) / "in-flight"
        f.mkdir()
        job = qm.add_folder(str(f))
        qm.update_job(job.id, {'status': JobStatus.PROCESSING})
        shutil.rmtree(f)

        result = qm.purge_missing_folders()

        assert result['count'] == 0
        assert [j.id for j in qm.get_all_jobs()] == [job.id]
    finally:
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass


def test_base_path_isolates_database(tmp_path):
    """QueueManager(base_path=...) must keep its database under base_path.

    Regression: base_path was ignored for db_path, so tests passing
    base_path=tmp_path silently wrote job rows into the real data/commander.db.
    Intentionally does NOT patch get_data_dir — isolation must come from base_path.
    """
    qm = QueueManager(base_path=tmp_path)
    assert qm.db_path.is_relative_to(tmp_path), (
        f"db_path {qm.db_path} escaped base_path {tmp_path}"
    )


@patch('backend.app.services.queue_manager.get_data_dir')
def test_remove_job_allows_pending_review(mock_get_data_dir):
    """A draft awaiting review must be deletable (user discards a bad result)."""
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))
        f = Path(tmpdir) / "review-item"
        f.mkdir()
        job = qm.add_folder(str(f))
        qm.update_job(job.id, {'status': JobStatus.PENDING_REVIEW})

        assert qm.remove_job(job.id) is True
        assert job.id not in [j.id for j in qm.get_all_jobs()]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@patch('backend.app.services.queue_manager.get_data_dir')
def test_remove_job_allows_completed(mock_get_data_dir):
    """Completed jobs can be removed from the dashboard."""
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))
        f = Path(tmpdir) / "done-item"
        f.mkdir()
        job = qm.add_folder(str(f))
        qm.update_job(job.id, {'status': JobStatus.COMPLETED})

        assert qm.remove_job(job.id) is True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@patch('backend.app.services.queue_manager.get_data_dir')
def test_remove_job_blocks_actively_processing(mock_get_data_dir):
    """A job that is actively processing must NOT be deletable mid-run."""
    tmpdir = tempfile.mkdtemp()
    try:
        mock_get_data_dir.return_value = Path(tmpdir)
        qm = QueueManager(Path(tmpdir))
        f = Path(tmpdir) / "running-item"
        f.mkdir()
        job = qm.add_folder(str(f))
        qm.update_job(job.id, {'status': JobStatus.PROCESSING})

        assert qm.remove_job(job.id) is False
        assert job.id in [j.id for j in qm.get_all_jobs()]
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
