
import sys
import subprocess
from pathlib import Path

def run_all_tests():
    print("=" * 60)
    print("RUNNING ALL AUTOMATED TESTS")
    print("=" * 60)
    
    project_root = Path(__file__).parent.absolute()
    
    # 1. Backend Tests
    print("\n" + "-" * 30)
    print("BACKEND TESTS (pytest)")
    print("-" * 30)
    backend_script = project_root / "scripts" / "run_tests_backend.py"
    
    try:
        backend_result = subprocess.run(
            [sys.executable, str(backend_script)], 
            cwd=str(project_root),
            check=False
        )
        backend_success = backend_result.returncode == 0
    except Exception as e:
        print(f"Failed to run backend tests: {e}")
        backend_success = False
        
    # 2. Frontend Tests
    print("\n" + "-" * 30)
    print("FRONTEND TESTS (vitest)")
    print("-" * 30)
    frontend_dir = project_root / "frontend"
    
    try:
        # Use shell=True for npm on Windows to find the executable
        frontend_result = subprocess.run(
            ["npm", "run", "test", "--", "--run"], 
            cwd=str(frontend_dir),
            shell=True,
            check=False
        )
        frontend_success = frontend_result.returncode == 0
    except Exception as e:
        print(f"Failed to run frontend tests: {e}")
        frontend_success = False

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Backend Tests: {'✅ PASS' if backend_success else '❌ FAIL'}")
    print(f"Frontend Tests: {'✅ PASS' if frontend_success else '❌ FAIL'}")
    
    if backend_success and frontend_success:
        print("\nAll tests passed! 🚀")
        return 0
    else:
        print("\nSome tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())
