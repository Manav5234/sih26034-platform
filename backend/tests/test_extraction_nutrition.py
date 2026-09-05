"""Tests for nutrition facts extraction."""
import pytest
from app.extraction import extract_nutrition_facts


class TestNutritionFacts:
    def test_basic_nutrition_panel(self):
        results = [
            {"text": "Nutrition Facts", "confidence": 0.90},
            {"text": "Energy 250 kcal", "confidence": 0.85},
            {"text": "Protein 5.2g", "confidence": 0.82},
            {"text": "Carbohydrate 30.1g", "confidence": 0.80},
            {"text": "Fat 12.0g", "confidence": 0.83},
        ]
        r = extract_nutrition_facts(results)
        assert r is not None
        assert len(r) >= 4
        labels = [n["nutrient"] for n in r]
        assert "energy" in labels
        assert "protein" in labels

    def test_header_case_insensitive(self):
        results = [
            {"text": "NUTRITION INFORMATION", "confidence": 0.90},
            {"text": "Total Fat 8g", "confidence": 0.85},
        ]
        r = extract_nutrition_facts(results)
        assert r is not None
        assert len(r) >= 1

    def test_no_header_returns_none(self):
        results = [
            {"text": "MRP Rs. 499.00", "confidence": 0.90},
            {"text": "Net Qty 500g", "confidence": 0.88},
        ]
        r = extract_nutrition_facts(results)
        assert r is None

    def test_empty_after_header_returns_empty_list(self):
        results = [{"text": "Nutrition Facts", "confidence": 0.90}]
        r = extract_nutrition_facts(results)
        assert r == []

    def test_garbled_value_included_with_zero_confidence(self):
        results = [
            {"text": "Nutrition Facts", "confidence": 0.90},
            {"text": "Protein xyz", "confidence": 0.85},
        ]
        r = extract_nutrition_facts(results)
        assert r is not None
        assert len(r) == 1
        assert r[0]["value"] is None
        assert r[0]["confidence"] == 0.0

    def test_per_100g_and_per_serving(self):
        results = [
            {"text": "Nutrition Facts per 100g", "confidence": 0.88},
            {"text": "Energy 350 kcal", "confidence": 0.85},
            {"text": "Protein 8.0g", "confidence": 0.82},
        ]
        r = extract_nutrition_facts(results)
        assert r is not None
        assert len(r) >= 2

    def test_zero_confidence_for_garbled(self):
        results = [
            {"text": "Nutrition Facts", "confidence": 0.90},
            {"text": "Protein 8.0g", "confidence": 0.78},
            {"text": "Fat xyzg", "confidence": 0.80},
        ]
        r = extract_nutrition_facts(results)
        assert r is not None
        protein = [n for n in r if n["nutrient"] == "protein"]
        fat = [n for n in r if n["nutrient"] == "fat"]
        assert len(protein) == 1
        assert protein[0]["value"] is not None
        assert protein[0]["confidence"] > 0
        assert len(fat) == 1
        assert fat[0]["value"] is None
        assert fat[0]["confidence"] == 0.0
