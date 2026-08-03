# neo-worker

Redis-backed job worker for GARLCLOUD. Listens on a Redis queue, executes
bash commands against mounted Unraid shares, and reports results back. It is
the execution gateway that lets AI agents (Neo / n8n) run controlled file
operations on the server.

## How it works

- Connects to Redis (`redis-ai:6379` by default, over Docker DNS on `homeai-net`).
- Blocks on `BRPOP` against queue `jobs:neo:pending` (default `QUEUE_NAME`).
- Supports one task type: `run_bash` (shell command, 1 hour timeout).
- Pushes a result object to the `jobs:neo:completed` list (LPUSH).
- If `/workspace/neo_worker.py` exists as a bind-mount override, that copy is
  executed instead of the baked-in `/app/neo_worker.py` — handy for
  hot-patching without rebuilding the image.

Job payload format (push to `jobs:neo:pending`):

```json
{"job_id": "neo-xxxxx", "task_type": "run_bash", "command": "echo hello"}
```

Result payload (read from `jobs:neo:completed`):

```json
{"job_id": "neo-xxxxx", "exit_code": 0, "stdout": "hello\n", "stderr": ""}
```

## Files

| File | Purpose |
|---|---|
| `neo_worker.py` | The worker itself (Python 3, redis-py). |
| `Dockerfile` | Builds `ghcr.io/slepner/neo-worker:latest`. python:3.11-slim, runs as UID 99 / GID 100. |
| `docker-compose.yml` | Compose definition matching the RUNNING container config on GARLCLOUD (all 14 mounts). |

## Build & publish

```bash
docker build -t ghcr.io/slepner/neo-worker:latest .
docker login ghcr.io -u Slepner          # token with write:packages
docker push ghcr.io/slepner/neo-worker:latest
```

Package visibility on GHCR is controlled per-package in GitHub settings /
API — it is NOT set via `docker push`. The `neo-worker` package must be
**public** so Unraid nodes can pull it anonymously (the Unraid template
references `ghcr.io/slepner/neo-worker:latest`).

**Visibility gotcha (learned 2026-08-03):** GHCR sets a container package's
visibility when the package is FIRST created, based on the linked repository's
visibility at that moment. If the repo is private at first push, the package
stays private forever — even after the repo is made public and newer images
are pushed. The "Set a package visibility" REST endpoint no longer exists
(404 since ~2023, absent from current OpenAPI spec), and classic PATs without
`delete:packages` cannot delete packages. Fix that works: a one-shot
GitHub Actions workflow with `packages: write` can delete the package
(GitHub enabled workflow-delete in public preview), then a fresh push
recreates it with visibility inherited from the now-public repo. The
`delete-package.yml` workflow in this repo is kept but DISABLED so it can be
re-enabled if this ever needs to be done again.

## Deploy on Unraid

The container is managed by the Unraid template `neo-worker.xml`
(template-user dir). It runs on the `homeai-net` Docker network alongside
`redis-ai`, `n8n`, and the rest of the GARLCLOUD stack.

Compose alternative (matches the running container's mounts):

```bash
cd /path/to/this/repo
docker network create homeai-net   # if missing
docker compose up -d
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `REDIS_HOST` | `redis-ai` | Redis host (Docker DNS name). |
| `REDIS_PORT` | `6379` | Redis port. |
| `QUEUE_NAME` | `jobs:neo:pending` | Queue to BRPOP from. |
| `PYTHONUNBUFFERED` | `1` | Flush logs immediately (set in compose). |

### Mounts (running config)

| Host path | Container path | Mode |
|---|---|---|
| `/mnt/user/workspace` | `/workspace` | rw |
| `/mnt/user/Dreamworld` | `/dreamworld` | rw |
| `/mnt/user/lucas` | `/shares/lucas` | rw |
| `/mnt/user/riley` | `/shares/riley` | rw |
| `/boot/config/plugins/dockerMan/templates-user` | `/share/dockertemplates` | rw |
| `/mnt/user/Media` | `/shares/Media` | rw, shared |
| `/mnt/user/photos` | `/shares/photos` | rw, shared |
| `/mnt/user/immich` | `/shares/immich` | ro |
| `/mnt/user/alison` | `/shares/alison` | ro |
| `/mnt/user/graham` | `/shares/graham` | ro |
| `/mnt/user/Backups` | `/shares/Backups` | ro |
| `/mnt/user/Homefiles` | `/shares/Homefiles` | ro |
| `/mnt/disks` | `/shares/disks` | ro |
| `/mnt/disks/USBDRIVEMEDIA` | `/shares/USBDRIVEMEDIA` | ro |

## Operational notes

- Redis connectivity uses Docker DNS (`redis-ai`), so the container must be on
  `homeai-net`. A startup loop retries `ping()` every 5s until Redis is reachable.
- Logs are plain-text stdout lines; container log driver is `json-file`
  (max-size 50m, max-file 1).
- The image is rebuilt from this repo whenever the worker changes; the running
  container keeps the same name/tag so rollback is a `docker pull` + recreate.
