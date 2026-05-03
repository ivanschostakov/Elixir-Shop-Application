FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /home/app app

COPY requirements.txt ./requirements.txt
COPY requirements-prod.txt ./requirements-prod.txt
COPY requirements-dev.txt ./requirements-dev.txt

ARG REQUIREMENTS_FILE=requirements-prod.txt
RUN pip install --no-cache-dir -r "${REQUIREMENTS_FILE}"
RUN python -m playwright install --with-deps chromium \
    && chmod -R 755 /ms-playwright

COPY --chown=app:app . .
RUN mkdir -p /app/backend/media /app/backend/logs \
    && chown -R app:app /app/backend

USER app

CMD ["python", "run.py"]
