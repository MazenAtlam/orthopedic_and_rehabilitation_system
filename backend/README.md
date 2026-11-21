# Backend · Database, Billing, Reports & HL7 FHIR (Amr Fekry)

Orthopedic and Rehabilitation System, Team 03. This package contains the database, billing, reporting, and HL7 FHIR R4 integration work assigned to Amr Fekry in Phase 0 and Phase 1 (Tables 1, 8, and 9).

## Scope

| Area | Details |
| --- | --- |
| Schema & migrations (F13) | 17-table PostgreSQL schema (`app/models/schema_v1.py`), initial Phase 2 revision (`migrations/versions/0001_phase2.py`) with `btree_gist` appointment overlap exclusion and append-only `audit_log` trigger, plus imaging/CDSS integrity constraints (`migrations/versions/0002_imaging_integrity.py`). |
| Billing & payments (F09, F10) | Service price catalogue (`GET`/`POST /api/v1/services`), invoicing with unit-price snapshots (`GET`/`POST /api/v1/invoices`, `GET /api/v1/invoices/<id>`), and idempotent simulated payment processing (`POST /api/v1/invoices/<id>/payments`). |
| Reporting & analytics (F11) | Date-filtered system, patient, and financial reports (`GET /api/v1/reports/system`, `/patients`, `/financial`). |
| ICD-10 coding (B1) | Catalogue lookup (`GET /api/v1/icd10?q=`), diagnosis and invoice coding, and diagnosis breakdown in patient reports. |
| HL7 FHIR R4 (F14) | Capability statement (`GET /api/v1/fhir/metadata`), search (`GET /api/v1/fhir/<ResourceType>`), read (`GET /api/v1/fhir/<ResourceType>/<id>`), create (`POST /api/v1/fhir/<ResourceType>`), and `OperationOutcome` errors across all 13 mapped resources (`Patient`, `Practitioner`, `Appointment`, `Encounter`, `Condition`, `MedicationRequest`, `CarePlan`, `Procedure`, `Observation`, `ImagingStudy`, `DiagnosticReport`, `Invoice`, `PaymentNotice`). |

## Backend checks

Use Python 3.12 and a dedicated empty PostgreSQL database. The test account needs permission to install the bundled PostgreSQL extension `btree_gist`. Set `ORTHO_TEST_DATABASE_URL` to that database with a `postgresql+psycopg://` URL. Run the commands from the `backend/` directory:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests apply both migrations, seed fictional records, and generate temporary access tokens for the fixture accounts. They cover billing and concurrent payment updates, ownership and role restrictions, date-filtered reports, ICD-10, FHIR read and write interactions, review visibility on `ImagingStudy`/`DiagnosticReport`, and append-only audit writes.

## Integration and migrations

Set `DATABASE_URL` and run `python -m alembic upgrade head`. To load development fixtures, set `DEMO_MODE=1` and invoke `python -m flask --app wsgi seed-demo` (or `python -m scripts.seed`).

The API factory in `app/__init__.py` uses `DATABASE_URL` and `JWT_SECRET_KEY`. The access adapter (`app/utils/access.py`) verifies the team's bearer token and loads the database account, role, and patient ownership. The authentication endpoints issuing tokens must share the signing configuration and use the database `user_id` as the token subject.

Billing, ICD-10, and report routes use `/api/v1`. The FHIR base path is `/api/v1/fhir`. Send `Authorization: Bearer <access_token>` and use `GET /api/v1/fhir/metadata` to discover supported resources and interactions for the acting role.

## PostgreSQL recovery

Use compatible PostgreSQL client tools and configure the connection through environment variables and a password file. Pair the daily PostgreSQL dump with the team Orthanc snapshot. For recovery verification, restore into a fresh isolated database with `pg_restore --exit-on-error --single-transaction`. Check the migration revision, table counts, and study-to-result links before returning the application to service.
