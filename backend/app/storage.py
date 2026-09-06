"""Storage adapter interface and local-disk implementation.

Swap this for S3-compatible storage later by implementing the same ABC.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

UPLOAD_ROOT = Path("/data/uploads")


class StorageAdapter(ABC):
    @abstractmethod
    def save(self, scan_id: str, filename: str, data: bytes) -> str:
        """Save file, return the URL path (e.g. /uploads/{scan_id}/{uuid}.{ext})."""

    @abstractmethod
    def get_path(self, url_path: str) -> Path | None:
        """Resolve a URL path to the local filesystem path."""


class LocalDiskStorage(StorageAdapter):
    def __init__(self, root: Path = UPLOAD_ROOT) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, scan_id: str, filename: str, data: bytes) -> str:
        ext = Path(filename).suffix.lower()
        safe_name = f"{uuid4().hex}{ext}"
        dest = self.root / scan_id
        dest.mkdir(parents=True, exist_ok=True)
        (dest / safe_name).write_bytes(data)
        return f"/uploads/{scan_id}/{safe_name}"

    def get_path(self, url_path: str) -> Path | None:
        if not url_path.startswith("/uploads/"):
            return None
        rel = url_path.removeprefix("/uploads/")
        p = self.root / rel
        return p if p.exists() else None


storage: StorageAdapter = LocalDiskStorage()
