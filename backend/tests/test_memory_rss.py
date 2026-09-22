"""Memory-RSS diagnostics: additive logging must never break the pipeline."""
import logging

from app.observability import log_inference_rss, log_rss, process_rss_mb


def test_process_rss_mb_returns_positive_or_none():
    rss = process_rss_mb()
    assert rss is None or rss > 0


def test_log_rss_emits_structured_line(caplog):
    # ponytail: non-"app" logger — the app hierarchy sets propagate=False.
    with caplog.at_level(logging.INFO, logger="test_memory_rss"):
        log_rss(logging.getLogger("test_memory_rss"), "memory_rss", stage="test_stage")
    assert any(
        r.getMessage() == "memory_rss" and getattr(r, "stage", None) == "test_stage"
        for r in caplog.records
    )


def test_log_inference_rss_logs_dims_for_real_file(caplog, tmp_path):
    import cv2
    import numpy as np

    p = tmp_path / "img.png"
    cv2.imwrite(str(p), np.zeros((40, 80, 3), dtype=np.uint8))
    with caplog.at_level(logging.INFO, logger="test_memory_rss"):
        log_inference_rss(logging.getLogger("test_memory_rss"), "test_pre", str(p), "single_pass")
    recs = [r for r in caplog.records if getattr(r, "stage", None) == "test_pre"]
    assert len(recs) == 1
    assert getattr(recs[0], "variant", None) == "single_pass"
    assert getattr(recs[0], "img_w", None) == 80
    assert getattr(recs[0], "img_h", None) == 40


def test_log_inference_rss_missing_file_never_raises(caplog):
    with caplog.at_level(logging.INFO, logger="test_memory_rss"):
        log_inference_rss(
            logging.getLogger("test_memory_rss"), "test_pre", "/nonexistent/x.png", "single_pass"
        )
    recs = [r for r in caplog.records if getattr(r, "stage", None) == "test_pre"]
    assert len(recs) == 1  # line still emitted, just without dims


def test_ensure_loaded_noop_emits_no_rss_lines(caplog):
    from app.ocr_provider import RapidOCRProvider
    p = RapidOCRProvider()
    p._initialized = True  # skip real model load; guard must stay silent
    p._engine = None
    with caplog.at_level(logging.INFO):
        assert p.extract("nonexistent.png") == {"tokens": [], "lines": []}
    assert not [r for r in caplog.records if getattr(r, "stage", "") in ("rapidocr_pre_load", "rapidocr_post_load")]
