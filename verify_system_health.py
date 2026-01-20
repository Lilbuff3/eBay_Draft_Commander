"""
Comprehensive System Health Verification Script
Runs all backend, API, and frontend checks for eBay Draft Commander.
"""
import sys
import subprocess
import json
import requests
import time
from pathlib import Path

# ========================
# CONFIGURATION
# ========================
PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SERVER_URL = "http://localhost:5000"

# ========================
# RESULTS TRACKING
# ========================
results = {
    "backend_tests": {"passed": 0, "failed": 0, "details": []},
    "api_tests": {"passed": 0, "failed": 0, "details": []},
    "frontend_tests": {"passed": 0, "failed": 0, "details": []},
}

def log_result(category: str, test_name: str, passed: bool, message: str = ""):
    """Log a test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}: {test_name}")
    if message and not passed:
        print(f"         └─ {message}")
    results[category]["passed" if passed else "failed"] += 1
    results[category]["details"].append({
        "test": test_name,
        "passed": passed,
        "message": message
    })

# ========================
# BACKEND TESTS
# ========================
def run_backend_tests():
    """Run queue manager unit tests."""
    print("\n" + "=" * 60)
    print("BACKEND LOGIC TESTS")
    print("=" * 60)
    
    try:
        import os
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(
            [sys.executable, "test_queue_manager.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        
        # Parse output for pass/fail count
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        
        # Look for results line
        results_line = ""
        for line in output.split('\n'):
            if "RESULTS:" in line:
                results_line = line.strip()
                break
        
        if passed:
            log_result("backend_tests", "Queue Manager Suite", True, results_line)
        else:
            log_result("backend_tests", "Queue Manager Suite", False, 
                      results_line or output[-200:])
                      
    except subprocess.TimeoutExpired:
        log_result("backend_tests", "Queue Manager Suite", False, "Timeout after 60s")
    except Exception as e:
        log_result("backend_tests", "Queue Manager Suite", False, str(e))

# ========================
# API CONNECTIVITY TESTS
# ========================
def run_api_tests():
    """Test eBay API connectivity and local server endpoints."""
    print("\n" + "=" * 60)
    print("API CONNECTIVITY TESTS")
    print("=" * 60)
    
    # Test 1: Local server /api/status
    try:
        resp = requests.get(f"{SERVER_URL}/api/status", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            log_result("api_tests", "Local Server /api/status", True)
        else:
            log_result("api_tests", "Local Server /api/status", False, f"HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        log_result("api_tests", "Local Server /api/status", False, "Server not running")
    except Exception as e:
        log_result("api_tests", "Local Server /api/status", False, str(e))
    
    # Test 2: eBay Status Endpoint
    try:
        resp = requests.get(f"{SERVER_URL}/api/ebay/status", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "unknown")
            if status == "connected":
                log_result("api_tests", "eBay Connection Status", True, "Token Valid")
            else:
                log_result("api_tests", "eBay Connection Status", False, f"Status: {status}")
        else:
            log_result("api_tests", "eBay Connection Status", False, f"HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        log_result("api_tests", "eBay Connection Status", False, "Server not running")
    except Exception as e:
        log_result("api_tests", "eBay Connection Status", False, str(e))
    
    # Test 3: eBay Policies (safe read-only API call)
    try:
        from ebay_policies import get_fulfillment_policies
        
        policies = get_fulfillment_policies()
        if len(policies) > 0:
            log_result("api_tests", "eBay Fulfillment Policies", True, f"{len(policies)} policies found")
        else:
            log_result("api_tests", "eBay Fulfillment Policies", False, "No policies returned (check token)")
    except Exception as e:
        log_result("api_tests", "eBay Fulfillment Policies", False, str(e))

    # Test 4: Jobs endpoint
    try:
        resp = requests.get(f"{SERVER_URL}/api/jobs", timeout=5)
        if resp.status_code == 200:
            jobs = resp.json()
            log_result("api_tests", "Local Server /api/jobs", True, f"{len(jobs)} jobs in queue")
        else:
            log_result("api_tests", "Local Server /api/jobs", False, f"HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        log_result("api_tests", "Local Server /api/jobs", False, "Server not running")
    except Exception as e:
        log_result("api_tests", "Local Server /api/jobs", False, str(e))

# ========================
# FRONTEND TESTS
# ========================
def run_frontend_tests():
    """Verify frontend build and PWA assets."""
    print("\n" + "=" * 60)
    print("FRONTEND INTEGRITY TESTS")
    print("=" * 60)
    
    # Test 1: NPM Build
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=FRONTEND_DIR,
            capture_output=True,
            text=True,
            timeout=120,
            shell=True  # Required on Windows
        )
        if result.returncode == 0:
            log_result("frontend_tests", "Vite Build (npm run build)", True)
        else:
            error_snippet = (result.stderr or result.stdout)[-300:]
            log_result("frontend_tests", "Vite Build (npm run build)", False, error_snippet)
    except subprocess.TimeoutExpired:
        log_result("frontend_tests", "Vite Build (npm run build)", False, "Timeout after 120s")
    except Exception as e:
        log_result("frontend_tests", "Vite Build (npm run build)", False, str(e))
    
    # Test 2: Manifest.json exists
    manifest_path = FRONTEND_DIR / "public" / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            has_name = "name" in manifest
            has_icons = "icons" in manifest and len(manifest["icons"]) > 0
            if has_name and has_icons:
                log_result("frontend_tests", "PWA Manifest (manifest.json)", True)
            else:
                log_result("frontend_tests", "PWA Manifest (manifest.json)", False, "Missing name or icons")
        except json.JSONDecodeError:
            log_result("frontend_tests", "PWA Manifest (manifest.json)", False, "Invalid JSON")
    else:
        log_result("frontend_tests", "PWA Manifest (manifest.json)", False, "File not found")
    
    # Test 3: Service Worker exists
    sw_path = FRONTEND_DIR / "public" / "sw.js"
    if sw_path.exists():
        log_result("frontend_tests", "Service Worker (sw.js)", True)
    else:
        log_result("frontend_tests", "Service Worker (sw.js)", False, "File not found")

# ========================
# REPORT GENERATION
# ========================
def generate_report():
    """Print final summary report."""
    print("\n" + "=" * 60)
    print("SYSTEM HEALTH SUMMARY")
    print("=" * 60)
    
    total_passed = sum(r["passed"] for r in results.values())
    total_failed = sum(r["failed"] for r in results.values())
    
    for category, data in results.items():
        cat_name = category.replace("_", " ").title()
        status = "✅" if data["failed"] == 0 else "❌"
        print(f"{status} {cat_name}: {data['passed']} passed, {data['failed']} failed")
    
    print("-" * 60)
    overall = "HEALTHY ✅" if total_failed == 0 else f"ISSUES FOUND ❌ ({total_failed} failures)"
    print(f"OVERALL STATUS: {overall}")
    print("=" * 60)
    
    return total_failed == 0

# ========================
# MAIN
# ========================
if __name__ == "__main__":
    print("=" * 60)
    print("eBay Draft Commander - System Health Check")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    run_backend_tests()
    run_api_tests()
    run_frontend_tests()
    
    success = generate_report()
    sys.exit(0 if success else 1)
