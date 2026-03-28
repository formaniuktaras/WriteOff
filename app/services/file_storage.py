import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from slugify import slugify

from app.core.config import get_settings

settings = get_settings()


@dataclass
class StoredFile:
    relative_path: str
    sha256: str
    size: int


class FileStorageService:
    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.storage_root)

    def _safe_name(self, name: str) -> str:
        ext = ""
        if "." in name:
            ext = "." + name.split(".")[-1].lower()
        stem = slugify(name.rsplit(".", 1)[0])[:80] or "file"
        return f"{stem}{ext}"

    def _validate_extension(self, filename: str) -> None:
        allowed = {x.strip().lower() for x in settings.allowed_upload_extensions.split(",") if x.strip()}
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in allowed:
            raise ValueError("File extension is not allowed")

    async def save_event_document(self, event_id: int, upload: UploadFile, target_name: str | None = None) -> StoredFile:
        self._validate_extension(upload.filename or "")
        event_dir = self.root / "events" / str(event_id) / "documents"
        event_dir.mkdir(parents=True, exist_ok=True)

        filename = self._safe_name(target_name or upload.filename or "upload.bin")
        path = event_dir / filename
        hasher = hashlib.sha256()
        total = 0

        with path.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                hasher.update(chunk)
                f.write(chunk)

        rel = path.relative_to(self.root)
        return StoredFile(relative_path=str(rel), sha256=hasher.hexdigest(), size=total)

    def absolute(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if self.root.resolve() not in path.parents and path != self.root.resolve():
            raise ValueError("Unsafe path")
        return path
