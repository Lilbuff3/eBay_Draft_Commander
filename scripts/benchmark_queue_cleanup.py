
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import sys
import os

# Add project to path
sys.path.insert(0, os.getcwd())

from backend.app.services.queue_manager import QueueManager, JobStatus

def setup_benchmark(num_jobs=100):
    tmpdir = tempfile.mkdtemp()
    data_dir = Path(tmpdir)
    qm = QueueManager(data_dir)

    # Create jobs and folders
    for i in range(num_jobs):
        folder = data_dir / "inbox" / f"item{i}"
        folder.mkdir(parents=True)
        # Add some files to make deletion more realistic
        for j in range(5):
            (folder / f"file{j}.txt").write_text("dummy content " * 100)

        job = qm.add_folder(str(folder))
        qm.update_job(job.id, {'status': JobStatus.COMPLETED})

    return qm, tmpdir

def run_benchmark(qm, num_jobs):
    print(f"Benchmarking clear_completed with {num_jobs} jobs...")
    start_time = time.perf_counter()
    result = qm.clear_completed(delete_folders=True)
    end_time = time.perf_counter()

    duration = end_time - start_time
    print(f"Deleted {result['folders_deleted']} folders in {duration:.4f} seconds")
    return duration

if __name__ == "__main__":
    num_jobs = 100
    qm, tmpdir = setup_benchmark(num_jobs)
    try:
        run_benchmark(qm, num_jobs)
    finally:
        shutil.rmtree(tmpdir)
