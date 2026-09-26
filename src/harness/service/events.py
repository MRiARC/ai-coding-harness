"""Redis event publisher (platform P3, issue #72).

Bridges engine trace events to Redis pub/sub (`harness.events.<run_id>`)
so the Go gateway can broadcast them to WebSocket clients. The publisher
is a no-op unless a Redis client is available: the graded eval path never
requires Redis.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from harness.infrastructure.logging import get_logger

logger = get_logger(__name__)

CHANNEL_PREFIX = "harness.events"


class RedisLike(Protocol):
    """Minimal client surface used by the publisher (real or fake)."""

    def publish(self, channel: str, message: str) -> Any: ...


class RedisEventPublisher:
    """Publishes JSON events to `harness.events.<run_id>` channels.

    Construct with an explicit client (tests inject fakes), or with
    `url=` to create a real client lazily. With neither, `publish`
    becomes a no-op - the offline/eval path stays fully functional.
    """

    def __init__(self, client: RedisLike | None = None, url: str | None = None) -> None:
        self._client = client
        self._url = url if url is not None else os.environ.get("REDIS_URL")

    def _resolved(self) -> RedisLike | None:
        if self._client is not None:
            return self._client
        if self._url:
            import redis  # optional platform dependency

            self._client = redis.Redis.from_url(self._url, decode_responses=True)
            return self._client
        return None

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        """Publish one event; silently inert without Redis configuration."""
        client = self._resolved()
        if client is None:
            return
        channel = f"{CHANNEL_PREFIX}.{run_id}"
        try:
            client.publish(channel, json.dumps(event, sort_keys=True, default=str))
        except Exception as exc:
            logger.warning("redis publish failed", channel=channel, error=str(exc)[:200])

    def sink_for(self, run_id: str) -> Any:
        """Event-sink callable for `EvidencePack(event_sink=...)`."""

        def _sink(event: dict[str, Any]) -> None:
            self.publish(run_id, event)

        return _sink
