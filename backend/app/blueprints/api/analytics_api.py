from flask import Blueprint, jsonify, request
from backend.app.services.ebay_service import eBayService
from backend.app.core.logger import get_logger

analytics_bp = Blueprint('analytics', __name__)
logger = get_logger('api.analytics')
ebay_service = eBayService()

@analytics_bp.route('/sales/recent')
def get_recent_sales():
    result, status = ebay_service.get_recent_sales()
    return jsonify(result), status

@analytics_bp.route('/analytics/summary')
def get_analytics_summary():
    days = request.args.get('days', 30)
    result, status = ebay_service.get_analytics_summary(days=days)
    return jsonify(result), status

@analytics_bp.route('/analytics/orders')
def get_analytics_orders():
    days = request.args.get('days', 30)
    limit = request.args.get('limit', 50)
    result, status = ebay_service.get_recent_orders(days=days, limit=limit)
    return jsonify(result), status
