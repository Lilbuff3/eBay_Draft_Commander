from flask import jsonify

def error_response(message, code=500, details=None):
    """Standardized error response helper"""
    response = {'success': False, 'error': str(message)}
    if details:
        response['details'] = details
    return jsonify(response), code


def build_pricing_data(ai_data, identification=None):
    """Project a job's flat ai_data pricing_* keys into the nested pricing_data
    shape the frontend price explainer consumes.

    Shared by /api/job/<id>/details and /api/listings/pending so the Review
    queue and the item drawer read the same structure.
    """
    from backend.app.services.pricing_engine import format_price_source

    identification = identification or {}
    # Real key is pricing_comps (written by processor_service); the old
    # 'comparables' key was never written anywhere.
    comps = ai_data.get('pricing_comps', []) or []
    return {
        'confidence': identification.get('confidence_score'),
        'comps': comps[:5],
        'median_price': ai_data.get('pricing_median'),
        'price_range': ai_data.get('pricing_range'),
        'comp_count': ai_data.get('pricing_comp_count'),
        'reasoning': ai_data.get('pricing_reasoning', ''),
        'pricing_confidence': ai_data.get('pricing_confidence'),
        'pricing_confidence_reason': ai_data.get('pricing_confidence_reason'),
        # Raw engine source (e.g. own_sales) for UI badges; label is display copy.
        'source': ai_data.get('pricing_source', ''),
        'price_source': ai_data.get('price_source', 'AI estimate'),
        'price_source_label': format_price_source(
            ai_data.get('pricing_source', ''), comp_count=len(comps)
        ),
        'market_price': ai_data.get('research', {}).get('market_price', {}),
    }
