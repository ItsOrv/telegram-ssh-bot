# Performance

Public mode is cached for 45 seconds so we don't hit the DB on every button press. One thread pool (default 15 workers, set `THREAD_POOL_MAX_WORKERS` in `.env`) is used for DB and SSH so the process stays light.

On low-RAM or single-CPU boxes use `THREAD_POOL_MAX_WORKERS=8` or lower. Long-running commands keep a worker until they finish, so avoid many at once.
