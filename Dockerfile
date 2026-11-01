FROM python:3.14-slim
WORKDIR /app
COPY requirements.txt requirements-staging.txt ./
RUN pip install --no-cache-dir -r requirements-staging.txt
COPY app.py calculator.py ./
ARG APP_REVISION
ENV APP_REVISION=${APP_REVISION} PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 10000
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --access-logfile - --error-logfile - app:app"]
