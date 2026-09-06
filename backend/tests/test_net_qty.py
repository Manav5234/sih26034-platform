"""Smoke test for net quantity enhancement."""
import sys
import os
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, '.')

from app.extraction import extract_net_quantity


def test_net_qty_valid():
    """Valid net quantity extraction."""
    lines = [{"text": "Net Qty 500g", "confidence": 0.85}]
    result = extract_net_quantity(lines)
    assert result is not None
    assert result["value"] == 500.0
    assert result["unit"] == "g"


def test_net_qty_tablets():
    """Tablet quantity extraction."""
    lines = [{"text": "60 TABLETS", "confidence": 0.9}]
    result = extract_net_quantity(lines)
    assert result is not None
    assert result["value"] == 60.0
    assert result["unit"] == "tablets"


def test_net_qty_kg():
    """KG quantity extraction."""
    lines = [{"text": "Net Wt 2.5kg", "confidence": 0.88}]
    result = extract_net_quantity(lines)
    assert result is not None
    assert result["value"] == 2.5
    assert result["unit"] == "kg"


def test_net_qty_garbled_returns_none():
    """Garbled value returns None (Bug 2 guard)."""
    lines = [{"text": "Ps AD NET QUANTITY: ee Perey", "confidence": 0.350}]
    result = extract_net_quantity(lines)
    assert result is None


def test_net_qty_taelets_returns_none():
    """"60 TAELETS" should NOT match (not a plausible unit)."""
    lines = [{"text": "60 TAELETS", "confidence": 0.8}]
    result = extract_net_quantity(lines)
    assert result is None


def test_net_qty_tablfts_returns_none():
    """"60 TABLFTS" should NOT match (not a plausible unit)."""
    lines = [{"text": "60 TABLFTS", "confidence": 0.8}]
    result = extract_net_quantity(lines)
    assert result is None


def test_net_qty_raw_text():
    """Net quantity must include raw_text."""
    lines = [{"text": "Net Qty: 250ml", "confidence": 0.8}]
    result = extract_net_quantity(lines)
    assert result is not None
    assert "raw_text" in result
    assert len(result["raw_text"]) > 0