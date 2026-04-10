
import time
import tempfile
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os

def _delete_folder(folder_path: str) -> bool:
    """Mocking the _delete_folder logic from QueueManager with artificial delay"""
    try:
        p = Path(folder_path)
        if p.exists() and p.is_dir():
            # Simulate disk latency or large folder deletion
            time.sleep(0.01)
            shutil.rmtree(p)
            return True
    except Exception:
        pass
    return False

def setup_benchmark(num_folders=100):
    tmpdir = tempfile.mkdtemp()
    data_dir = Path(tmpdir)

    folder_paths = []
    for i in range(num_folders):
        folder = data_dir / f"item{i}"
        folder.mkdir(parents=True)
        for j in range(5):
            (folder / f"file{j}.txt").write_text("dummy content " * 100)
        folder_paths.append(str(folder))

    return folder_paths, tmpdir

def run_synchronous(folder_paths):
    start_time = time.perf_counter()
    deleted_count = 0
    for path in folder_paths:
        if _delete_folder(path):
            deleted_count += 1
    duration = time.perf_counter() - start_time
    return deleted_count, duration

def run_threaded(folder_paths, max_workers=10):
    start_time = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(_delete_folder, folder_paths))
    deleted_count = sum(1 for r in results if r)
    duration = time.perf_counter() - start_time
    return deleted_count, duration

if __name__ == "__main__":
    num_folders = 50

    # Baseline
    folder_paths, tmpdir = setup_benchmark(num_folders)
    try:
        count, duration = run_synchronous(folder_paths)
        print(f"Synchronous: Deleted {count} folders in {duration:.4f} seconds")
    finally:
        shutil.rmtree(tmpdir)

    # Optimized
    folder_paths, tmpdir = setup_benchmark(num_folders)
    try:
        count, duration = run_threaded(folder_paths)
        print(f"Threaded (10 workers): Deleted {count} folders in {duration:.4f} seconds")
    finally:
        shutil.rmtree(tmpdir)
