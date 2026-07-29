# neo-worker — Redis-backed AI task execution container for Unraid
#
# A sandboxed worker that listens on a Redis queue, executes bash commands
# against mounted Unraid shares, and reports results. Designed as a gateway
# for AI agents to perform file operations with controlled access.
#
# Build locally:  docker build -t neo-worker .
# Run via Unraid Docker UI template (recommended) or compose.

FROM python:3.11-slim

# Install Redis client for job queue
RUN pip install --no-cache-dir redis

# Run as nobody:nogroup for Unraid share compatibility
USER 99:100

# Working directory for data exchange with orchestrator
WORKDIR /workspace

# Copy the worker (runtime check for newer version in /workspace)
COPY neo_worker.py /app/neo_worker.py

# Start the worker
CMD ["python", "/app/neo_worker.py"]
