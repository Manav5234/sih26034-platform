"""Tests for multi-source product lookup adapter chain."""
import pytest
import json
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, ProductCache
from app.product_lookup import (
    OpenFoodFactsAdapter, UPCitemdbAdapter, GS1GepirAdapter,
    ProductLookupAdapter, _ADAPTERS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# 1. OpenFoodFacts real barcode test
# ---------------------------------------------------------------------------

class TestOpenFoodFactsReal:
    """Test with a real barcode against OpenFoodFacts."""

    # Coca-Cola Zero Sugar — confirmed present on OpenFoodFacts
    REAL_BARCODE = "0049000042566"

    def test_real_barcode_found_on_openfoodfacts(self):
        """Real product should be found on Open Food Facts."""
        adapter = OpenFoodFactsAdapter()
        result = adapter.lookup(self.REAL_BARCODE)
        assert result is not None, f"Expected product to be found (barcode {self.REAL_BARCODE})"
        assert result.get("name") is not None
        assert "coca" in result.get("name", "").lower() or "cola" in result.get("name", "").lower()

    def test_openfoodfacts_returns_normalized_shape(self):
        """Returned dict should match the expected normalized shape."""
        adapter = OpenFoodFactsAdapter()
        result = adapter.lookup(self.REAL_BARCODE)
        assert result is not None
        # Must have at least one of: name, brand, category, manufacturer
        assert any(result.get(k) for k in ["name", "brand", "category", "manufacturer"])
        # If net_quantity present, must have value + unit
        if "net_quantity" in result:
            assert "value" in result["net_quantity"]
            assert "unit" in result["net_quantity"]


# ---------------------------------------------------------------------------
# 2. FreshHarvest not-found fallthrough
# ---------------------------------------------------------------------------

class TestFreshHarvestNotFound:
    """FreshHarvest deodorant barcode (personal care) should NOT be found
    in any food-focused adapter, and should complete cleanly without errors."""

    FRESHHARVEST_BARCODE = "8901542001406"

    def test_openfoodfacts_not_found(self):
        adapter = OpenFoodFactsAdapter()
        result = adapter.lookup(self.FRESHHARVEST_BARCODE)
        assert result is None

    def test_upcitemdb_not_found_without_key(self):
        """UPCitemdb should skip cleanly when no API key is set."""
        adapter = UPCitemdbAdapter()
        with patch.dict("os.environ", {"UPCITEMDB_API_KEY": ""}, clear=False):
            result = adapter.lookup(self.FRESHHARVEST_BARCODE)
        assert result is None

    def test_chain_returns_none(self):
        """Full adapter chain should return None for unknown personal-care barcode."""
        with patch.dict("os.environ", {"UPCITEMDB_API_KEY": ""}, clear=False):
            result = ProductLookupAdapter.lookup(self.FRESHHARVEST_BARCODE, db=None)
        assert result is None

    def test_chain_does_not_crash(self):
        """Verify no exceptions during fallthrough."""
        with patch.dict("os.environ", {"UPCITEMDB_API_KEY": ""}, clear=False):
            try:
                ProductLookupAdapter.lookup(self.FRESHHARVEST_BARCODE, db=None)
            except Exception as e:
                pytest.fail(f"Chain raised {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 3. Cache hit test
# ---------------------------------------------------------------------------

class TestCache:
    """Verify caching works — second lookup should not re-hit external APIs."""

    BARCODE = "0049000042566"  # Coca-Cola (confirmed in OFF)

    def test_cache_hit_on_second_lookup(self, db_session):
        """First lookup hits API, second lookup hits cache."""
        db_session.query(ProductCache).delete()
        db_session.flush()

        # First lookup — should call OpenFoodFacts
        adapter = OpenFoodFactsAdapter()
        mock_get = MagicMock(side_effect=adapter._get_json)

        with patch.object(OpenFoodFactsAdapter, "_get_json", mock_get):
            result1 = ProductLookupAdapter.lookup(self.BARCODE, db=db_session)

        # Second lookup — should NOT call any external API (cache hit)
        with patch.object(OpenFoodFactsAdapter, "_get_json", MagicMock()) as mock_get2:
            result2 = ProductLookupAdapter.lookup(self.BARCODE, db=db_session)

        assert result2 is not None, "Cache should return previously stored result"
        assert result1["name"] == result2["name"]
        mock_get2.assert_not_called()  # No external API call

    def test_not_found_is_cached(self, db_session):
        """Not-found results are also cached (avoid re-hitting APIs for known misses)."""
        db_session.query(ProductCache).delete()
        db_session.flush()

        barcode = "0000000000000"
        # First lookup
        ProductLookupAdapter.lookup(barcode, db=db_session)
        # Should be cached as not-found
        cached = db_session.query(ProductCache).filter(ProductCache.barcode == barcode).first()
        assert cached is not None
        assert cached.result is None
        assert cached.adapter is None

        # Second lookup should not crash
        result = ProductLookupAdapter.lookup(barcode, db=db_session)
        assert result is None


# ---------------------------------------------------------------------------
# 4. Evidence fusion with real data (integration test)
# ---------------------------------------------------------------------------

class TestFusionIntegration:
    """Verify that a real product lookup result integrates into evidence."""

    def test_pipeline_product_lookup_returns_normalized_data(self):
        """A real OpenFoodFacts lookup should return data in the shape
        the pipeline expects (name, brand, category, manufacturer)."""
        adapter = OpenFoodFactsAdapter()
        result = adapter.lookup("0049000042566")  # Coca-Cola
        assert result is not None
        # Pipeline accesses these keys:
        assert "name" in result or "brand" in result
        # pipeline.py:249: provider_data.get("name")
        # pipeline.py:250: provider_data.get("brand")
        # pipeline.py:251: provider_data.get("category")
        # pipeline.py:252: provider_data.get("manufacturer")
        if result.get("net_quantity"):
            assert "value" in result["net_quantity"]
            assert "unit" in result["net_quantity"]


# ---------------------------------------------------------------------------
# 5. Adapter ordering
# ---------------------------------------------------------------------------

class TestAdapterOrdering:
    def test_adapters_in_correct_order(self):
        names = [a.name for a in _ADAPTERS]
        assert names[0] == "openfoodfacts"
        assert names[1] == "upcitemdb"
        assert names[2] == "gs1gepir"


# ---------------------------------------------------------------------------
# 6. GS1Gepir best-effort
# ---------------------------------------------------------------------------

class TestGS1Gepir:
    def test_gepir_does_not_crash(self):
        adapter = GS1GepirAdapter()
        try:
            adapter.lookup("0049000042566")
        except Exception as e:
            pytest.fail(f"GS1Gepir raised {type(e).__name__}: {e}")
