from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.security import verify_password
from app.auth.session import create_session_token, parse_session_token
from app.core.config import get_settings
from app.core.templating import templates
from app.db.session import get_db
from app.models import User
from app.services.audit_service import AuditService

settings = get_settings()
router = APIRouter(tags=["auth"])


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username, User.is_deleted.is_(False), User.is_active.is_(True)).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=400)

    user.last_login_at = datetime.now(UTC)
    AuditService(db).log(
        entity_type="auth",
        entity_id=str(user.id),
        action="login",
        user_id=user.id,
        description=f"User {user.username} logged in",
    )
    db.commit()

    response = RedirectResponse(url="/", status_code=303)
    token = create_session_token(user.id)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_secure,
        samesite=settings.session_samesite,
        max_age=settings.session_max_age,
    )
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(settings.session_cookie_name)
    user_id = parse_session_token(token) if token else None
    if user_id:
        user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
        if user:
            AuditService(db).log(
                entity_type="auth",
                entity_id=str(user.id),
                action="logout",
                user_id=user.id,
                description=f"User {user.username} logged out",
            )
            db.commit()

    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
