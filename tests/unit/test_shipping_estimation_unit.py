import sys
import os
from pathlib import Path

# Add project root to sys.path
# File is at root/tests/test_...py, so parents[1] is root
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from backend.app.services.listing_ai_agent import ListingAIAgent

def test_shipping_estimation():
    print("=== Testing Shipping Estimation Logic ===")
    agent = ListingAIAgent()
    
    # Mock data sets
    tests = [
        {
            "name": "Light Item (Small size)",
            "ai_data": {"identification": {"package_size": "small", "estimated_weight_lbs": 0.5}},
            "expected": 4.50
        },
        {
            "name": "Medium Item (1.5 lbs)",
            "ai_data": {"identification": {"package_size": "medium", "estimated_weight_lbs": 1.5}},
            "expected": 6.50
        },
        {
            "name": "Heavy Item (Board Game, 5 lbs)",
            "ai_data": {"identification": {"package_size": "large", "estimated_weight_lbs": 5.0}},
            "expected": 10.00
        },
        {
            "name": "Very Heavy Item (12 lbs)",
            "ai_data": {"identification": {"package_size": "heavy", "estimated_weight_lbs": 12.0}},
            "expected": 15.00
        },
        {
            "name": "Size Missing, Weight provided (8 lbs)",
            "ai_data": {"identification": {"estimated_weight_lbs": 8.0}},
            "expected": 10.00
        },
        {
            "name": "Weight < 1lb, Size missing",
            "ai_data": {"identification": {"estimated_weight_lbs": 0.8}},
            "expected": 4.50
        },
        {
            "name": "Both Missing (Fallback)",
            "ai_data": {"identification": {}},
            "expected": agent._default_shipping_cost
        }
    ]
    
    passed = 0
    for t in tests:
        actual = agent._calculate_shipping_cost(t['ai_data'])
        if actual == t['expected']:
            print(f"✅ {t['name']}: ${actual:.2f}")
            passed += 1
        else:
            print(f"❌ {t['name']}: Expected ${t['expected']:.2f}, got ${actual:.2f}")
            
    print(f"\nPassed {passed}/{len(tests)} tests.")
    return passed == len(tests)

if __name__ == "__main__":
    if test_shipping_estimation():
        print("\nUnit Tests PASSED")
        sys.exit(0)
    else:
        print("\nUnit Tests FAILED")
        sys.exit(1)
