"""Request correlation and structured logging helpers for the backend."""

from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Iterator


request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
scan_id_var: ContextVar[str | None] = ContextVar("scan_id", default=None)


class ContextFilter(logging.Filter):
    """Attach correlation IDs to every application log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.scan_id = scan_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """Emit compact, queryable JSON without logging request or image contents."""

    _extra_fields = (
        "event",
        "stage",
        "elapsed_ms",
        "image_label",
        "line_count",
        "barcode_count",
        "declaration_count",
        "overall_status",
        "method",
        "path",
        "status_code",
        "rss_mb",
        "variant",
        "img_w",
        "img_h",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "scan_id": getattr(record, "scan_id", None),
        }
        for field in self._extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_app_logging() -> None:
    """Configure JSON logs for app.* loggers once per process."""
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False

    if app_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ContextFilter())
    app_logger.addHandler(handler)


def process_rss_mb() -> float | None:
    """Current process RSS in MB, or None where unmeasurable.

    Reads /proc on Linux (Render); falls back to getrusage peak elsewhere.
    Stdlib only — no psutil dependency for a diagnostic.
    """
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    try:
        import resource
        import sys
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak / 1024, 1) if sys.platform.startswith("linux") else round(peak / 1024 / 1024, 1)
    except Exception:
        return None


def log_rss(logger: logging.Logger, event: str, *, stage: str, **extra: object) -> None:
    """Emit one structured memory log line; never raises, never changes behavior."""
    try:
        rss = process_rss_mb()
    except Exception:
        rss = None
    logger.info(
        event,
        extra={"event": event, "stage": stage, **({"rss_mb": rss} if rss is not None else {}), **extra},
    )


def log_inference_rss(
    logger: logging.Logger, stage: str, image_path: str, variant: str
) -> None:
    """RSS + on-disk dims for one OCR inference call; never raises.

    Reads dims with a throwaway imread purely for logging — the image bytes
    actually passed to the engine are untouched. The transient decode (~12MB
    at 2000px) is freed before inference starts.
    """
    w: int | None = None
    h: int | None = None
    try:
        import cv2

        img = cv2.imread(image_path)
        if img is not None:
            h, w = img.shape[:2]
    except Exception:
        w = h = None  # dims stay absent; the RSS line is still emitted
    extra: dict[str, object] = {"variant": variant}
    if w is not None and h is not None:
        extra.update(img_w=w, img_h=h)
    log_rss(logger, "memory_rss", stage=stage, **extra)


@contextmanager
def pipeline_context(
    logger: logging.Logger,
    *,
    request_id: str | None,
    scan_id: str,
) -> Iterator[None]:
    """Bind correlation IDs and log the full pipeline duration."""
    request_token = request_id_var.set(request_id) if request_id else None
    scan_token = scan_id_var.set(scan_id)
    started = time.perf_counter()
    logger.info("pipeline_started", extra={"event": "pipeline_started", "stage": "pipeline"})
    try:
        yield
    except Exception:
        logger.exception(
            "pipeline_failed",
            extra={
                "event": "pipeline_failed",
                "stage": "pipeline",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        raise
    else:
        logger.info(
            "pipeline_completed",
            extra={
                "event": "pipeline_completed",
                "stage": "pipeline",
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
    finally:
        scan_id_var.reset(scan_token)
        if request_token is not None:
            request_id_var.reset(request_token)


@contextmanager
def timed_stage(logger: logging.Logger, stage: str, **extra: object) -> Iterator[None]:
    """Record a stage's outcome and elapsed time without affecting its behavior."""
    started = time.perf_counter()
    logger.info("stage_started", extra={"event": "stage_started", "stage": stage, **extra})
    try:
        yield
    except Exception:
        logger.exception(
            "stage_failed",
            extra={
                "event": "stage_failed",
                "stage": stage,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                **extra,
            },
        )
        raise
    else:
        logger.info(
            "stage_completed",
            extra={
                "event": "stage_completed",
                "stage": stage,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                **extra,
            },
        )
