from pathlib import Path

from app.core.config import get_settings


settings = get_settings()


def main() -> None:
    root = Path(settings.storage_root)
    for p in [
        root / "events",
        root / "templates",
        root / "exports",
        Path(settings.backups_root),
    ]:
        p.mkdir(parents=True, exist_ok=True)
        print(f"Created: {p}")


if __name__ == "__main__":
    main()
