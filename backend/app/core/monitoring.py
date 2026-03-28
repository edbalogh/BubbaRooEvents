"""Monitoring, metrics, and error tracking.

Provides Sentry integration for error tracking and a simple
metrics endpoint for Prometheus/Grafana scraping.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# --- Sentry Integration ---


def init_sentry(dsn: str, environment: str = "development") -> None:
    """Initialize Sentry error tracking if DSN is configured."""
    if not dsn:
        logger.info("Sentry DSN not configured, skipping error tracking")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=0.1,  # 10% of requests
            profiles_sample_rate=0.1,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
            ],
        )
        logger.info(f"Sentry initialized for {environment}")
    except ImportError:
        logger.warning("sentry-sdk not installed. pip install sentry-sdk[fastapi]")


# --- Simple Metrics ---


class MetricsCollector:
    """Lightweight in-process metrics for Prometheus scraping."""

    def __init__(self):
        self.request_count: dict[str, int] = defaultdict(int)
        self.request_duration: dict[str, list[float]] = defaultdict(list)
        self.error_count: dict[str, int] = defaultdict(int)
        self.ingestion_count: dict[str, int] = defaultdict(int)
        self.notification_count: dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def record_request(self, method: str, path: str, status: int, duration: float) -> None:
        key = f"{method} {path}"
        self.request_count[key] += 1
        self.request_duration[key].append(duration)
        # Keep only last 1000 durations per endpoint
        if len(self.request_duration[key]) > 1000:
            self.request_duration[key] = self.request_duration[key][-500:]
        if status >= 400:
            self.error_count[key] += 1

    def record_ingestion(self, source: str, count: int) -> None:
        self.ingestion_count[source] += count

    def record_notification(self, channel: str, success: bool) -> None:
        key = f"{channel}:{'ok' if success else 'fail'}"
        self.notification_count[key] += 1

    def get_metrics_text(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        uptime = time.time() - self._start_time

        lines.append(f"# HELP bubbaroo_uptime_seconds Time since process start")
        lines.append(f"# TYPE bubbaroo_uptime_seconds gauge")
        lines.append(f"bubbaroo_uptime_seconds {uptime:.0f}")

        lines.append(f"# HELP bubbaroo_http_requests_total Total HTTP requests")
        lines.append(f"# TYPE bubbaroo_http_requests_total counter")
        for key, count in self.request_count.items():
            method, path = key.split(" ", 1)
            lines.append(
                f'bubbaroo_http_requests_total{{method="{method}",path="{path}"}} {count}'
            )

        lines.append(f"# HELP bubbaroo_http_errors_total Total HTTP errors (4xx/5xx)")
        lines.append(f"# TYPE bubbaroo_http_errors_total counter")
        for key, count in self.error_count.items():
            method, path = key.split(" ", 1)
            lines.append(
                f'bubbaroo_http_errors_total{{method="{method}",path="{path}"}} {count}'
            )

        lines.append(f"# HELP bubbaroo_http_duration_seconds Request duration")
        lines.append(f"# TYPE bubbaroo_http_duration_seconds summary")
        for key, durations in self.request_duration.items():
            if durations:
                method, path = key.split(" ", 1)
                avg = sum(durations) / len(durations)
                p99 = sorted(durations)[int(len(durations) * 0.99)] if len(durations) > 1 else durations[0]
                lines.append(
                    f'bubbaroo_http_duration_seconds{{method="{method}",path="{path}",quantile="0.99"}} {p99:.4f}'
                )
                lines.append(
                    f'bubbaroo_http_duration_seconds{{method="{method}",path="{path}",quantile="avg"}} {avg:.4f}'
                )

        lines.append(f"# HELP bubbaroo_ingestion_total Events ingested by source")
        lines.append(f"# TYPE bubbaroo_ingestion_total counter")
        for source, count in self.ingestion_count.items():
            lines.append(f'bubbaroo_ingestion_total{{source="{source}"}} {count}')

        lines.append(f"# HELP bubbaroo_notifications_total Notifications by channel")
        lines.append(f"# TYPE bubbaroo_notifications_total counter")
        for key, count in self.notification_count.items():
            channel, status = key.split(":")
            lines.append(
                f'bubbaroo_notifications_total{{channel="{channel}",status="{status}"}} {count}'
            )

        return "\n".join(lines) + "\n"


# Global metrics instance
metrics = MetricsCollector()


class MetricsMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that records request metrics."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        # Simplify path for grouping (replace UUIDs with :id)
        path = request.url.path
        import re
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            ":id",
            path,
        )

        metrics.record_request(request.method, path, response.status_code, duration)
        return response
