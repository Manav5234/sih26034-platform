"""Storage adapter interface and local-disk implementation.

Swap this for S3-compatible storage later by implementing the same ABC.
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

UPLOAD_ROOT = Path("/data/uploads")

# ponytail: single chokepoint cap. 512MB instance OOMs on 12MP+ phone photos
# (~36MB raw) once both OCR engines + 2x-upscale variants hold copies.
# Resized file is what OCR consumes AND what the evidence viewer serves,
# so bboxes stay in stored-image coords. Env-overridable for tests/tuning.
MAX_IMAGE_DIMENSION = int(os.getenv("MAX_IMAGE_DIMENSION", "2000"))


class StorageAdapter(ABC):
    @abstractmethod
    def save(self, scan_id: str, filename: str, data: bytes) -> str:
        """Save file, return the URL path (e.g. /uploads/{scan_id}/{uuid}.{ext})."""

    @abstractmethod
    def get_path(self, url_path: str) -> Path | None:
        """Resolve a URL path to the local filesystem path."""


def _maybe_downscale(data: bytes, ext: str) -> bytes:
    """Downscale images whose long edge exceeds MAX_IMAGE_DIMENSION.

    Returns the original bytes untouched when the image is already small
    (byte-identical passthrough) or undecodable (downstream returns 400).
    """
    import cv2
    import numpy as np

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        return data
    h, w = img.shape[:2]
    long_edge = max(h, w)
    if long_edge <= MAX_IMAGE_DIMENSION:
        return data
    scale = MAX_IMAGE_DIMENSION / long_edge
    small = cv2.resize(
        img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA
    )
    ok, buf = cv2.imencode(ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg", small)
    return bytes(buf) if ok else data


class LocalDiskStorage(StorageAdapter):
    def __init__(self, root: Path = UPLOAD_ROOT) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, scan_id: str, filename: str, data: bytes) -> str:
        ext = Path(filename).suffix.lower()
        safe_name = f"{uuid4().hex}{ext}"
        dest = self.root / scan_id
        dest.mkdir(parents=True, exist_ok=True)
        (dest / safe_name).write_bytes(_maybe_downscale(data, ext))
        return f"/uploads/{scan_id}/{safe_name}"

    def get_path(self, url_path: str) -> Path | None:
        if not url_path.startswith("/uploads/"):
            return None
        rel = url_path.removeprefix("/uploads/")
        p = self.root / rel
        return p if p.exists() else None


storage: StorageAdapter = LocalDiskStorage()
