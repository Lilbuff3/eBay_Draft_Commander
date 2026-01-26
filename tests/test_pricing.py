"""Quick test for pricing engine integration"""
from pricing_engine import PricingEngine

engine = PricingEngine()

# Test with mock data (simulating what AI would provide)
test_title = "SVBONY SV28 Spotting Scope 25-75x70mm"
test_condition = "Used - Good"
test_ai_price = "79.99"

result = engine.get_price_with_comps(test_title, test_condition, ai_suggested_price=test_ai_price)

print("=== PRICING ENGINE TEST ===")
print(f"Input Title: {test_title}")
print(f"Input Condition: {test_condition}")
print(f"AI Fallback Price: ${test_ai_price}")
print()
print("OUTPUT:")
print(f"  Suggested Price: ${result['suggested_price']}")
print(f"  Source: {result['source']}")
print(f"  Reasoning: {result['reasoning']}")
print(f"  Research Link: {result['research_link'][:60]}...")
print()
print("✅ Test PASSED" if result['suggested_price'] else "❌ Test FAILED")
