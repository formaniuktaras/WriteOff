from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.auth.session import parse_session_token
from app.core.config import get_settings

settings = get_settings()


class SessionAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        token = request.cookies.get(settings.session_cookie_name)
        request.state.user_id = parse_session_token(token) if token else None
        return await call_next(request)
