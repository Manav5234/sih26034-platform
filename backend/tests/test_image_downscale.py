"""Upload-path downscale: 12MP+ phone photos must not reach OCR at full res."""
import cv2
import numpy as np

from app.storage import MAX_IMAGE_DIMENSION, LocalDiskStorage


def _png(w: int, h: int) -> bytes:
    img = np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return bytes(buf)


def _stored_dims(storage: LocalDiskStorage, url: str):
    p = storage.get_path(url)
    assert p is not None
    img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
    assert img is not None
    h, w = img.shape[:2]
    return w, h


def test_large_image_capped_at_max_dimension(tmp_path):
    storage = LocalDiskStorage(root=tmp_path)
    url = storage.save("scan1", "photo.png", _png(4000, 3000))
    w, h = _stored_dims(storage, url)
    assert max(w, h) == MAX_IMAGE_DIMENSION
    assert (w, h) == (2000, 1500)  # aspect preserved


def test_portrait_large_image_capped(tmp_path):
    storage = LocalDiskStorage(root=tmp_path)
    url = storage.save("scan1", "photo.jpg", _png(3000, 4000))
    w, h = _stored_dims(storage, url)
    assert max(w, h) == MAX_IMAGE_DIMENSION
    assert (w, h) == (1500, 2000)


def test_small_image_passes_through_unchanged(tmp_path):
    storage = LocalDiskStorage(root=tmp_path)
    raw = _png(800, 400)
    url = storage.save("scan1", "small.png", raw)
    p = storage.get_path(url)
    assert p is not None
    assert p.read_bytes() == raw  # byte-identical, no re-encode


def test_undecodable_bytes_pass_through(tmp_path):
    storage = LocalDiskStorage(root=tmp_path)
    raw = b"not an image"
    url = storage.save("scan1", "bad.png", raw)
    p = storage.get_path(url)
    assert p is not None
    assert p.read_bytes() == raw
