"""
utils/rate_limiter.py
~~~~~~~~~~~~~~~~~~~~~
TokenBucket — async rate limiter for controlling tool execution speed.

CONTRACT
--------
TokenBucket(rate, capacity=None)
    ``rate``     — tokens added per second (float)
    ``capacity`` — max tokens in the bucket (defaults to ``rate``)

async acquire(tokens=1)
    Wait until ``tokens`` are available, then consume them.
    NEVER raises.  Always succeeds eventually (blocks until tokens refill).

try_acquire(tokens=1) -> bool
    Non-blocking.  Returns True if tokens were consumed, False otherwise.

available -> float
    Current number of tokens in the bucket (read-only).
"""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """
    Async token bucket rate limiter.

    Tokens are added at a fixed ``rate`` per second.  The bucket has a
    maximum ``capacity``.  Consumers call ``acquire()`` to wait for
    tokens or ``try_acquire()`` to check without blocking.

    Parameters
    ----------
    rate:
        Tokens added per second.
    capacity:
        Maximum tokens in the bucket.  Defaults to ``rate`` (1 second burst).
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        if rate <= 0:
            raise ValueError(f"rate must be positive, got {rate}")
        self._rate     = float(rate)
        self._capacity = float(capacity if capacity is not None else rate)
        self._tokens   = self._capacity  # start full
        self._last     = time.monotonic()
        self._lock     = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def acquire(self, tokens: float = 1.0) -> None:
        """
        Wait until ``tokens`` are available, then consume them.

        If the bucket doesn't have enough tokens, this coroutine sleeps
        until enough tokens have refilled.
        """
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Calculate wait time
                deficit = tokens - self._tokens
                wait = deficit / self._rate

            await asyncio.sleep(wait)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """
        Non-blocking acquire.  Returns True if tokens were consumed.

        NOTE: This is a synchronous method — it cannot be ``await``ed.
        For use in sync code paths or quick checks.
        """
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    @property
    def available(self) -> float:
        """Current number of tokens in the bucket."""
        self._refill()
        return self._tokens

    @property
    def rate(self) -> float:
        """Tokens per second."""
        return self._rate

    @property
    def capacity(self) -> float:
        """Maximum bucket size."""
        return self._capacity

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now     = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate)
        self._last   = now
