FROM python:3.14-slim
WORKDIR /app
COPY requirements-staging.lock ./
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-staging.lock
COPY app.py calculator.py ./
ARG APP_REVISION
ENV APP_REVISION=${APP_REVISION} PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:10000/health/ready', timeout=2)"]
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --access-logfile - --error-logfile - app:app"]
