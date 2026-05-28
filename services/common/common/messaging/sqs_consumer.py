from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

try:
    import boto3
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


class SQSConsumer:
    """Long-poll SQS consumer that runs in a background daemon thread.

    Automatically deletes messages after successful handler invocation.
    Failed messages are left in the queue and routed to the DLQ after
    maxReceiveCount retries (configured on the queue).
    """

    def __init__(
        self,
        queue_url: str,
        handler: Callable[[dict[str, Any]], None],
        max_messages: int = 10,
    ) -> None:
        self._queue_url = queue_url
        self._handler = handler
        self._max_messages = max_messages
        self._running = False
        self._thread: threading.Thread | None = None
        self._sqs = None

        if not _BOTO3_AVAILABLE:
            logger.warning("boto3 not installed; SQS consumer disabled")
            return

        if not queue_url:
            logger.warning("SQS_NOTIFICATION_EVENTS_URL not set; consumer disabled")
            return

        region = os.environ.get("AWS_REGION", "ap-south-1")
        self._sqs = boto3.client("sqs", region_name=region)

    def start(self) -> None:
        if not self._sqs:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="sqs-consumer")
        self._thread.start()
        logger.info("SQS consumer started — queue: %s", self._queue_url)

    def stop(self) -> None:
        self._running = False

    def _poll_loop(self) -> None:
        while self._running:
            try:
                response = self._sqs.receive_message(
                    QueueUrl=self._queue_url,
                    MaxNumberOfMessages=self._max_messages,
                    WaitTimeSeconds=20,
                    AttributeNames=["All"],
                )
                for msg in response.get("Messages", []):
                    self._process(msg)
            except Exception as exc:
                logger.warning("SQS poll error: %s", exc)

    def _process(self, msg: dict[str, Any]) -> None:
        try:
            body = json.loads(msg["Body"])
            self._handler(body)
            self._sqs.delete_message(
                QueueUrl=self._queue_url,
                ReceiptHandle=msg["ReceiptHandle"],
            )
        except Exception as exc:
            logger.error("SQS message handler failed (will retry via DLQ): %s", exc)
