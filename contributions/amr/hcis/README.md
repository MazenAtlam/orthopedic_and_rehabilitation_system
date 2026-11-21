# HCIS final contribution · Amr Fekry

Orthopedic and Rehabilitation System, Team 03. This contribution covers the database, billing and health data exchange work assigned to Amr in the Phase 0 roles and Phase 1 Tables 8 and 9, through the Phase 4 individual handoff.

## Scope by phase

| Phase | Individual work |
| --- | --- |
| Phase 0 and Phase 1 | PostgreSQL and FHIR design, including the 17-table schema, API resource mappings and access rules. |
| Phase 2 | F09 service catalogue and billing, F10 simulated payments, F11 reporting, F13 database and audit log, F14 FHIR R4 API, and B1 ICD-10 lookup and coding. F15 provides a separate runnable React EMR that consumes the FHIR API. B1 includes the orthopedic ICD-10 importer. |
| Phase 3 | Persistence adapters for DICOM study registration, annotations, and CDSS results and reviews. Patient ownership and reviewer constraints are applied by the second migration. FHIR links diagnostic reports to the corresponding study. |
| Phase 4 | Integration tests, a PostgreSQL recovery check, and handoff instructions for the team. The submission includes the working prototype, the individual progress reports, the English discussion guide and the presentation. |

The contribution includes database and FHIR support for ownership checks, appointment overlap rules, coded visits and rehabilitation data. The local demo uses fictional clinical records, an orthopedic ICD-10 demo fixture and simulated payments.

## Run the standalone contribution

Open this directory in PyCharm and select Python 3.12. Set `DATABASE_URL` to your PostgreSQL database with a `postgresql+psycopg://` URL. Set `JWT_SECRET_KEY` to a unique value of at least 32 bytes. For the fictional demo, set `DEMO_MODE=1` in the backend terminal and run configuration.

```powershell
python -m pip install -r requirements.txt
python -m alembic upgrade head
python -m flask --app ortho.app seed-demo
python -m flask --app ortho.app demo-fhir-token --role staff
```

Start Flask with `python -m flask --app ortho.app run --host 127.0.0.1 --port 5000`. To use the green Run button, make a Python run configuration with module name `flask`, the same parameters and this contribution directory as its working directory.

In a second terminal from the contribution directory:

```powershell
Set-Location emr-client
npm ci
npm run dev -- --host 127.0.0.1
```

Open [the EMR](http://127.0.0.1:5174) and paste the staff token. The demo CLI also supports `patient`, `other` and `admin`. These tokens last 15 minutes. The client uses the same-origin Vite proxy, which sends `/api` requests to Flask. Its access token stays in memory, and the backend assigns the role and enforces ownership on every request.

## Import the orthopedic ICD-10 catalog

Download the English 2019 metadata file named `icd102019enMeta.zip` from the [WHO ICD-10 download page](https://icdcdn.who.int/icd10/index.html). After the migrations, run this command from the contribution directory:

```powershell
python -m flask --app ortho.app load-icd10 --archive 'C:\path\icd102019enMeta.zip'
```

The importer checks the archive and upserts 679 orthopedic codes while preserving existing references. The WHO archive is obtained locally. Staff can look up an imported code at `GET /api/v1/icd10?q=M16.1`. The code is available to diagnosis, billing and reporting workflows.

## Backend checks

Use Python 3.12 and a dedicated empty PostgreSQL database. The test account needs permission to install the bundled PostgreSQL extension `btree_gist`. Set `ORTHO_TEST_DATABASE_URL` to that database with a `postgresql+psycopg://` URL. Run the commands from this contribution's directory.

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The tests apply both migrations, seed fictional records, and generate temporary access tokens for the fixture accounts. They cover billing and concurrent payment updates, ownership and role restrictions, date-filtered reports, ICD-10, FHIR read and write interactions, consistent study registration, review visibility and atomic audit writes.

Set `HCIS_ICD10_TEST_ARCHIVE` to the locally downloaded ZIP to verify the full terminology import. From `emr-client`, run `npm ci`, `npm test` and `npm run build` to verify the client.

## Integration and migrations

Compare migration histories before applying these revisions to a shared database. The initial revision creates the Phase 1 tables. The second revision requires studies to reference visits owned by the same patient and requires a staff reviewer for a completed review. Resolve inconsistent legacy rows on a restored copy before migrating.

Set `DATABASE_URL` and run `python -m alembic upgrade head`. To load development fixtures, set `DEMO_MODE=1` and invoke `python -m flask --app ortho.app seed-demo`.

The API factory in `ortho/app.py` uses `DATABASE_URL` and `JWT_SECRET_KEY`. The access adapter verifies the team's bearer token and loads the database account, role and patient ownership. The application issuing tokens must share the signing configuration and use its database user ID as the token subject.

Billing, ICD-10, coded-record and report routes use `/api/v1`. The FHIR base path is `/api/v1/fhir`. Send `Authorization: Bearer <access_token>` and use `GET /api/v1/fhir/metadata` to discover supported resources and interactions for the acting role.

## Imaging and CDSS handoff

The team's PACS, viewer and inference services call the persistence adapter after authenticating the caller. Pass the server-resolved staff account ID and a connection inside an `engine.begin()` transaction. The transaction boundary commits the change and its audit event together.

| Function in `ortho/imaging.py` | Contract |
| --- | --- |
| `register_study` | Persists the patient, optional visit, raw DICOM Study Instance UID and internal Orthanc ID. Exact retries return the existing study. Conflicting metadata for the same UID returns 409. |
| `record_cdss_result` | Adds a pending result to a study with its model version and optional finding, confidence and report text. The inference service deduplicates job delivery. |
| `review_cdss_result` | Records an authorized staff decision as accepted or rejected. Repeating the same reviewer and decision returns the existing result. |
| `record_annotation` | Saves an arrow, length, angle or note with a JSON object linked to the study. The viewer owns the interpretation of its geometry. |

`ImagingStudy.identifier` contains the DICOM Study UID. `DiagnosticReport.imagingStudy` links the report to the study. Pending, accepted and rejected results map to FHIR `preliminary`, `final` and `entered-in-error`. A patient receives only their own accepted reports. The local demo exercises these contracts with fictional study metadata. Live Orthanc and inference execution are part of the team integration.

## PostgreSQL recovery

Use compatible PostgreSQL client tools and configure the connection through environment variables and a password file. Pair the daily PostgreSQL dump with the team Orthanc snapshot. For recovery verification, restore into a fresh isolated database with `pg_restore --exit-on-error --single-transaction`. Check the migration revision, table counts and study-to-result links before returning the application to service.

## Phase 4 deliverables

- [English project and discussion guide](docs/Team%2003%20-%20Amr%20Fekry%20-%20Final%20Project%20and%20Discussion%20Guide%20EN.pdf)
- [Phase 2 progress report](docs/Team%2003%20-%20Amr%20Fekry%20-%20Phase%202%20Progress%20Report.pdf)
- [Phase 3 progress report](docs/Team%2003%20-%20Amr%20Fekry%20-%20Phase%203%20Progress%20Report.pdf)
- [Team integration presentation](docs/Team%2003%20-%20Amr%20Fekry%20-%20Final%20Presentation.pptx)
