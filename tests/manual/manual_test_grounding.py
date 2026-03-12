from pricing_engine import PricingEngine
import json

def test_gemini3_grounding():
    print("Testing Gemini 3 Search Grounding in Pricing Engine...\n")
    engine = PricingEngine()
    
    # Use a niche item that might not be in recent eBay sold history
    # but exists in the real world
    test_title = "Sony Alpha 9 III Mirrorless Camera with Global Shutter"
    test_condition = "New"
    
    print(f"Item: {test_title}")
    
    # We deliberately don't provide ai_suggested_price to force grounding if market data fails
    result = engine.get_price_with_comps(test_title, test_condition)
    
    print("-" * 50)
    print(f"Suggested Price: ${result['suggested_price']}" if result['suggested_price'] else "No price suggestion")
    print(f"Source: {result['source']}")
    print(f"Reasoning: {result['reasoning']}")
    
    if result['source'] == 'ai_grounded_research':
        print("\n✅ Gemini 3 Search Grounding successfully retrieved research data!")
    elif result['source'] == 'market_data':
         print("\n✅ Found market data on eBay!")
    else:
        print("\n❌ Failed to get grounded price estimation.")

if __name__ == "__main__":
    test_gemini3_grounding()
