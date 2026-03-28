.PHONY: install run migrate seed-roles seed-admin init-storage format

install:
	python -m pip install -r requirements.txt

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

migrate:
	alembic upgrade head

seed-roles:
	python scripts/seed_roles.py

seed-admin:
	python scripts/seed_admin.py

init-storage:
	python scripts/init_storage.py
