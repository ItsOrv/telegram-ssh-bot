# Performance and low-resource servers

## Summary of optimizations

### 1. Public mode cache
- **Before**: Every callback (button click) and `/start`/`/help` ran a DB query to check `public_mode`.
- **After**: Result is cached in memory for 45 seconds. Cache is cleared when admin toggles public mode.
- **Effect**: Far fewer DB queries and faster response on menu navigation.

### 2. Single thread pool and worker count
- **Before**: Two separate thread pools (default + command executor), each with 50 workers → up to 100 threads.
- **After**: One shared thread pool; default 15 workers, configurable via `THREAD_POOL_MAX_WORKERS` in `.env`.
- **Effect**: Less RAM and CPU usage; fewer threads competing on low-resource servers.

### 3. Resource usage overview
| Resource        | Typical use |
|----------------|-------------|
| Thread pool     | 1 pool, 15 workers by default (env override) |
| DB connections | Pool size 5, max overflow 10 (SQLAlchemy) |
| SSH connections| Limited by semaphore (10 concurrent connects) |
| Long commands  | Each holds one thread until timeout (default 300s) |

### When the bot feels slow

1. **Low RAM**: Reduce `THREAD_POOL_MAX_WORKERS` to 8 in `.env`.
2. **Many users running long commands**: Each execution uses one worker; consider lowering `COMMAND_TIMEOUT` or `THREAD_POOL_MAX_WORKERS` so new requests are not starved.
3. **Database on same host**: Default DB pool is usually enough; if DB is remote/slow, the public_mode cache already cuts down repeated checks.
4. **Network**: Telegram timeouts are 60s (read/write/connect); slow networks may need a better connection, not code changes.

### Optional .env for low-resource

```env
THREAD_POOL_MAX_WORKERS=8
RATE_LIMIT_PER_MINUTE=20
COMMAND_TIMEOUT=120
```

For powerful servers you can increase workers:

```env
THREAD_POOL_MAX_WORKERS=30
```
