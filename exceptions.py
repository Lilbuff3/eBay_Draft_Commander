"""
Custom exception hierarchy for eBay Draft Commander.

Provides domain-specific exceptions for better error handling
and more informative error messages.
"""


class DraftCommanderError(Exception):
    """Base exception for all Draft Commander errors"""
    pass


# ============================================================================
# eBay API Exceptions
# ============================================================================

class eBayAPIError(DraftCommanderError):
    """Base exception for eBay API errors"""
    pass


class eBayAuthError(eBayAPIError):
    """eBay authentication/authorization failed"""
    pass


class eBayRateLimitError(eBayAPIError):
    """eBay API rate limit exceeded"""
    pass


class eBayNotFoundError(eBayAPIError):
    """Requested eBay resource not found (404)"""
    pass


class eBayTimeoutError(eBayAPIError):
    """eBay API request timed out"""
    pass


class eBayValidationError(eBayAPIError):
    """eBay rejected request due to validation errors (400)"""
    pass


# ============================================================================
# AI/Image Processing Exceptions
# ============================================================================

class AIAnalysisError(DraftCommanderError):
    """AI analysis failed"""
    pass


class ImageProcessingError(DraftCommanderError):
    """Image processing operation failed"""
    pass


class InvalidImageError(ImageProcessingError):
    """Image file is invalid or corrupted"""
    pass


# ============================================================================
# Queue Management Exceptions
# ============================================================================

class QueueError(DraftCommanderError):
    """Base exception for queue operations"""
    pass


class JobNotFoundError(QueueError):
    """Requested job ID not found in queue"""
    pass


class QueueStateCorruptedError(QueueError):
    """Queue state file is corrupted"""
    pass


# ============================================================================
# Template & Settings Exceptions
# ============================================================================

class TemplateError(DraftCommanderError):
    """Template operation failed"""
    pass


class SettingsError(DraftCommanderError):
    """Settings operation failed"""
    pass


# ============================================================================
# Helper Functions
# ============================================================================

def from_http_status(status_code: int, message: str = None) -> eBayAPIError:
    """
    Create appropriate eBay exception from HTTP status code.
    
    Args:
        status_code: HTTP status code from eBay API
        message: Optional custom error message
        
    Returns:
        Appropriate eBayAPIError subclass
        
    Example:
        if response.status_code != 200:
            raise from_http_status(response.status_code, response.text)
    """
    msg = message or f"eBay API returned status {status_code}"
    
    if status_code == 401:
        return eBayAuthError(msg)
    elif status_code == 404:
        return eBayNotFoundError(msg)
    elif status_code == 429:
        return eBayRateLimitError(msg)
    elif status_code == 400:
        return eBayValidationError(msg)
    elif status_code in (502, 503, 504):
        return eBayTimeoutError(msg)
    else:
        return eBayAPIError(msg)
