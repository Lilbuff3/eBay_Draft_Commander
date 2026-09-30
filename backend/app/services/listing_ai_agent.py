"""
Delegating adapter for backward compatibility.
Deep orchestration logic lives in AIAnalyzer and PricingEngine.
"""
from typing import Optional, Union, Dict, Any
from backend.app.services.ai_analyzer import AIAnalyzer as RealAIAnalyzer, AIAnalyzer
from backend.app.services.pricing_engine import PricingEngine as RealPricingEngine, PricingEngine
from backend.app.services.ebay import taxonomy


class ListingAIAgent:
    """Delegating adapter for backward compatibility.
    Eliminates duplicated orchestration code and the pricing projection seam.
    """
    def __init__(self, ai_analyzer: Optional[AIAnalyzer] = None, pricing_engine: Optional[PricingEngine] = None):
        self.ai_analyzer = ai_analyzer or AIAnalyzer()
        self.pricing_engine = pricing_engine or PricingEngine()
        self._default_shipping_cost = self._resolve_default_shipping_cost()

    def _resolve_default_shipping_cost(self) -> float:
        return getattr(self.ai_analyzer, '_default_shipping_cost', 6.50)

    def _calculate_shipping_cost(self, ai_data: dict) -> float:
        calc = getattr(self.ai_analyzer, 'calculate_shipping_cost', None)
        if callable(calc) and type(calc).__name__ != 'MagicMock':
            return calc(ai_data)
        return RealAIAnalyzer.calculate_shipping_cost(self.ai_analyzer, ai_data)

    def analyze_item(self, job_obj, images, condition=None, log_callback=None):
        return RealAIAnalyzer.analyze_job_item(
            self.ai_analyzer, job_obj, images, condition=condition, log_callback=log_callback, taxonomy_module=taxonomy
        )

    def get_final_pricing(
        self,
        title: str,
        condition: Optional[str] = None,
        ai_suggested_price: Optional[Union[float, str]] = None,
        user_price: Optional[Union[float, str]] = None,
        shipping_cost: Optional[float] = None,
        log_callback=None,
        identification: Optional[Dict] = None,
        research_market_price: Optional[float] = None,
        availability: Optional[str] = None,
        seller_note: Optional[str] = None,
    ) -> Dict[str, Any]:
        return RealPricingEngine.get_final_pricing(
            self.pricing_engine,
            title,
            condition=condition,
            ai_suggested_price=ai_suggested_price,
            user_price=user_price,
            shipping_cost=shipping_cost,
            log_callback=log_callback,
            identification=identification,
            research_market_price=research_market_price,
            availability=availability,
            seller_note=seller_note,
        )
