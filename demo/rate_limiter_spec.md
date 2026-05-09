Implement a thread-safe token bucket rate limiter in Python.

The rate limiter must:
- Accept `rate` (tokens per second, float) and `burst` (maximum token capacity, int) at construction
- Expose an `acquire(tokens: int = 1)` method that:
  - Returns immediately if enough tokens are available
  - Raises `RateLimitExceeded` if `tokens > burst` (impossible to ever satisfy)
  - Blocks (sleeps) until enough tokens have replenished if tokens <= burst but not currently available
- Replenish tokens continuously at the configured rate (token bucket algorithm)
- Be thread-safe: multiple threads calling `acquire()` concurrently must not corrupt internal state
- `RateLimitExceeded` must be a subclass of `Exception`

The implementation must live in a single file and export: `TokenBucket`, `RateLimitExceeded`.
