# WriteOff — private self-hosted event/accounting system (MVP foundation)

## Stack
- Python 3.12+
- FastAPI + Jinja2
- SQLAlchemy 2.x + Alembic
- PostgreSQL + psycopg3
- Docker Compose + Nginx

## Project structure

```text
app/
  api/ auth/ core/ db/ models/ schemas/ services/ templates/ static/ utils/
migrations/
scripts/
docker/
docker-compose.yml
```

## Environment configuration

There are 3 templates:

- `.env.example` — documented combined template (contains both local and Docker examples).
- `.env.local.example` — ready-to-use local host template (`localhost`, relative data dirs).
- `.env.docker.example` — ready-to-use Docker template (`db` service, container paths).

> Important: `db` works only inside Docker network (`docker compose`).
> For local host runs use `localhost` in `DATABASE_URL`.

---

## Local run on Windows

1. Install Python 3.12+ and PostgreSQL 16+.
2. Create environment file:
   ```powershell
   copy .env.local.example .env
   ```
3. Create and activate venv:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
4. Install deps:
   ```powershell
   pip install -r requirements.txt
   ```
5. Run migrations:
   ```powershell
   alembic upgrade head
   ```
6. Seed roles/admin:
   ```powershell
   python scripts/seed_roles.py
   python scripts/seed_admin.py --password "ChangeMe!"
   ```
7. Initialize storage and start app:
   ```powershell
   python scripts/init_storage.py
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
8. Open: http://localhost:8000/login

---

## Local run on Linux/macOS

1. Install Python 3.12+ and PostgreSQL 16+.
2. Create environment file:
   ```bash
   cp .env.local.example .env
   ```
3. Create and activate venv:
   ```bash
   python3.12 -m venv .venv
   source .venv/bin/activate
   ```
4. Install deps:
   ```bash
   pip install -r requirements.txt
   ```
5. Run migrations:
   ```bash
   alembic upgrade head
   ```
6. Seed roles/admin:
   ```bash
   python scripts/seed_roles.py
   python scripts/seed_admin.py --password 'ChangeMe!'
   ```
7. Initialize storage and start app:
   ```bash
   python scripts/init_storage.py
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
8. Open: http://localhost:8000/login

---

## Docker Compose run

1. Create `.env` from Docker profile:
   ```bash
   cp .env.docker.example .env
   ```
2. Build and start stack:
   ```bash
   docker compose up --build -d
   ```
3. Seed roles/admin (after web is healthy):
   ```bash
   docker compose exec web python scripts/seed_roles.py
   docker compose exec web python scripts/seed_admin.py --password 'ChangeMe!'
   ```
4. Open: http://localhost:8080/login

### Notes about startup reliability
- `db` has healthcheck (`pg_isready`).
- `web` waits for `db` readiness, then runs:
  - `alembic upgrade head`
  - `python scripts/init_storage.py`
  - `uvicorn ...`

This prevents web container crashes when PostgreSQL is started but not yet accepting connections.

---

## Migrations

```bash
alembic revision --autogenerate -m "..."
alembic upgrade head
alembic downgrade -1
```

## Current MVP capabilities
- Login/logout and role checks.
- Dictionaries (units/services/nomenclature/document types).
- Events list/create.
- Event detail tabs: General/Units/Items/Documents/Valuations/Audit.
- Residual valuation with explicit item→qty mapping.
- Document uploads + download.
- Event export zip.
- Backup CLI scaffold.
- Excel import service scaffold with preview/import contract.

## Production baseline
- Use strong `SECRET_KEY`.
- Keep `DEBUG=false`.
- Under HTTPS set `SESSION_SECURE=true`.
- Limit upload size via `MAX_UPLOAD_MB` and whitelist extensions.
- Replace default DB credentials before deployment.
