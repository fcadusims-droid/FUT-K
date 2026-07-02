# FUT-K backend — engine + API
FROM python:3.12-slim

WORKDIR /srv/futk
# Engine first (the backend depends on it as a local package).
COPY pyproject.toml conftest.py README.md ./
COPY src ./src
COPY plugins ./plugins
COPY backend/pyproject.toml backend/
COPY backend/app backend/app
COPY backend/scripts backend/scripts
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir -e ./backend

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
WORKDIR /srv/futk/backend
# JSON access logs go to stdout; the platform collects them (level 16: logs).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
