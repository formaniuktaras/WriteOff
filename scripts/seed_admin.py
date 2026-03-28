import argparse

from app.auth.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default="Administrator")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.code == "admin").first()
        if not role:
            raise RuntimeError("Admin role is missing. Run seed_roles first")
        existing = db.query(User).filter(User.username == args.username).first()
        if existing:
            existing.password_hash = hash_password(args.password)
            existing.role_id = role.id
            existing.is_active = True
            print("Admin updated")
        else:
            db.add(User(username=args.username, full_name=args.full_name, password_hash=hash_password(args.password), role_id=role.id, is_active=True))
            print("Admin created")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
