from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import boto3
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


class SQSPublisher:
    """Publishes JSON event messages to an SQS queue."""

    def __init__(self, queue_url: str) -> None:
        self._queue_url = queue_url
        self._sqs = None

        if not _BOTO3_AVAILABLE:
            logger.warning("boto3 not installed; SQS publisher disabled")
            return

        if not queue_url:
            return

        region = os.environ.get("AWS_REGION", "ap-south-1")
        self._sqs = boto3.client("sqs", region_name=region)

    def publish(self, event_type: str, payload: dict[str, Any]) -> bool:
        if not self._sqs:
            logger.debug("SQS publish skipped (no client): %s", event_type)
            return False
        try:
            body = json.dumps({"event_type": event_type, "payload": payload}, default=str)
            self._sqs.send_message(QueueUrl=self._queue_url, MessageBody=body)
            logger.debug("SQS event sent: %s → %s", event_type, self._queue_url)
            return True
        except Exception as exc:
            logger.warning("SQS publish failed (%s): %s", event_type, exc)
            return False
