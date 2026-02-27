"""
Thread-safe rate limiter for Azure OpenAI API.
Tracks TPM (tokens per minute) using a sliding window.
"""

import time
import threading
from collections import deque
from typing import Optional

from common.config import AZURE_TPM_LIMIT


class AzureRateLimiter:
    """
    Thread-safe rate limiter for Azure OpenAI API.
    Tracks TPM (tokens per minute) using a sliding window.
    """

    def __init__(self, tpm_limit: int = AZURE_TPM_LIMIT):
        self.tpm_limit = tpm_limit
        self.lock = threading.Lock()
        self.token_log: deque = deque()  # (timestamp, token_count) pairs
        self.total_tokens = 0
        self.total_requests = 0
        self.throttle_events = 0
        self.retry_after_until = 0  # Timestamp until which we must wait

    def estimate_tokens(self, prompt: str, completion: str = "") -> int:
        """Estimate token count (~4 chars per token for English)."""
        text = prompt + completion
        return max(1, len(text) // 4)

    def _cleanup_old_entries(self):
        """Remove entries older than 60 seconds."""
        cutoff = time.time() - 60
        while self.token_log and self.token_log[0][0] < cutoff:
            self.token_log.popleft()

    def get_current_tpm(self) -> int:
        """Get current tokens used in the last 60 seconds."""
        with self.lock:
            self._cleanup_old_entries()
            return sum(tokens for _, tokens in self.token_log)

    def wait_if_needed(self, estimated_tokens: int) -> float:
        """
        Wait if we would exceed TPM limit.
        Returns the time waited in seconds.
        """
        wait_time = 0

        with self.lock:
            # Check if we need to respect Retry-After
            now = time.time()
            if self.retry_after_until > now:
                wait_time = self.retry_after_until - now

            # Check TPM limit
            self._cleanup_old_entries()
            current_tpm = sum(tokens for _, tokens in self.token_log)

            if current_tpm + estimated_tokens > self.tpm_limit:
                # Calculate how long to wait for oldest entries to expire
                if self.token_log:
                    oldest_time = self.token_log[0][0]
                    wait_time = max(wait_time, (oldest_time + 60) - now + 0.5)
                    self.throttle_events += 1

        if wait_time > 0:
            time.sleep(wait_time)

        return wait_time

    def record_usage(self, prompt: str, completion: str, actual_tokens: Optional[int] = None):
        """Record token usage from a completed request."""
        if actual_tokens is not None:
            tokens = actual_tokens
        else:
            tokens = self.estimate_tokens(prompt, completion)

        with self.lock:
            self.token_log.append((time.time(), tokens))
            self.total_tokens += tokens
            self.total_requests += 1

    def set_retry_after(self, seconds: float):
        """Set a global pause due to 429 response."""
        with self.lock:
            self.retry_after_until = time.time() + seconds

    def get_stats(self) -> dict:
        """Get rate limiter statistics."""
        current_tpm = self.get_current_tpm()
        return {
            'current_tpm': current_tpm,
            'tpm_limit': self.tpm_limit,
            'total_tokens': self.total_tokens,
            'total_requests': self.total_requests,
            'throttle_events': self.throttle_events,
            'utilization': f"{(current_tpm / self.tpm_limit * 100):.1f}%" if self.tpm_limit > 0 else "0%"
        }


# Global rate limiter instance
rate_limiter = AzureRateLimiter()
