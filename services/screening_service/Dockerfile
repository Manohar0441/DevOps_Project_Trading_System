FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY config /app/config
COPY inputs /app/inputs
COPY services /app/services
COPY main.py /app/main.py
COPY batchrunner.py /app/batchrunner.py
COPY stocks.txt /app/stocks.txt

RUN mkdir -p /app/outputs /app/logs /app/failed \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser
