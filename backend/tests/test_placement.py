import cv2
import numpy as np
import pytest

from app.placement import PlacementAnalyzer, build_region_hint


def test_detect_returns_ranked_reviewable_candidate_for_synthetic_label():
    image = np.full((500, 800, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (80, 60), (720, 440), (20, 20, 20), 4)
    cv2.putText(image, "MRP Rs 50", (150, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 0, 0), 3)
    cv2.putText(image, "Net Qty 500 g", (150, 280), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)

    candidates = PlacementAnalyzer().detect(image)

    assert candidates
    assert candidates[0]["rank"] == 1
    assert candidates[0]["heuristic"] is True
    assert candidates[0]["authoritative"] is False
    assert candidates[0]["officer_review_required"] is True
    assert len(candidates[0]["bbox"]) == 4
    assert 0 <= candidates[0]["score"] <= 1


@pytest.mark.parametrize("fixture_name", ["sharp.png", "blurry.png"])
def test_detect_handles_existing_label_fixtures(fixture_name: str):
    fixture = f"/fixtures/{fixture_name}"
    image = cv2.imread(str(fixture))

    assert image is not None, f"fixture missing or unreadable: {fixture}"
    candidates = PlacementAnalyzer().detect(image)

    assert isinstance(candidates, list)
    assert candidates  # non-blank real label photos receive at least the surface fallback
    assert all(candidate["heuristic"] is True for candidate in candidates)
    assert all(candidate["authoritative"] is False for candidate in candidates)


def test_region_hint_explicitly_requires_officer_review():
    hint = build_region_hint("front", [])

    assert hint["status"] == "no_candidate_detected"
    assert hint["region"] is None
    assert hint["heuristic"] is True
    assert hint["authoritative"] is False
    assert hint["officer_review_required"] is True
    assert "not a legal placement determination" in hint["disclaimer"]
