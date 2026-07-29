# neo-worker

Redis-backed worker container for AI task execution with controlled Unraid share access.

## How it works

```
Neo (Hermes) → Redis queue → neo-worker → executes job → Redis completed → Neo reads result
```

Jobs are pushed to `jobs:neo:pending` as JSON. The worker picks them up, executes the
`run_bash` command against mounted Unraid shares, and pushes the result to `jobs:neo:completed`.

## Environment

| Variable      | Default    | Description                    |
|---------------|------------|--------------------------------|
| REDIS_HOST    | redis-ai   | Redis server hostname          |
| REDIS_PORT    | 6379       | Redis server port              |
| QUEUE_NAME    | jobs:neo:pending | Redis list key for pending jobs |

## Runtime Override

If `/workspace/neo_worker.py` exists as a bind mount, it takes precedence over the
built-in worker. This lets you update the worker logic without rebuilding the image.

## Building

```bash
docker build -t neo-worker .
```

For Unraid, build and push to GHCR via the included GitHub Actions workflow,
then deploy using the Unraid XML template.
