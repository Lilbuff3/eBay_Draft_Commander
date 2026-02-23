from flask import jsonify

def error_response(message, code=500, details=None):
    """Standardized error response helper"""
    response = {'success': False, 'error': str(message)}
    if details:
        response['details'] = details
    return jsonify(response), code
