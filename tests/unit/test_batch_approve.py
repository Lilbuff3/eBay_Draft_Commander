"""
Tests for Fix 1: Batch-approve should set user_approved=True in job_metadata.

Without this fix, approved items loop back to pending_review because
the processor_service checks user_approved before allowing publish.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager, JobStatus


def _make_mock_job(job_id, status='pending_review', metadata=None):
    """Create a mock job for batch-approve testing."""
    job = MagicMock()
    job.id = job_id
    job.status = status
    job.job_metadata = metadata or {}
    return job


@pytest.fixture
def app_client(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    # No config['QUEUE_MANAGER'] injection: production only sets
    # app.queue_manager, and the endpoint must work through that attribute.
    return app, app.test_client(), qm


class TestBatchApprove:
    """Batch approve should set user_approved=True on each job."""

    def test_batch_approve_sets_user_approved(self, app_client):
        """After batch approve, job_metadata should have user_approved=True."""
        app, client, qm = app_client

        mock_job = _make_mock_job('abc123', status='pending_review')

        # Track what update_job receives
        captured_updates = []
        original_update = qm.update_job

        def tracking_update(job_id, updates):
            captured_updates.append((job_id, updates))
            return True

        with app.app_context():
            with patch.object(qm, 'get_job_by_id', return_value=mock_job), \
                 patch.object(qm, 'update_job', side_effect=tracking_update), \
                 patch.object(qm, 'is_processing', return_value=True):

                response = client.post('/api/listings/batch-approve', json={
                    'listing_ids': ['abc123']
                })
                data = json.loads(response.data)

                assert data['success'] is True
                assert data['approved_count'] == 1

                # The update should include user_approved in metadata
                found_user_approved = False
                for job_id, updates in captured_updates:
                    if job_id == 'abc123':
                        meta = updates.get('job_metadata', {})
                        if meta.get('user_approved') is True:
                            found_user_approved = True

                assert found_user_approved, \
                    "Batch approve must set user_approved=True in job_metadata"

    def test_batch_approve_preserves_existing_metadata(self, app_client):
        """Existing metadata fields should not be lost when adding user_approved."""
        app, client, qm = app_client

        existing_meta = {'ordered_images': ['img1.jpg', 'img2.jpg'], 'custom_field': 'value'}
        mock_job = _make_mock_job('def456', status='pending_review', metadata=existing_meta)

        captured_updates = []

        def tracking_update(job_id, updates):
            captured_updates.append((job_id, updates))
            return True

        with app.app_context():
            with patch.object(qm, 'get_job_by_id', return_value=mock_job), \
                 patch.object(qm, 'update_job', side_effect=tracking_update), \
                 patch.object(qm, 'is_processing', return_value=True):

                response = client.post('/api/listings/batch-approve', json={
                    'listing_ids': ['def456']
                })
                data = json.loads(response.data)

                assert data['success'] is True

                # Find the update that has metadata
                for job_id, updates in captured_updates:
                    if job_id == 'def456' and 'job_metadata' in updates:
                        meta = updates['job_metadata']
                        assert meta.get('user_approved') is True
                        assert meta.get('ordered_images') == ['img1.jpg', 'img2.jpg'], \
                            "Existing metadata should be preserved"
                        assert meta.get('custom_field') == 'value'
                        break
                else:
                    pytest.fail("No update with job_metadata found")
