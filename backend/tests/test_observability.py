import json
import logging
import os

os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient

from app.main import app
from app.observability import JsonFormatter, request_id_var, scan_id_var, timed_stage


def test_health_response_contains_generated_request_id():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]


def test_health_response_preserves_client_request_id():
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "demo-trace-001"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "demo-trace-001"


def test_json_formatter_includes_request_and_scan_context():
    request_token = request_id_var.set("request-123")
    scan_token = scan_id_var.set("scan-456")
    try:
        record = logging.LogRecord(
            "app.pipeline", logging.INFO, __file__, 1, "stage_completed", (), None
        )
        record.request_id = request_id_var.get()
        record.scan_id = scan_id_var.get()
        record.stage = "ocr"
        record.elapsed_ms = 12.5

        payload = json.loads(JsonFormatter().format(record))
    finally:
        scan_id_var.reset(scan_token)
        request_id_var.reset(request_token)

    assert payload["request_id"] == "request-123"
    assert payload["scan_id"] == "scan-456"
    assert payload["stage"] == "ocr"
    assert payload["elapsed_ms"] == 12.5


def test_timed_stage_logs_elapsed_time(caplog):
    logger = logging.getLogger("observability.test")

    with caplog.at_level(logging.INFO, logger="observability.test"):
        with timed_stage(logger, "ocr", image_label="front"):
            pass

    completed = [record for record in caplog.records if record.msg == "stage_completed"]
    assert len(completed) == 1
    assert completed[0].stage == "ocr"
    assert completed[0].image_label == "front"
    assert completed[0].elapsed_ms >= 0
