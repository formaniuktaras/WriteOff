from itsdangerous import URLSafeSerializer

from app.core.config import get_settings

settings = get_settings()
serializer = URLSafeSerializer(settings.secret_key, salt="session")


def create_session_token(user_id: int) -> str:
    return serializer.dumps({"uid": user_id})


def parse_session_token(token: str) -> int | None:
    try:
        data = serializer.loads(token)
        uid = data.get("uid")
        return int(uid)
    except Exception:
        return None
