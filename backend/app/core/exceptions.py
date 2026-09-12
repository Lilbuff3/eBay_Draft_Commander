"""
Custom exception hierarchy for eBay Draft Commander.
"""


class DraftCommanderError(Exception):
    """Base exception for all Draft Commander errors"""
    pass


class QueueError(DraftCommanderError):
    """Base exception for queue operations"""
    pass


class NeedsReviewException(QueueError):
    """Job requires manual review before it can proceed (e.g. missing item specifics)"""
    pass
