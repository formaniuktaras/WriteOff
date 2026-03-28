# WriteOff — private self-hosted event/accounting system (MVP foundation)

## Реалізаційний план по етапах

1. **Foundation/Infra**
   - FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL only.
   - Docker Compose (web, db, nginx), env-based config, storage/backups volumes.
2. **Security/Auth**
   - Role model (Admin/Operator/Viewer), argon2 password hashing, cookie session auth.
   - Route protection and role checks.
3. **Domain model + migration**
   - Events, multi-unit relation, event items (object/group), documents, valuations, valuation links, audit log.
4. **MVP UI**
   - Login, dashboard, dictionaries CRUD, events list + event detail tabs.
5. **File/document layer**
   - FileStorageService with safe filename + hashing.
   - TemplateGenerationService abstraction (MVP stub).
6. **Operational services**
   - Event export (zip bundle), backup service (pg_dump + storage copy), Excel dictionary import service.
7. **Bootstrap scripts**
   - seed roles, seed admin, init storage.

## Stack
- Python 3.12+
- FastAPI, Jinja2 (server-rendered UI)
- SQLAlchemy 2.x + Alembic
- PostgreSQL + psycopg3
- Passlib(argon2)
- Nginx reverse proxy
- Docker Compose

## Project structure

```text
app/
  api/ auth/ core/ db/ models/ schemas/ services/ templates/ static/ utils/
migrations/
scripts/
docker/
docker-compose.yml
```

## Local development

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_roles.py
python scripts/seed_admin.py --password 'ChangeMe!'
python scripts/init_storage.py
uvicorn app.main:app --reload
```

Open: http://localhost:8000/login

## Docker deployment

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec web python scripts/seed_roles.py
docker compose exec web python scripts/seed_admin.py --password 'ChangeMe!'
```

Open: http://localhost:8080/login

## Migration commands

```bash
alembic revision --autogenerate -m "..."
alembic upgrade head
alembic downgrade -1
```

## Security baseline
- `DEBUG=False` in production.
- Secrets only via `.env`.
- Session cookie: HttpOnly + SameSite + optional Secure flag.
- Password hashing: Argon2.
- Restricted upload extensions + sanitized filenames.
- Files stored on filesystem, metadata in DB.

## Current MVP capabilities
- Login/logout and role checks.
- Dictionaries (units/services/nomenclature/document types).
- Events list/create.
- Event detail tabs: General/Units/Items/Documents/Valuations/Audit.
- Residual valuation with `valuation_links`.
- Document uploads + download.
- Event export zip.
- Backup CLI scaffold.
- Excel import service scaffold with preview/import contract.

## Production notes
- Use TLS termination in front of nginx or add HTTPS config.
- Set `SESSION_SECURE=true` under HTTPS.
- Replace default DB credentials before deployment.
