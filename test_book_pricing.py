
from backend.app.services.pricing_engine import PricingEngine

def test_book_pricing():
    print("📚 Testing Book Pricing Logic...")
    
    engine = PricingEngine()
    
    # K&R C Programming Language
    isbn = "9780131103627" 
    title = "The C Programming Language"
    condition = "Used - Good"
    
    # 1. Test with ISBN (Expected: market_data_isbn)
    print("\n--- TEST 1: With ISBN ---")
    result = engine.get_price_with_comps(title, condition, isbn=isbn)
    
    if result.get('source') == 'market_data_isbn':
        print(f"✅ Success! Used ISBN source. Price: ${result['suggested_price']}")
    else:
        print(f"⚠️ Result source: {result.get('source')}")
        
    # 2. Test without ISBN (Expected: market_data)
    print("\n--- TEST 2: Without ISBN ---")
    result = engine.get_price_with_comps(title, condition)
    
    if result.get('source') == 'market_data':
        print(f"✅ Success! Used Keyword source. Price: ${result['suggested_price']}")

if __name__ == "__main__":
    test_book_pricing()
