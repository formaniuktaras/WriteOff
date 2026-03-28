import csv
import json
import zipfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, Event, EventItem

settings = get_settings()


class EventExportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.root = Path(settings.storage_root)

    def export_event(self, event_id: int) -> Path:
        export_root = self.root / "exports"
        export_root.mkdir(parents=True, exist_ok=True)
        tmp_dir = export_root / f"event_{event_id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        event = self.db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise ValueError("Event not found")
        items = self.db.query(EventItem).filter(EventItem.event_id == event_id, EventItem.is_deleted.is_(False)).all()
        docs = self.db.query(Document).filter(Document.event_id == event_id, Document.is_deleted.is_(False)).all()

        with (tmp_dir / "event.json").open("w", encoding="utf-8") as f:
            json.dump({"id": event.id, "title": event.title, "event_date": event.event_date.isoformat()}, f, ensure_ascii=False)

        with (tmp_dir / "items.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "kind", "unit_id", "service_id", "qty"])
            writer.writeheader()
            writer.writerows([{"id": i.id, "kind": i.kind.value, "unit_id": i.unit_id, "service_id": i.service_id, "qty": i.qty} for i in items])

        bundle = export_root / f"event_{event_id}.zip"
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in tmp_dir.glob("*"):
                zf.write(file, arcname=file.name)
            for doc in docs:
                src = self.root / doc.file_path
                if src.exists():
                    zf.write(src, arcname=f"documents/{src.name}")
        return bundle
