"""
Tests for /api/scan endpoint.

Verifies that the scan endpoint correctly reads the 'added' key
from scanner_service.scan_inbox() result.
"""

import pytest
from unittest.mock import MagicMock, patch
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager


@pytest.fixture
def app_client(tmp_path):
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    app.config['INBOX_DIR'] = str(tmp_path / 'inbox')
    return app, app.test_client(), qm


class TestScanEndpoint:
    """Verify /api/scan reads the correct key from scanner result."""

    @patch('backend.app.services.scanner_service.ScannerService')
    def test_scan_returns_correct_count(self, MockScannerService, app_client):
        """The endpoint should read 'added' (not 'added_count') from the scanner result."""
        app, client, qm = app_client

        mock_scanner = MagicMock()
        mock_scanner.scan_inbox.return_value = {
            'success': True,
            'added': 3,
            'skipped': 1,
            'total_scanned': 4,
            'batch_id': 'test_batch'
        }
        MockScannerService.return_value = mock_scanner

        response = client.post('/api/scan')
        data = response.get_json()

        assert response.status_code == 200
        assert data['success'] is True
        assert data['count'] == 3
        assert 'Added 3 jobs' in data['message']

    @patch('backend.app.services.scanner_service.ScannerService')
    def test_scan_returns_zero_when_no_jobs_added(self, MockScannerService, app_client):
        """When scanner finds nothing, count should be 0."""
        app, client, qm = app_client

        mock_scanner = MagicMock()
        mock_scanner.scan_inbox.return_value = {
            'success': True,
            'added': 0,
            'skipped': 0,
            'total_scanned': 0,
            'batch_id': 'test_batch'
        }
        MockScannerService.return_value = mock_scanner

        response = client.post('/api/scan')
        data = response.get_json()

        assert response.status_code == 200
        assert data['count'] == 0
        assert 'Added 0 jobs' in data['message']
