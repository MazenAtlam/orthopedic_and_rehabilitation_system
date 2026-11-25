# Backend · Orthopedic & Rehabilitation System (Team 03)

Unified Flask + SQLAlchemy ORM backend for Phase 2 (F01–F14 & B1) and Phase 3 imaging/CDSS persistence hooks.

## Scope

| Area | Details |
| --- | --- |
| Schema & migrations (F13) | 17-table PostgreSQL Declarative ORM schema (`app/models/`), baseline Phase 2 revision (`migrations/versions/0001_phase2.py`) with `btree_gist` appointment overlap exclusion and append-only `audit_log` trigger, plus imaging/CDSS integrity constraints (`migrations/versions/0002_imaging_integrity.py`). |
| Auth, RBAC & accounts (F01–F03) | Patient registration, JWT access + HttpOnly refresh-cookie login/refresh/logout (`/api/v1/auth/*`), role/ownership guards, and admin user management (`/api/v1/users`). |
| Profiles & scheduling (F04, F05) | Patient and clinical staff directories (`/api/v1/patients`, `/api/v1/staff`), clinician availability (`/api/v1/staff/<id>/availability`), and half-open interval appointment booking, rescheduling, and cancellation (`/api/v1/appointments`). |
| Clinical EMR & rehab (F06–F08) | Medical visit records (`/api/v1/records`, `/api/v1/patients/<id>/records`), prescriptions (`/api/v1/records/<id>/prescriptions`, `/api/v1/patients/<id>/prescriptions`), rehabilitation treatment plans (`/api/v1/treatment-plans`), and rehab session logging (`/api/v1/treatment-plans/<id>/sessions`). |
| Billing & payments (F09, F10) | Service price catalogue (`GET`/`POST /api/v1/services`), invoicing with unit-price snapshots (`GET`/`POST /api/v1/invoices`, `GET /api/v1/invoices/<id>`), and idempotent simulated payment processing (`POST /api/v1/invoices/<id>/payments`). |
| Reporting & analytics (F11) | Date-filtered system, patient, and financial reports (`GET /api/v1/reports/system`, `/patients`, `/financial`). |
| ICD-10 coding (B1) | Catalogue lookup (`GET /api/v1/icd10?q=`), diagnosis and invoice coding, and diagnosis breakdown in patient reports. |
| HL7 FHIR R4 (F14) | Capability statement (`GET /api/v1/fhir/metadata`), search (`GET /api/v1/fhir/<ResourceType>`), read (`GET /api/v1/fhir/<ResourceType>/<id>`), create (`POST /api/v1/fhir/<ResourceType>`), and `OperationOutcome` errors across all 13 mapped resources. |
| Imaging persistence (Phase 3 adapter) | Transactional study, CDSS result, review, and annotation persistence helpers (`app/services/imaging.py`) for Phase 3 Orthanc/CDSS integration. |

## Backend checks

Run formatting, linting, static typing, and tests from `backend/`:

```text
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m black --check .
python -m flake8 .
python -m mypy app
python -m pytest -q
```

- `tests/unit/` and `tests/f01_f08/` run without external services (using isolated in-memory SQLite fixtures for F01–F08).
- `tests/integration/` exercises Alembic migrations, PostgreSQL `btree_gist` exclusion constraints, append-only `audit_log` triggers, concurrent `FOR UPDATE` payment locking, billing, reports, FHIR R4, and imaging persistence against a dedicated empty PostgreSQL database configured via `ORTHO_TEST_DATABASE_URL` (or `DATABASE_URL` when `APP_ENV=testing`).

## Integration and migrations

Set `DATABASE_URL` and run `python -m alembic upgrade head`. To load development fixtures, set `DEMO_MODE=1` and invoke `python -m flask --app wsgi seed-demo` (or `python -m scripts.seed`).

List endpoints under `/api/v1` return a bare JSON array by default and switch to `{"items": [...], "page", "page_size", "total"}` when `?page=`, `?page_size=`, or `?paginated=true` is supplied. The FHIR base path is `/api/v1/fhir`.

## PostgreSQL recovery

Use compatible PostgreSQL client tools and configure the connection through environment variables and a password file. Pair the daily PostgreSQL dump with the team Orthanc snapshot. For recovery verification, restore into a fresh isolated database with `pg_restore --exit-on-error --single-transaction`. Check the migration revision, table counts, and study-to-result links before returning the application to service.
