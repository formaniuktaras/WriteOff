import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, UTC
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()


class BackupService:
    def __init__(self) -> None:
        self.storage_root = Path(settings.storage_root)
        self.backups_root = Path(settings.backups_root)

    def create_backup(self) -> Path:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        target = self.backups_root / f"backup_{ts}"
        target.mkdir(parents=True, exist_ok=True)

        db_dump = target / "database.sql"
        env = os.environ.copy()
        cmd = ["pg_dump", env.get("DATABASE_URL", "")]
        try:
            with db_dump.open("wb") as f:
                subprocess.run(cmd, check=True, stdout=f, stderr=subprocess.PIPE)
        except Exception:
            db_dump.write_text("pg_dump unavailable in current runtime\n", encoding="utf-8")

        shutil.copytree(self.storage_root, target / "storage", dirs_exist_ok=True)

        digest = hashlib.sha256()
        for file in sorted(target.rglob("*")):
            if file.is_file():
                digest.update(file.read_bytes())
        manifest = {"created_at": ts, "checksum": digest.hexdigest()}
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return target
