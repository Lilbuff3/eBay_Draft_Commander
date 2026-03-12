
import pytest
import shutil
from pathlib import Path
from backend.app import create_app
from backend.app.services.queue_manager import QueueManager
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_deps():
    # Patch dependencies that interact with external services or file system deeply if needed
    # For this test, we mostly rely on temp dirs, so simple qm is enough.
    pass

@pytest.fixture
def test_client(tmp_path):
    # Setup a real QueueManager on a temp path
    qm = QueueManager(base_path=tmp_path)
    app = create_app(queue_manager=qm)
    app.config['TESTING'] = True
    app.config['INBOX_DIR'] = tmp_path / "inbox"
    app.config['INBOX_DIR'].mkdir(exist_ok=True)
    
    with app.test_client() as client:
        yield client

def test_add_single_folder(test_client, tmp_path):
    """Test adding a single folder with images"""
    # Create valid item folder
    item_folder = tmp_path / "inbox" / "Item1"
    item_folder.mkdir(parents=True)
    (item_folder / "photo1.jpg").touch()
    
    # Call Endpoint
    resp = test_client.post('/api/add-folder', json={
        'path': str(item_folder)
    })
    
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] == True
    assert data['count'] == 1
    assert len(data['jobIds']) == 1

def test_add_batch_folder(test_client, tmp_path):
    """Test adding a parent folder with multiple item subfolders"""
    # Create batch structure inside authorized inbox
    batch_folder = tmp_path / "inbox" / "Batch"
    batch_folder.mkdir()
    
    # Item A (Valid)
    item_a = batch_folder / "Item A"
    item_a.mkdir()
    (item_a / "a.jpg").touch()
    
    # Item B (Valid)
    item_b = batch_folder / "Item B"
    item_b.mkdir()
    (item_b / "b.png").touch()
    
    # Empty Folder (Should be ignored)
    item_c = batch_folder / "Empty"
    item_c.mkdir()
    
    # Call Endpoint
    resp = test_client.post('/api/add-folder', json={
        'path': str(batch_folder)
    })
    
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['success'] == True
    assert data['count'] == 2 # Only A and B
    assert len(data['jobIds']) == 2
    
def test_add_invalid_path(test_client):
    # Path outside of authorized root should return 403 Forbidden now
    resp = test_client.post('/api/add-folder', json={
        'path': "C:/fake/path/does/not/exist"
    })
    assert resp.status_code == 403
