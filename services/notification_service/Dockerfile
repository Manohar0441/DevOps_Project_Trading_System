FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY config /app/config
COPY inputs /app/inputs
COPY services /app/services
COPY stocks.txt /app/stocks.txt

RUN mkdir -p /app/outputs /app/logs /app/failed \
    && useradd -m -u 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8006
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8006/health')"
CMD ["python", "-m", "services.notification_service.app.main"]
