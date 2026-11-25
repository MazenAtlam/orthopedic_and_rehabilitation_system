# Amr Fekry’s HCIS contribution

Team 03 · Orthopedic and Rehabilitation System · Phases 0–4

## Requirements and evidence

| Phase | Assignment | Implementation and verification |
| --- | --- | --- |
| 0 | Database, FHIR and development conventions | PostgreSQL design, FHIR R4, Python and React conventions, and review of work on a branch from `develop`. |
| 1 | Data model, FHIR mapping and individual workload | Phase 1 Tables 1, 3, 6, 8 and 9 define the feature IDs, database, exchange contract and test responsibilities. |
| 2 | F09 billing, F10 simulated payments, F11 reports | `backend/app/api/v1/billing.py` captures price snapshots, serializes payments and supports idempotency. `backend/app/api/v1/reports.py` supplies date-filtered patient, financial and system aggregates. |
| 2 | F13 persistence and audit | The Alembic revisions create and protect 17 application tables. The demo seeder generates fictional clinic records. |
| 2 | F14 FHIR and F15 separate EMR | Flask exposes mapped R4 resources. `emr-client` reads patient details, appointments, visits, diagnoses, medication, rehabilitation and imaging through FHIR. |
| 2 | B1 ICD-10 | One local WHO catalog supplies the search API, coded diagnoses, invoices and grouped reports. |
| 3 | Imaging data and FHIR interoperability | `backend/app/services/imaging.py` supplies study registration, results, review and annotations. The integration tests check identifiers, access and audit transactions. |
| 4 | Individual demonstration and handoff | Run the acceptance walkthrough below and use the linked reports and discussion guide. |

The clinic frontend, team authentication, PACS and OHIF deployment, and live CDSS inference are tracked in the team components. The EMR accepts the team’s bearer JWT. The CLI provides a local demonstration while the authentication route is being integrated.

## Run in PyCharm on Windows

Open the team checkout as a PyCharm project. Create a Python 3.12 virtual environment and install `backend/requirements.txt`. Configure a Python run configuration with module name `flask`, parameters `--app wsgi run --host 127.0.0.1 --port 5000`, and working directory `backend`. Set `DATABASE_URL`, `JWT_SECRET_KEY` and `DEMO_MODE=1` in the run configuration for the local fictional demo. Supply the same values in the backend terminal. Use a local PostgreSQL database for the demo and a separate empty database for tests.

In a PowerShell terminal from the project root with the interpreter active:

```powershell
Set-Location backend
python -m alembic upgrade head
python -m flask --app wsgi load-icd10 --archive 'C:\path\icd102019enMeta.zip'
python -m flask --app wsgi seed-demo
python -m flask --app wsgi demo-fhir-token --role staff
```

Press the green Run button on the Flask configuration. In a second terminal from the project root:

```powershell
Set-Location emr-client
npm ci
npm run dev -- --host 127.0.0.1
```

Open [the EMR](http://127.0.0.1:5174) and paste the staff token. The demo CLI also supports `patient`, `other` and `admin` with a 15-minute lifetime. Keep tokens and the database connection and signing key on your machine.

For the Compose setup, start the team stack using the root README. Pass `DEMO_MODE=1` to the backend container and CLI for the demo. Use `docker compose cp` to place the official archive at `/tmp/icd102019enMeta.zip` in the backend container, then run `docker compose exec backend flask --app wsgi load-icd10 --archive /tmp/icd102019enMeta.zip`. The EMR container proxies `/api` to `backend:5000`.

## What to demonstrate

1. Connect as clinical staff. Select Nour Example and open Appointments, Visit history, Prescriptions and Rehabilitation. Visit history joins Encounter and Condition references. Rehabilitation links Observation measurements to Procedure sessions.
2. Open Imaging. Compare the ImagingStudy DICOM UID with the study reference on both DiagnosticReports. The fictional fixture has a final report and a preliminary result.
3. Sign out and reconnect with `patient`. The API returns one patient profile and the final report. Connect with `other` to check isolation. Connect with `admin` to confirm the administrative appointment view.
4. Save an Encounter with an imported ICD-10 code and post an invoice with that code. Open the patient and financial reports for the visit date. Submit a simulated payment and check the remaining invoice balance.
5. In an isolated PostgreSQL environment, run `python -m pytest --cov=app` in `backend` with `ORTHO_TEST_DATABASE_URL` set. Set `HCIS_ICD10_TEST_ARCHIVE` to run verification with the WHO archive. In `emr-client`, run `npm test` and `npm run build`.

## HTTP, FHIR and privacy

The browser sends HTTPS in a hosted configuration or HTTP on loopback for the demo. The Vite proxy serves API requests on the same origin as the client. The browser sends a bearer token in the Authorization header and requests `application/fhir+json`. The token stays in memory for the session. Flask validates the JWT, resolves the current role from PostgreSQL and applies the patient ownership filter in the query. The EMR handles a 401 by clearing the session. FHIR returns an OperationOutcome for API errors, a Bundle for searches and a CapabilityStatement describing role-available resources. The client follows only pagination links for the same origin, resource and patient filter.

The DICOM Study Instance UID identifies a study across applications. `scan_id` relates the rows inside PostgreSQL, and `DiagnosticReport.imagingStudy` refers to that ID. FHIR exposes the UID as an `urn:oid:` value with the identifier system `urn:dicom:uid`. The private Orthanc identifier remains in the database. Staff review moves pending results to accepted or rejected and commits the audit event with the state change. For patients, the FHIR query includes ownership and accepted-review filters.

Adapter callers open a transaction using the team database engine and pass the authenticated staff user ID to `register_study`, `record_cdss_result`, `review_cdss_result` and `record_annotation`. They supply the real PACS identifier when connecting the team components. The sample DICOM reference in the fixture is fictional.

## Git and recovery

In the team repository, branch from current `develop`, review the diff, commit the relevant changes, and open the pull request against `develop`. Wait for another team member to review and approve before merging. For a local and GitHub source check, fetch and compare the local commit with `origin/develop`, then confirm a clean working tree. Local environment settings and backups stay outside the shared source.

Use `pg_dump --format=custom` for PostgreSQL and maintain a corresponding Orthanc snapshot for a deployment that uses PACS. Restore to a separate empty database with `pg_restore --exit-on-error`, then check migration revision, counts and study to report relationships before switching connections.

- [WHO catalog import](../../../database/seed/README.md)
- [Phase 2 progress report](Team%2003%20-%20Amr%20Fekry%20-%20Phase%202%20Progress%20Report.pdf)
- [Phase 2 feature status and frontend review](PHASE_2_PROGRESS.md)
- [Phase 3 progress report](Team%2003%20-%20Amr%20Fekry%20-%20Phase%203%20Progress%20Report.pdf)
- [Final project and discussion guide](Team%2003%20-%20Amr%20Fekry%20-%20Final%20Project%20and%20Discussion%20Guide%20EN.pdf)
- [Final presentation](Team%2003%20-%20Amr%20Fekry%20-%20Final%20Presentation.pptx)
