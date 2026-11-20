# Amr Fekry's Phase 2 contribution

Orthopedic and Rehabilitation System, Team 03. The Phase 1 report assigns this work to Amr Fekry in Tables 8 and 9.

| Feature | Implementation |
| --- | --- |
| F09 | Service catalogue and invoices with itemized totals and prices captured at issue time. |
| F10 | Simulated payments, balance updates, idempotency and transaction locking. |
| F11 | Usage, patient and financial reports with date filters and data for charts. |
| F13 | PostgreSQL schema, Alembic migration, fictional seed records and an append-only audit log. |
| F14 | Role-filtered FHIR R4 search and reads, supported staff create interactions and a capability statement. |
| F15 | The local Phase 2 demo includes a separate EMR client. This contribution provides the FHIR API it consumes. |
| B1 | ICD-10 lookup, coded clinical records, invoice coding, diagnosis reports and FHIR Condition resources. |

The contribution also provides the Phase 1 database tables and scoped support for ownership checks, appointment overlap rules, coded visits and rehabilitation data.

## Run the backend checks

Use Python 3.12 and a dedicated empty PostgreSQL database. The test account needs permission to install the bundled PostgreSQL extension `btree_gist`. Set `ORTHO_TEST_DATABASE_URL` to that database with a `postgresql+psycopg://` URL. The suite applies the migration and seeds fictional records in the test database.

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Pytest generates temporary access tokens for its fixture accounts. Tests cover service pricing, payment retries and concurrency, authorization, reporting, database constraints, ICD-10 and FHIR request and response behavior.

## Integrate with the team application

Use `migrations/versions/0001_phase2.py` as the baseline migration for an empty team schema. Compare migration histories before applying it to an existing database. Set `DATABASE_URL` and run `python -m alembic upgrade head`. For a fictional development dataset, set `DEMO_MODE=1` and invoke `python -m flask --app ortho.app seed-demo`.

`ortho/app.py` supplies a headless Flask factory for the Phase 2 tests and API. It expects `DATABASE_URL` and `JWT_SECRET_KEY`. The billing, records, reports and FHIR blueprints use the team's authenticated session. The access adapter in `ortho/access.py` verifies the bearer token and resolves its database account, role and patient ownership. The application issuing tokens must use the same signing configuration and encode its database user ID as the token subject.

Billing, ICD-10 and report routes use `/api/v1`. FHIR clients use `/api/v1/fhir` with `Authorization: Bearer <access_token>`. The role-specific `GET /api/v1/fhir/metadata` endpoint lists available resources and interactions. The seeded ICD-10 entries are an orthopedic sample. All seeded patient and billing records are fictional.
