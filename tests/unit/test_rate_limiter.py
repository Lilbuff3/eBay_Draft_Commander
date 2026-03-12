import pytest
import time
from unittest.mock import patch
from backend.app.core.rate_limiter import TokenBucket, RateLimiter

def test_token_bucket_consumption():
    # Capacity 10, refill 1 per second
    bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
    
    # Consume 5
    assert bucket.consume(5.0) == 0.0
    assert bucket.tokens == 5.0
    
    # Consume remaining 5
    assert bucket.consume(5.0) == 0.0
    assert bucket.tokens == 0.0
    
    # Next consumption should require wait
    wait_time = bucket.consume(1.0)
    assert wait_time > 0.0
    assert wait_time == 1.0

def test_token_bucket_refill():
    bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
    bucket.tokens = 0.0
    
    # Mock time.time to simulate 5 seconds passing
    start_time = time.time()
    with patch('time.time', side_effect=[start_time + 5.0]):
        wait_time = bucket.consume(2.0)
        assert wait_time == 0.0
        # 5 tokens refilled - 2 consumed = 3 remaining
        assert bucket.tokens == 3.0

def test_rate_limiter_global_instance():
    from backend.app.core.rate_limiter import limiter
    assert 'ebay' in limiter.buckets
    assert 'gemini' in limiter.buckets

@patch('time.sleep')
def test_rate_limiter_wait(mock_sleep):
    # Gemini limit is 2 RPM -> 1 request every 30s
    bucket = TokenBucket(capacity=1.0, refill_rate=1.0/30.0)
    
    limiter = RateLimiter()
    limiter.buckets['gemini'] = bucket
    
    # First call: no wait
    limiter.wait_if_needed('gemini')
    assert mock_sleep.call_count == 0
    
    # Second call immediate: should wait 30s
    limiter.wait_if_needed('gemini')
    assert mock_sleep.call_count == 1
    mock_sleep.assert_called_with(pytest.approx(30.0, rel=0.1))
