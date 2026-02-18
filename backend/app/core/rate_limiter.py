import time
import threading
from backend.app.core.logger import get_logger

logger = get_logger('rate_limiter')

class TokenBucket:
    """Thread-safe Token Bucket implementation for rate limiting."""
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def consume(self, tokens: float = 1.0) -> float:
        """
        Consume tokens from the bucket.
        Returns the amount of time to sleep if tokens are not available.
        """
        with self._lock:
            now = time.time()
            # Refill tokens
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            
            # Calculate wait time
            wait_time = (tokens - self.tokens) / self.refill_rate
            return wait_time

class RateLimiter:
    """
    Centralized Rate Limiter for eBay and Gemini APIs.
    """
    def __init__(self):
        from backend.app.core.constants import (
            GEMINI_RPM_LIMIT, EBAY_BURST_LIMIT, EBAY_REFILL_RATE
        )
        
        # buckets stores named TokenBucket instances
        self.buckets = {
            # Gemini: Strict RPM. Bucket size 1, refill speed = 1/interval
            'gemini': TokenBucket(capacity=1.0, refill_rate=1.0 / (60.0 / GEMINI_RPM_LIMIT)),
            
            # eBay: Burst oriented. Refills over time.
            'ebay': TokenBucket(capacity=float(EBAY_BURST_LIMIT), refill_rate=float(EBAY_REFILL_RATE))
        }

    def wait_if_needed(self, service: str):
        """Pauses execution if rate limit for the service is exceeded."""
        bucket = self.buckets.get(service)
        if not bucket:
            return

        wait_time = bucket.consume()
        if wait_time > 0:
            logger.info(f"⏳ Rate limit hit for '{service}'. Throttling for {wait_time:.2f}s...")
            time.sleep(wait_time)

# Global Instance
limiter = RateLimiter()
