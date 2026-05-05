"""Retry strategies for resilient crawling."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Callable, Dict, Optional, TypeVar

T = TypeVar("T")


class RetryStrategy(ABC):
    """Abstract base for retry strategies."""

    @abstractmethod
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Determine if operation should be retried."""
        pass

    @abstractmethod
    def get_delay(self, attempt: int) -> float:
        """Get delay before next retry in seconds."""
        pass

    def execute(
        self,
        func: Callable[[], T],
        on_retry: Optional[Callable[[int, Exception], None]] = None,
    ) -> T:
        """Execute function with retry logic."""
        attempt = 0
        last_error: Optional[Exception] = None

        while True:
            try:
                return func()
            except Exception as e:
                last_error = e
                attempt += 1

                if not self.should_retry(attempt, e):
                    raise

                if on_retry:
                    on_retry(attempt, e)

                delay = self.get_delay(attempt)
                if delay > 0:
                    time.sleep(delay)

        # This should never be reached, but for type checking
        if last_error:
            raise last_error
        raise RuntimeError("Retry logic failed unexpectedly")


class ExponentialBackoffRetry(RetryStrategy):
    """Exponential backoff retry strategy."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if should retry based on attempt count."""
        # Don't retry certain errors
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            return False

        return attempt < self.max_retries

    def get_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.base_delay * (self.exponential_base ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            import random

            delay = delay * (0.5 + random.random() * 0.5)

        return delay


class AdaptiveRetry(RetryStrategy):
    """Adaptive retry strategy that learns from failures."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 120.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._failure_counts: Dict[str, int] = defaultdict(int)
        self._success_counts: Dict[str, int] = defaultdict(int)

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if should retry based on attempt count and error type."""
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            return False

        error_type = type(error).__name__

        # Track failure
        self._failure_counts[error_type] += 1

        # If this error type fails too often, be more conservative
        failure_rate = self._get_failure_rate(error_type)
        if failure_rate > 0.8:
            # High failure rate, reduce retries
            return attempt < max(1, self.max_retries - 1)

        return attempt < self.max_retries

    def get_delay(self, attempt: int) -> float:
        """Calculate adaptive delay based on historical performance."""
        # Base exponential backoff
        delay = self.base_delay * (2 ** (attempt - 1))

        # Adjust based on overall failure rate
        overall_failure_rate = self._get_overall_failure_rate()
        if overall_failure_rate > 0.5:
            # High failure rate, increase delays
            delay *= 1.5

        delay = min(delay, self.max_delay)
        return delay

    def _get_failure_rate(self, error_type: str) -> float:
        """Get failure rate for specific error type."""
        failures = self._failure_counts[error_type]
        successes = self._success_counts[error_type]
        total = failures + successes
        return failures / total if total > 0 else 0.0

    def _get_overall_failure_rate(self) -> float:
        """Get overall failure rate across all error types."""
        total_failures = sum(self._failure_counts.values())
        total_successes = sum(self._success_counts.values())
        total = total_failures + total_successes
        return total_failures / total if total > 0 else 0.0

    def record_success(self, error_type: Optional[str] = None) -> None:
        """Record a successful operation."""
        if error_type:
            self._success_counts[error_type] += 1


class RateLimitRetry(RetryStrategy):
    """Retry strategy specifically for rate limiting."""

    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 60.0,
        max_delay: float = 600.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if should retry rate limit errors."""
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            return False

        # Check if error is rate limit related
        error_str = str(error).lower()
        is_rate_limit = any(
            term in error_str
            for term in ["rate limit", "too many requests", "429", "quota exceeded"]
        )

        if not is_rate_limit:
            return False

        return attempt < self.max_retries

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for rate limit retry."""
        # Longer delays for rate limits
        delay = self.base_delay * (1.5 ** (attempt - 1))
        delay = min(delay, self.max_delay)
        return delay
