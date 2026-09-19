"""Tests for _normalize_mrp currency-warning behavior."""
import logging

from app.fusion import _normalize_mrp, ASSUMED_CURRENCY


def test_same_currency_returns_value_unchanged():
    result = _normalize_mrp(199.0, "INR")
    assert result == 199.0


def test_none_currency_returns_value_unchanged():
    result = _normalize_mrp(299.0, None)
    assert result == 299.0


def test_empty_currency_returns_value_unchanged():
    result = _normalize_mrp(149.0, "")
    assert result == 149.0


def test_case_insensitive_match():
    result = _normalize_mrp(199.0, "inr")
    assert result == 199.0


def test_whitespace_currency_matches():
    result = _normalize_mrp(199.0, "  INR  ")
    assert result == 199.0


def test_mismatched_currency_logs_warning(caplog):
    """Currency mismatch emits a WARNING on the app.fusion logger.

    The app logger has propagate=False (set by configure_app_logging),
    so we temporarily enable propagation on both app and app.fusion
    to let caplog capture the record via the root logger.
    """
    app_logger = logging.getLogger("app")
    fusion_logger = logging.getLogger("app.fusion")
    app_prop_old = app_logger.propagate
    fusion_prop_old = fusion_logger.propagate
    app_logger.propagate = True
    fusion_logger.propagate = True
    try:
        with caplog.at_level(logging.WARNING, logger="app.fusion"):
            result = _normalize_mrp(50.0, "USD")
    finally:
        app_logger.propagate = app_prop_old
        fusion_logger.propagate = fusion_prop_old

    assert result == 50.0
    assert "MRP currency differs from assumed currency" in caplog.text
    assert "USD" in caplog.text
    assert ASSUMED_CURRENCY in caplog.text


def test_numeric_comparison_unaffected_by_currency():
    """Same numeric value with different currency still returns the value.

    _normalize_mrp only logs; it does not alter the numeric comparison
    behavior that fuse_field() depends on.
    """
    assert _normalize_mrp(100.0, "INR") == _normalize_mrp(100.0, "USD")
    assert _normalize_mrp(100.0, "INR") == _normalize_mrp(100.0, None)
