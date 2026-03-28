from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models import User


def ui_context(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    return {"request": request, "db": db, "current_user": user}
