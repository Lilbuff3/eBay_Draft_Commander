
import unittest
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from backend.app.services.pricing_engine import PricingEngine

class TestSmartPricing(unittest.TestCase):
    def setUp(self):
        self.engine = PricingEngine()
        
    def test_condition_multiplier_nos(self):
        # Test NOS multiplier (0.90)
        # Mock comps: 5x $100 items (median $100)
        comps = [{'price': 100.0} for _ in range(5)]
        
        # New Old Stock
        result = self.engine.calculate_suggested_price(comps, "New Old Stock")
        self.assertEqual(result['median_price'], 100.0)
        self.assertEqual(result['multiplier'], 0.90)
        self.assertEqual(result['suggested_price'], 89.99) # 90 -> 89.99 (smart pricing)

    def test_margin_protection(self):
        # Mock comps: Median $30
        comps = [{'price': 30.0} for _ in range(5)]
        
        # Case A: Low acquisition cost ($5) -> Good margin
        # Price ~22.50. Fees ~3.30. Profit ~14.20. (Above min margin $10)
        result_a = self.engine.calculate_suggested_price(comps, "Used - Good", acquisition_cost=5.0)
        # 30 * 0.75 = 22.50
        # Smart pricing -> 21.99 (Python round(22.5) -> 22 - 0.01)
        self.assertEqual(result_a['suggested_price'], 21.99)
        self.assertFalse("Boosted" in result_a['reasoning'])
        
        # Case B: High acquisition cost ($20) -> Low margin
        # Price ~22.50. Fees ~3.30. Profit ~ -0.80. (Below min margin $10)
        # Target = (20 + 10 + 0.30) / (1 - 0.1325) = 30.30 / 0.8675 = 34.93
        result_b = self.engine.calculate_suggested_price(comps, "Used - Good", acquisition_cost=20.0)
        self.assertGreater(result_b['suggested_price'], 30.0)
        self.assertTrue("Boosted" in result_b['reasoning'])
        self.assertGreaterEqual(result_b['projected_profit'], 9.9) # Approx 10

if __name__ == '__main__':
    print("🧪 Testing Smart Pricing Logic...")
    unittest.main()
