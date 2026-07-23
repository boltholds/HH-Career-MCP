FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install . \
    && useradd --create-home --uid 10001 app \
    && mkdir -p /data/hh \
    && chown -R app:app /app /data/hh

USER app

EXPOSE 8000 8766

CMD ["hh-career-mcp"]
