from app.db.session import SessionLocal
from app.models import Role
from app.models.enums import RoleCode


def main() -> None:
    db = SessionLocal()
    try:
        for code, name in [
            (RoleCode.ADMIN.value, "Admin"),
            (RoleCode.OPERATOR.value, "Operator"),
            (RoleCode.VIEWER.value, "Viewer"),
        ]:
            if not db.query(Role).filter(Role.code == code).first():
                db.add(Role(code=code, name=name))
        db.commit()
        print("Roles seeded")
    finally:
        db.close()


if __name__ == "__main__":
    main()
