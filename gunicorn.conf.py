import multiprocessing
import os


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


cpu_count = multiprocessing.cpu_count()

# Baseline for a medium internal workload on the same VM as PostgreSQL.
workers = env_int("GUNICORN_WORKERS", max(2, min(4, cpu_count)))
threads = env_int("GUNICORN_THREADS", 2)
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
timeout = env_int("GUNICORN_TIMEOUT", 60)
graceful_timeout = env_int("GUNICORN_GRACEFUL_TIMEOUT", 30)
keepalive = env_int("GUNICORN_KEEPALIVE", 5)
max_requests = env_int("GUNICORN_MAX_REQUESTS", 1000)
max_requests_jitter = env_int("GUNICORN_MAX_REQUESTS_JITTER", 100)
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")
