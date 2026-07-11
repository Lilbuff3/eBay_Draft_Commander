"""Queue worker regression tests.

- _process_job failure path must not raise UnboundLocalError on `elapsed`
  (it previously crashed the worker iteration and skipped on_job_error).
- get_stats must report scheduled jobs in their own bucket, and progress
  consumers must count them as done.
"""
from unittest.mock import patch, MagicMock

from backend.app.services.queue_manager import QueueManager, JobStatus


def _make_job_folder(tmp_path, name='item1'):
    folder = tmp_path / 'inbox' / name
    folder.mkdir(parents=True)
    (folder / 'photo_1.jpg').write_bytes(b'\xff\xd8\xff\xe0fakejpg')
    return folder


class TestProcessJobFailurePath:
    def test_failure_path_does_not_crash_batch_stats(self, tmp_path):
        qm = QueueManager(base_path=tmp_path)
        job = qm.add_folder(str(_make_job_folder(tmp_path)))
        assert job is not None

        qm._reset_batch_stats()  # active batch → the elapsed append executes

        with patch('backend.app.services.processor_service.ProcessorService') as ps_cls:
            ps_cls.return_value.create_listing.side_effect = RuntimeError('boom')
            qm._process_job(job)  # must not raise UnboundLocalError

        assert job.status == JobStatus.FAILED
        assert job.error_message == 'boom'
        assert len(qm._batch_stats['item_times']) == 1
        assert qm._batch_stats['failed'] == 1


class TestSchedulingStats:
    def test_get_stats_reports_scheduled_bucket(self, tmp_path):
        qm = QueueManager(base_path=tmp_path)
        j1 = qm.add_folder(str(_make_job_folder(tmp_path, 'a')))
        j2 = qm.add_folder(str(_make_job_folder(tmp_path, 'b')))
        qm.update_job(j1.id, {'status': JobStatus.SCHEDULED})
        qm.update_job(j2.id, {'status': JobStatus.COMPLETED})

        stats = qm.get_stats()
        assert stats['scheduled'] == 1
        assert stats['completed'] == 1
        assert stats['total'] == 2
