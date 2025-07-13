# gunicorn_conf.py

import os

# Server socket
host = os.environ.get("HOST", "0.0.0.0")
port = os.environ.get("PORT", "8000")
bind = f"{host}:{port}"

# Worker processes
workers = int(os.environ.get("WEB_CONCURRENCY", 3))
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout setting for long-running AI calls
timeout = 180

# Logging configuration
loglevel = os.environ.get("LOG_LEVEL", "info")
accesslog = "-"
errorlog = "-"
