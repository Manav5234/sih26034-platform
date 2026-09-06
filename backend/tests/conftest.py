"""conftest.py — test setup: pyzbar mock, JSONB compat, test DB."""
import sys
from unittest.mock import MagicMock

# Mock pyzbar before ANY app import (missing libzbar DLL on Windows)
if "pyzbar" not in sys.modules:
    sys.modules["pyzbar"] = MagicMock()
    sys.modules["pyzbar.pyzbar"] = MagicMock()

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"
