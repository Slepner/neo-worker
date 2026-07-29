#!/usr/bin/env python3
"""neo_worker.py - Redis job worker for GARLCLOUD.

Listens on QUEUE_NAME, executes run_bash tasks, pushes results to jobs:neo:completed.
If /workspace/neo_worker.py exists (bind mount override), loads that instead.
"""

import os, subprocess, time, sys, importlib, json

# Allow runtime override via bind mount
OVERRIDE_PATH = "/workspace/neo_worker.py"
if os.path.isfile(OVERRIDE_PATH):
    with open(OVERRIDE_PATH) as f:
        exec(compile(f.read(), OVERRIDE_PATH, 'exec'))
    sys.exit(0)

REDIS_HOST = os.environ.get("REDIS_HOST", "redis-ai")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
QUEUE_NAME = os.environ.get("QUEUE_NAME", "jobs:neo:pending")


def _install_redis():
    target = "/tmp/redis_pkg"
    os.makedirs(target, exist_ok=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--target", target, "--quiet", "redis"]
    )
    sys.path.insert(0, target)
    importlib.invalidate_caches()


try:
    import redis as redis_mod
except ImportError:
    _install_redis()
    import redis as redis_mod

r = redis_mod.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=0, socket_timeout=10, decode_responses=True
)

while True:
    try:
        r.ping()
        print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        break
    except redis_mod.ConnectionError:
        print("Waiting for Redis...")
        time.sleep(5)

print(f"Listening on queue: {QUEUE_NAME}")

while True:
    try:
        item = r.brpop(QUEUE_NAME, timeout=5)
        if item is None:
            continue

        _, payload = item
        job = json.loads(payload)
        job_id = job.get("job_id", "unknown")
        task_type = job.get("task_type", "")
        command = job.get("command", "")

        print(f"Processing job {job_id}: {task_type} -> {command[:80]}")

        if task_type == "run_bash":
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=3600
            )
            output = {
                "job_id": job_id,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        else:
            output = {"job_id": job_id, "error": f"Unknown task_type: {task_type}"}

        r.lpush("jobs:neo:completed", json.dumps(output))
        print(f"Completed job {job_id}")

    except subprocess.TimeoutExpired:
        print(f"Timeout for job {job_id}")
        r.lpush(
            "jobs:neo:completed",
            json.dumps({"job_id": job_id, "error": "timeout after 3600s"}),
        )
    except json.JSONDecodeError as e:
        print(f"Bad JSON: {e}")
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)
