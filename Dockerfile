ARG PYTHON_BASE_IMAGE=mirror.gcr.io/library/python:3.11-alpine
FROM ${PYTHON_BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AUTOBAHN_USE_NVX=0
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/app/healthz/', timeout=3).status == 200 else 1)"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-c", "gunicorn.conf.py", "conf.wsgi:application"]
