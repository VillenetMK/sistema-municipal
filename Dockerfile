FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLET_FORCE_WEB_SERVER=true \
    MUNIGEST_MODE=supabase \
    PORT=8550

WORKDIR /app
RUN python -m pip install --no-cache-dir uv==0.12.11
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra server --no-install-project

RUN useradd --create-home --uid 10001 municipal
COPY --chown=municipal:municipal src ./src
COPY --chown=municipal:municipal run.py ./run.py
USER municipal

EXPOSE 8550
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD /app/.venv/bin/python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8550') + '/', timeout=4)"

CMD ["/app/.venv/bin/python", "run.py", "--web", "--host", "0.0.0.0"]
