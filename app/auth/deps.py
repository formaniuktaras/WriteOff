from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True), User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


def require_roles(*role_codes: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role.code not in role_codes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return user

    return dependency
