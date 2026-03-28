from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        user_id: int | None,
        description: str,
        diff: dict | None = None,
    ) -> None:
        record = AuditLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            description=description,
            diff_json=diff,
            created_at=datetime.now(UTC),
        )
        self.db.add(record)
        self.db.flush()
