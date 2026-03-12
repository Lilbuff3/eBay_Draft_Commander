
import sys
import os
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import Flask

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.services.queue_manager import QueueManager, JobStatus
from backend.app.blueprints.api.queue_api import queue_bp

def test_batch_summary_api():
    print("Testing Backend Batch Summary API...")
    tmpdir = tempfile.mkdtemp()
    try:
        # 1. Setup QueueManager with Batch ID
        qm = QueueManager(Path(tmpdir))
        batch_id = "test_batch_123"
        
        # 2. Add jobs to specific batch
        job1 = qm.add_folder(str(Path(tmpdir) / "item1"), batch_id=batch_id)
        job2 = qm.add_folder(str(Path(tmpdir) / "item2"), batch_id=batch_id)
        
        # 3. Update jobs to simulate completion
        qm.update_job(job1.id, {
            'status': JobStatus.COMPLETED,
            'price': '19.99',
            'timing': {'total': 5.5}
        })
        qm.update_job(job2.id, {
            'status': JobStatus.FAILED,
            'timing': {'total': 3.2}
        })
        
        # 4. Test service layer calculation
        summary = qm.get_batch_summary(batch_id)
        print(f"Summary: {summary}")
        
        assert summary['total_processed'] == 2
        assert summary['succeeded'] == 1
        assert summary['failed'] == 1
        assert summary['total_value_listed'] == 19.99
        assert summary['average_processing_time_seconds'] == 4.35
        print("  PASS: Service layer calculation correct")
        
        # 5. Test API layer via Flask Test Client
        app = Flask(__name__)
        app.queue_manager = qm
        app.register_blueprint(queue_bp, url_prefix='/api/queue')
        
        with app.test_client() as client:
            response = client.get(f'/api/queue/batch-summary/{batch_id}')
            assert response.status_code == 200
            data = response.get_json()
            print(f"API Response: {data}")
            assert data['total_value_listed'] == 19.99
            
        print("  PASS: API endpoint correctly wired")
        
    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    test_batch_summary_api()
