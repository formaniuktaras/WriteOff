from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.ui import router as ui_router
from app.core.config import get_settings
from app.core.middleware import SessionAuthMiddleware

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie=settings.session_cookie_name,
    https_only=settings.session_secure,
    same_site=settings.session_samesite,
    max_age=settings.session_max_age,
)
app.add_middleware(SessionAuthMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth_router)
app.include_router(ui_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

