FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY app /app/app
COPY pytest.ini /app/pytest.ini
COPY tests /app/tests

RUN addgroup --system sentinel && adduser --system --ingroup sentinel sentinel && chown -R sentinel:sentinel /app
USER sentinel

EXPOSE 8000

CMD ["bash", "-lc", "alembic upgrade head && python -m app.scripts.seed_demo && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
