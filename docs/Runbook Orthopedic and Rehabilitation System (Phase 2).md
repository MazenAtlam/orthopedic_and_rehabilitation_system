# Runbook: Orthopedic and Rehabilitation System (Phase 2)

Team 03 · Healthcare Information System course project · Repository branch: `develop`

## 1. About this runbook

This runbook explains how to install, start, and test the Phase 2 system (healthcare system, FHIR API, and EMR client). It has four parts: Prerequisites, Getting Started, Run Guide, and Test Cases.

- **Scope.** Phase 2 only: login, users, patients, appointments, EMR, prescriptions, rehabilitation plans, billing and simulated payments, reports, FHIR R4, and the EMR client. The Phase 3 imaging services (Orthanc, OHIF, CDSS) start only with `--profile imaging` and are not tested here.
- **How the expected results were written.** They come from reading the project code, the migrations, and the README. Run the test cases once on a clean machine and fix any line that does not match what you see.
- **Test case format.** Every test case has: Type (Normal or Edge), Steps, and Expected result. The expected result says whether it is **Visual** (what you see in the browser or terminal), **Database** (what you see in PostgreSQL), or both.
- **Names.** Demo data is fictional. All demo passwords are `Test@12345`.

## 2. Prerequisites

### 2.1 Software

| Item | Needed for | How to check |
| --- | --- | --- |
| Git | Clone the repository | `git --version` |
| Docker Desktop (Windows, macOS) or Docker Engine with the Compose plugin (Linux) | Run all services | `docker --version` |
| Docker Compose v2 (command `docker compose`, with a space) | Start and stop services | `docker compose version` |
| A web browser (Chrome, Edge, or Firefox) | Use the web app and EMR client | Open any page |
| `curl` (Git Bash, Linux, or macOS terminal) | API test cases | `curl --version` |

Optional, only to run tests outside Docker: Python 3.12, Node.js 20, and PostgreSQL 16.

### 2.2 Machine

- Internet access for the first build (Docker images and packages are downloaded).
- Free disk space of a few GB for images and the database volume.
- These ports must be free: **80** (Nginx), **5000** (backend), **5173** (web app), **5174** (EMR client), **5432** (PostgreSQL).
- Windows users: run the commands in Git Bash or PowerShell. The test helper scripts below use Bash, so use Git Bash for them.

### 2.3 Accounts and files

- Access to the GitHub repository `https://github.com/MazenAtlam/orthopedic_and_rehabilitation_system.git`.
- No cloud accounts or API keys are needed.

## 3. Getting Started (Setup and Installation)

### Step 1. Get the code

```bash
git clone https://github.com/MazenAtlam/orthopedic_and_rehabilitation_system.git
cd orthopedic_and_rehabilitation_system
```

If you downloaded the ZIP file instead, unzip it and open a terminal in the folder that contains `docker-compose.yml`.

### Step 2. Create the `.env` file

```bash
# Linux / macOS / Git Bash
cp .env.example .env
# Windows PowerShell
Copy-Item .env.example .env
```

### Step 3. Change the secrets in `.env`

Change these three values: `POSTGRES_PASSWORD`, `SECRET_KEY`, `JWT_SECRET_KEY`. Create a secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

- Also put the same database password inside `DATABASE_URL`.
- Do not use the characters `@ : / #` in the database password.
- To test with demo data, keep `DEMO_MODE=1`, `SEED_ON_START=true`, and `APP_ENV=development`.
- Keep `LOAD_ICD10_ON_START=true` so the ICD-10 catalogue is loaded.

### Step 4. Build and start

```bash
docker compose up --build
```

Use `docker compose up -d --build` to run in the background. On the first start the backend does these things in order: applies the migrations (`alembic upgrade head`), loads the ICD-10 catalogue, and loads the demo data.

### Step 5. Check that everything is healthy

```bash
docker compose ps
```

**Expected:** the services `db`, `backend`, `frontend`, `emr-client`, and `nginx` show `running` and `healthy`. The first start can take a few minutes. Then open:

| Check | URL | Expected |
| --- | --- | --- |
| API health through Nginx | http://localhost/api/v1/health | `{"status":"ok"}` |
| Web application | http://localhost | Login page titled "OrthoRehab HIS" |
| EMR client | http://localhost:5174 | Page "EMR client" with "Connect to patient records" |

## 4. Run Guide

### 4.1 Addresses

| Service | URL |
| --- | --- |
| Web application (use this one) | http://localhost |
| API base path | http://localhost/api/v1 |
| EMR client | http://localhost:5174 |
| Backend directly | http://localhost:5000/api/v1/health |
| PostgreSQL | `localhost:5432` (user, password, and database from `.env`) |

### 4.2 Demo accounts

Password for all accounts: `Test@12345`.

| Email | Role | What it has |
| --- | --- | --- |
| `admin@hcis.test` | Admin | Manages users, service prices, invoices, all reports |
| `doctor1@hcis.test` | Clinical staff (doctor) | A booked appointment with patient 1 on the day after seeding, 10:00 to 10:30 UTC |
| `physio1@hcis.test` | Clinical staff (physiotherapist) | Second staff account |
| `patient1@hcis.test` | Patient | A visit, a rehabilitation plan, and one unpaid invoice of 500.00 EGP |
| `patient2@hcis.test` | Patient | A separate visit and a partially paid invoice (use it to test ownership) |
| `patient3@hcis.test` | Patient | Clean account for lock and deactivation tests |

Demo services: Consultation 300.00, Physio session 250.00, X-ray imaging 400.00 (EGP).

### 4.3 What each role sees in the sidebar

| Sidebar item | Admin | Staff | Patient |
| --- | --- | --- | --- |
| Dashboard & Reports | Yes | Yes | Yes |
| User Management | Yes | No | No |
| Appointments | Yes | Yes | Yes |
| Musculoskeletal EMR | No | Yes | Yes |
| Rehab & Physio Plans | No | Yes | Yes |
| Orthanc DICOM & CDSS | No | Yes | Yes |
| Billing & ICD-10 | Yes | Yes | Yes |

Opening a page your role cannot use sends you back to `/dashboard`. Opening any page without logging in sends you to `/login`.

### 4.4 Using the EMR client

The EMR client asks for an access token. Create one with the demo command:

```bash
docker compose exec backend python -m flask --app wsgi demo-fhir-token --role staff
```

Copy the printed token, open http://localhost:5174, paste it into **Access token**, and click **Connect**. This command works only when `DEMO_MODE=1` and the environment is not production.

### 4.5 Useful commands

| Task | Command |
| --- | --- |
| Show service status | `docker compose ps` |
| Follow backend logs | `docker compose logs -f backend` |
| Stop, keep the data | `docker compose down` |
| Stop and delete the database (fresh start) | `docker compose down -v` |
| Apply a changed `.env` | `docker compose up -d --force-recreate` |
| Restart only the backend | `docker compose restart backend` |
| Open the database shell | `docker compose exec db psql -U hcis_user -d hcis_db` |
| Reload the demo data | `docker compose exec backend python -m scripts.seed` |

### 4.6 Helper commands for the test cases

Paste these in Git Bash. They create one token per demo account. A token lives 15 minutes; run the block again if you get `401`.

```bash
API=http://localhost/api/v1
login() { curl -s -X POST $API/auth/login -H "Content-Type: application/json" \
  -d "{\"email\":\"$1\",\"password\":\"Test@12345\"}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])"; }
ADMIN=$(login admin@hcis.test); DOCTOR=$(login doctor1@hcis.test)
PHYSIO=$(login physio1@hcis.test); P1=$(login patient1@hcis.test); P2=$(login patient2@hcis.test)
psql_run() { docker compose exec -T db psql -U hcis_user -d hcis_db -c "$1"; }
```

Find the IDs used in the cases:

```bash
psql_run "SELECT s.staff_id, u.email FROM staff s JOIN \"user\" u ON u.user_id = s.user_id;"
psql_run "SELECT p.patient_id, u.email FROM patient p JOIN \"user\" u ON u.user_id = p.user_id;"
psql_run "SELECT appointment_id, staff_id, patient_id, start_time, end_time, status FROM appointment;"
```

In the cases below, `DOCTOR_ID` is the staff\_id of `doctor1`, `P1_ID` and `P2_ID` are the patient\_id values of `patient1` and `patient2`, and `D` is the date of the day after seeding (format `YYYY-MM-DD`). Note: `user` is a reserved word in PostgreSQL, so write `"user"` with double quotes in SQL.

### 4.7 Run the automated tests

```bash
docker compose exec backend black --check .
docker compose exec backend flake8 .
docker compose exec backend mypy app
docker compose exec backend pytest
docker compose exec frontend npm test
docker compose exec emr-client npm test
```

The backend integration tests need an **empty** PostgreSQL database set in `ORTHO_TEST_DATABASE_URL`. Never point it at the demo database.

### 4.8 Troubleshooting

| Problem | Fix |
| --- | --- |
| `Copy .env.example to .env first` | You skipped Step 2. Create `.env`. |
| Port already in use | Stop the program that uses the port, or change the port mapping in `docker-compose.yml`. |
| Windows: `entrypoint.sh` errors or `\r` characters | The file needs LF line endings. Run `git add --renormalize .` and rebuild. |
| Page does not reload after a code change on Windows | Keep `CHOKIDAR_USEPOLLING=true` in `.env`. |
| `.env` change has no effect | Run `docker compose up -d --force-recreate`. |
| Login works but data is missing | The seed did not run. Check `DEMO_MODE=1` and `SEED_ON_START=true`, then run `docker compose exec backend python -m scripts.seed`. |
| `401` on an API call | The 15-minute token expired. Log in again. |

## 5. Test Cases

If a test changes data, run `docker compose down -v` and `docker compose up --build` to return to the clean demo state before the next group.

### 5.1 Setup and health

**TC-01 · All services start and become healthy** (Normal)

- Steps: complete Section 3, then run `docker compose ps`.
- Expected (Visual): `db`, `backend`, `frontend`, `emr-client`, and `nginx` show `healthy`. No service is restarting or `exited`.

**TC-02 · Health check** (Normal)

- Steps: open http://localhost/api/v1/health and http://localhost:5000/api/v1/health.
- Expected (Visual): both pages show `{"status":"ok"}` with HTTP 200.

**TC-03 · Migrations and seed data created** (Normal)

- Steps: run `psql_run "\dt"`, then `psql_run "SELECT count(*) FROM \"user\";"`, `psql_run "SELECT name, price FROM service;"`, `psql_run "SELECT count(*) FROM icd10_code;"`.
- Expected (Database): 17 application tables plus `alembic_version`. `user` has 6 rows. `service` shows Consultation 300.00, Physio session 250.00, X-ray imaging 400.00. `icd10_code` has at least 679 rows and includes `M17.9`.

**TC-04 · Restart keeps data and the seed does not duplicate it** (Edge)

- Steps: run `docker compose down`, then `docker compose up -d`. Wait until healthy. Repeat the count queries from TC-03.
- Expected (Database): `user` still has 6 rows, `service` still has 3 rows. No duplicate emails.
- Expected (Visual): you can still sign in with `admin@hcis.test`.

**TC-05 · Start without a `.env` file** (Edge)

- Steps: rename `.env` to `.env.bak`, run `docker compose up`, then rename it back.
- Expected (Visual): Compose stops with the message `Copy .env.example to .env first`. No containers start.

**TC-06 · Port 80 already in use** (Edge)

- Steps: start any program on port 80, then run `docker compose up`.
- Expected (Visual): `nginx` cannot start and Compose shows a port-binding error. After you stop the other program and run `docker compose up -d`, the site opens at http://localhost.

### 5.2 Authentication and registration

**TC-07 · Login for each role** (Normal)

- Steps: open http://localhost. Sign in with `admin@hcis.test`, sign out, then `doctor1@hcis.test`, sign out, then `patient1@hcis.test`.
- Expected (Visual): after each login you land on `/dashboard`. The sidebar matches the table in Section 4.3 for that role. The button shows "Signing In..." while the request runs.
- Expected (Database): `SELECT action, resource FROM audit_log ORDER BY log_id DESC LIMIT 6;` shows `login` and `logout` rows for the three users.

**TC-08 · Wrong password** (Edge)

- Steps: sign in with `patient1@hcis.test` and password `Wrong@123`.
- Expected (Visual): a red alert shows "Invalid email or password." You stay on the login page.
- Expected (Database): a new `audit_log` row with action `login_failed` for that user.

**TC-09 · Unknown email** (Edge)

- Steps: sign in with `nobody@hcis.test` and any password.
- Expected (Visual): the same message, "Invalid email or password." The message does not say whether the email exists.
- Expected (Database): no `login_failed` row (there is no user to link it to).

**TC-10 · Account lock after 5 failed logins** (Edge)

- Steps: use `patient3@hcis.test`. Enter a wrong password 5 times. Then enter the **correct** password `Test@12345`.
- Expected (Visual): attempts 1 to 4 show "Invalid email or password." Attempt 5 and the correct-password attempt show "Too many failed attempts. Try again in N seconds." (N is up to 900, the 15-minute lock).
- Expected (Database): `login_failed` rows for this user. No `login` row for the blocked attempt.
- Reset: the counter is kept in the backend's memory, so `docker compose restart backend` clears the lock.

**TC-11 · Login form checks** (Edge)

- Steps: (a) submit the form with an empty email. (b) type `abc` in the email field. (c) with curl, send a login without a password: `curl -s -X POST $API/auth/login -H "Content-Type: application/json" -d '{"email":"patient1@hcis.test"}'`.
- Expected (Visual): (a) and (b) the browser stops the submit with a field message and no request is sent. (c) HTTP 400 with the message "A password is required."

**TC-12 · Patient registration** (Normal)

- Steps: on the login page click "Register for Patient Portal". Fill full name `Test Patient`, email `new.patient@hcis.test`, password `Valid@12345`, birth date `1995-05-20`, gender, and phone `+20 100 123 4567`. Submit.
- Expected (Visual): you go to `/dashboard` as the new patient. The sidebar shows the patient items.
- Expected (Database): `SELECT u.email, u.role, p.full_name FROM "user" u JOIN patient p ON p.user_id = u.user_id WHERE u.email='new.patient@hcis.test';` returns one row with role `patient`. The password is stored as a bcrypt hash starting with `$2`, not as plain text. An `audit_log` row with action `register` exists.

**TC-13 · Register with an email that already exists** (Edge)

- Steps: register again with `new.patient@hcis.test`, or use `patient1@hcis.test`.
- Expected (Visual): the form shows "An account with this email already exists." (HTTP 409).
- Expected (Database): no new row in `user` or `patient`.

**TC-14 · Password rules** (Edge)

- Steps: register with a 7-character password (`Abc@123`). Then try a password longer than 72 bytes (80 letters).
- Expected (Visual): HTTP 422 `validation_failed` with the field `password`. The short one says "Must contain between 8 and 128 characters." The long one says "Must be at most 72 bytes when encoded as UTF-8."
- Expected (Database): no new user row.

**TC-15 · Birth date rules** (Edge)

- Steps: register with birth date (a) tomorrow, (b) `2026-02-30`, (c) `20/05/1995`.
- Expected (Visual): HTTP 422 on `birth_date`: (a) "Must be today or earlier." (b) "Must be a real calendar date." (c) "Must be a date in YYYY-MM-DD format."
- Expected (Database): no new row.

**TC-16 · Protected pages and role guard** (Edge)

- Steps: (a) while signed out, open http://localhost/billing. (b) sign in as `patient1@hcis.test` and open http://localhost/users.
- Expected (Visual): (a) you are sent to `/login`. (b) you are sent to `/dashboard` and User Management is not shown.

**TC-17 · Sign out** (Normal)

- Steps: sign in as any user, click the sign-out button in the sidebar, then press the browser Back button.
- Expected (Visual): you return to the login page. Back does not show the dashboard data.
- Expected (Database): an `audit_log` row with action `logout` for that user.

### 5.3 User management (admin)

**TC-18 · Admin creates a staff account** (Normal)

- Steps: sign in as admin, open **User Management**, create a user with a new email (for example `doctor2@hcis.test`), password `Valid@12345`, role Clinical Staff, staff type Doctor, a name, and a specialty.
- Expected (Visual): the new user appears in the list. Filter by role "Clinical Staff" shows it.
- Expected (Database): one new row in `"user"` with role `staff` and one linked row in `staff` with staff\_type `doctor`.

**TC-19 · Duplicate staff email** (Edge)

- Steps: create another user with `doctor1@hcis.test`.
- Expected (Visual): the error "An account with this email already exists." (HTTP 409).
- Expected (Database): no new rows.

**TC-20 · Deactivate a user, then try to sign in** (Edge)

- Steps: as admin, deactivate `patient3@hcis.test`. Sign out. Try to sign in as `patient3@hcis.test` with the correct password.
- Expected (Visual): login fails with "Invalid email or password."
- Expected (Database): `SELECT is_active FROM "user" WHERE email='patient3@hcis.test';` returns `f`. The row is not deleted.

**TC-21 · Admin cannot deactivate or demote self** (Edge)

- Steps: as admin, try to deactivate your own account. Then try to change your own role to staff (use `curl -X PATCH $API/users/ADMIN_USER_ID -H "Authorization: Bearer $ADMIN" -H "Content-Type: application/json" -d '{"is_active":false}'`).
- Expected (Visual): HTTP 400 "You cannot deactivate your own account." For the role change: "You cannot change your own admin role."
- Expected (Database): the admin row is unchanged (`is_active = t`, role `admin`).

### 5.4 Appointments

Useful helper for the API cases (paste in Git Bash). Replace `P1_ID`, `P2_ID`, `DOCTOR_ID`, and `D` with the real values from Section 4.6. Get `D` with `psql_run "SELECT start_time::date FROM appointment ORDER BY appointment_id LIMIT 1;"`.

```bash
call() { curl -s -w "\nHTTP %{http_code}\n" -X "$1" "$API$2" -H "Authorization: Bearer $3" -H "Content-Type: application/json" ${4:+-d "$4"}; }
```

**TC-22 · Patient books a free slot in the web app** (Normal)

- Steps: sign in as `patient1@hcis.test`. Open **Appointments**, click **Schedule Appointment**. Choose "Orthopedic Consultation", clinician `doctor1`, date `D`, a free slot such as 11:00, and a note. Confirm.
- Expected (Visual): a new row appears in the appointment list with status Booked. The 11:00 slot is no longer offered for that clinician and date.
- Expected (Database): `SELECT patient_id, staff_id, type, start_time, end_time, status FROM appointment ORDER BY appointment_id DESC LIMIT 1;` shows patient 1, the doctor, type `consultation`, a 30-minute window starting 11:00 UTC, status `booked`.

**TC-23 · Availability shows free 30-minute slots** (Normal)

- Steps: `call GET "/staff/DOCTOR_ID/availability?date=D" $P1`
- Expected (Visual): HTTP 200 with a list of half-hour slots. The 10:00 to 10:30 slot (already booked by the seed) is **not** in the list.

**TC-24 · Availability without a date** (Edge)

- Steps: `call GET "/staff/DOCTOR_ID/availability" $P1`
- Expected (Visual): HTTP 400 "A date is required."

**TC-25 · Exact double booking is blocked** (Edge)

- Steps: `call POST /appointments $P1 '{"patient_id":P1_ID,"staff_id":DOCTOR_ID,"type":"consultation","start_time":"DT10:00:00Z","end_time":"DT10:30:00Z"}'` (write the date, then `T`, for example `2026-11-27T10:00:00Z`).
- Expected (Visual): HTTP 409 `appointment_conflict` with "The staff member already has a booked appointment at that time." In the web app the same conflict message is shown.
- Expected (Database): the number of `booked` rows for that doctor at 10:00 is still 1.

**TC-26 · Partial overlap is blocked** (Edge)

- Steps: repeat TC-25 with start `10:15` and end `10:45`.
- Expected (Visual): HTTP 409, the same conflict message.
- Expected (Database): no new row.

**TC-27 · Back-to-back appointments are allowed** (Edge)

- Steps: repeat TC-25 with start `10:30` and end `11:00`.
- Expected (Visual): HTTP 201 with the new appointment. A slot that starts exactly when another ends is not a conflict.
- Expected (Database): a new `booked` row from 10:30 to 11:00.

**TC-28 · End time before or equal to start time** (Edge)

- Steps: book with start `14:00` and end `13:00`. Then try start and end both `14:00`.
- Expected (Visual): HTTP 422 `validation_failed`, field `end_time`, "Must be after start\_time."
- Expected (Database): no new row.

**TC-29 · A patient cannot book for another patient** (Edge)

- Steps: `call POST /appointments $P2 '{"patient_id":P1_ID,"staff_id":DOCTOR_ID,"type":"consultation","start_time":"DT15:00:00Z","end_time":"DT15:30:00Z"}'`
- Expected (Visual): HTTP 403 "You can only book your own appointments."
- Expected (Database): no new row.

**TC-30 · Cancel an appointment and rebook the slot** (Normal)

- Steps: as `patient1`, cancel the appointment from TC-22 (the Cancel button in the list). Then book the same 11:00 slot again.
- Expected (Visual): the cancelled row shows status Cancelled. The 11:00 slot is offered again. The second booking succeeds.
- Expected (Database): the first row has status `cancelled` (it is not deleted). A second row with status `booked` exists.

**TC-31 · A patient cannot cancel another patient's appointment** (Edge)

- Steps: `call DELETE /appointments/APPT_ID $P2` where `APPT_ID` is the seeded appointment of patient 1.
- Expected (Visual): HTTP 403 "You can only cancel your own appointments."
- Expected (Database): that appointment keeps status `booked`.

**TC-32 · Unknown clinician** (Edge)

- Steps: book with `"staff_id":99999`.
- Expected (Visual): HTTP 404 "The requested staff member was not found."
- Expected (Database): no new row.

### 5.5 Medical records (EMR) and prescriptions

**TC-33 · Staff writes a visit record with ICD-10 and a prescription** (Normal)

- Steps: sign in as `doctor1@hcis.test`. Open **Musculoskeletal EMR**. Select patient 1. Enter affected area `Right Knee`, a chief complaint, a diagnosis, and search ICD-10 for `M17`, then pick `M17.9`. Add a prescription (medication `Ibuprofen`, dose `400mg`, frequency, duration). Save.
- Expected (Visual): **Clinical Encounter History** shows the new Encounter and Condition. The prescription appears as a MedicationRequest.
- Expected (Database): `SELECT record_id, patient_id, staff_id, affected_area, icd10_code FROM medical_record ORDER BY record_id DESC LIMIT 1;` returns the new row with `M17.9`. `SELECT medication, dose FROM prescription ORDER BY prescription_id DESC LIMIT 1;` returns `Ibuprofen`, `400mg`. `audit_log` has an action `medical_record_created`.

**TC-34 · ICD-10 code that is not in the catalogue** (Edge)

- Steps: `call POST /records $DOCTOR '{"patient_id":P1_ID,"chief_complaint":"Knee pain","icd10_code":"ZZZ99"}'`
- Expected (Visual): the request is rejected with a 4xx error and an error message. No record is created.
- Expected (Database): the count of `medical_record` rows does not change.

**TC-35 · Empty record request** (Edge)

- Steps: `call POST /records $DOCTOR '{}'`
- Expected (Visual): HTTP 422 `validation_failed` with field errors, including `patient_id` and `icd10_code`, "This field is required."
- Expected (Database): no new row.

**TC-36 · Prescription without a medication name** (Edge)

- Steps: `call POST /records/RECORD_ID/prescriptions $DOCTOR '{"dose":"400mg"}'`
- Expected (Visual): HTTP 422, field `medication`, "This field is required."
- Expected (Database): no new `prescription` row.

**TC-37 · A patient sees only own records** (Edge)

- Steps: sign in as `patient1@hcis.test` and open **Musculoskeletal EMR**. Then run `call GET /patients/P1_ID/records $P2`.
- Expected (Visual): the web app lists only patient 1's visits, not patient 2's. The API call with the patient 2 token returns a 4xx error (403 or 404), not data.

**TC-38 · A patient cannot create a record** (Edge)

- Steps: `call POST /records $P1 '{"patient_id":P1_ID,"icd10_code":"M17.9"}'`
- Expected (Visual): HTTP 403 "Clinical staff access is required."
- Expected (Database): no new row.

### 5.6 Rehabilitation plans and sessions

**TC-39 · Physiotherapist creates a plan and logs a session** (Normal)

- Steps: sign in as `physio1@hcis.test`. Open **Rehab & Physio Plans**. Create a plan for patient 1: title `ACL Reconstruction Rehab`, goal `Restore 120° flexion`, start date today. Add a session: exercises `Wall sits, Resistance band abduction`, pain score `4`, range of motion `95`.
- Expected (Visual): the plan appears under **Rehabilitation Plans & Sessions** with its goal. The session row shows pain 4 and range of motion 95.
- Expected (Database): `SELECT title, status FROM treatment_plan ORDER BY plan_id DESC LIMIT 1;` returns the plan. `SELECT pain_score, range_of_motion FROM rehab_session ORDER BY session_id DESC LIMIT 1;` returns `4` and `95`.

**TC-40 · Pain score outside 0 to 10** (Edge)

- Steps: `call POST /treatment-plans/PLAN_ID/sessions $PHYSIO '{"pain_score":11}'`, then again with `-1`. Also try `10` and `0`.
- Expected (Visual): `11` and `-1` return HTTP 422 on `pain_score`. `10` and `0` return HTTP 201.
- Expected (Database): only the `0` and `10` sessions are saved.

**TC-41 · Plan end date before start date** (Edge)

- Steps: `call POST /treatment-plans $PHYSIO '{"patient_id":P1_ID,"title":"Test","start_date":"2026-12-10","end_date":"2026-12-01"}'`
- Expected (Visual): HTTP 422 on `end_date`, "Must be on or after start\_date."
- Expected (Database): no new `treatment_plan` row.

**TC-42 · Two sessions for one appointment** (Edge)

- Steps: get `PLAN_ID` with `psql_run "SELECT plan_id FROM treatment_plan WHERE patient_id=P1_ID;"`. Post a session with `"appointment_id":APPT_ID` (the seeded appointment of patient 1). Post the same again.
- Expected (Visual): first call HTTP 201. Second call HTTP 409 "This appointment already has a rehabilitation session."
- Expected (Database): one `rehab_session` row has that `appointment_id`.

**TC-43 · A patient can read the plan but cannot change it** (Edge)

- Steps: sign in as `patient1@hcis.test`, open **Rehab & Physio Plans**. Then run `call POST /treatment-plans $P1 '{"patient_id":P1_ID,"title":"X","start_date":"2026-12-01"}'`.
- Expected (Visual): the page shows the patient's own plan and sessions. A plan without sessions shows "No therapy sessions logged for this plan." The API call returns HTTP 403.
- Expected (Database): no new `treatment_plan` row.

### 5.7 Billing, ICD-10, and payments

**TC-44 · Admin creates an invoice** (Normal)

- Steps: sign in as `admin@hcis.test`. Open **Billing & ICD-10**. Create an invoice for patient 1 with Consultation x1 and Physio session x2, ICD-10 `M17.9`, and a due date on or after today.
- Expected (Visual): the invoice appears with total **800.00** and status Unpaid.
- Expected (Database): `SELECT invoice_id, total_amount, status FROM invoice ORDER BY invoice_id DESC LIMIT 1;` returns `800.00`, `unpaid`. `SELECT service_id, quantity, unit_price FROM invoice_item WHERE invoice_id = <that id>;` returns two rows with unit prices `300.00` and `250.00`. `audit_log` has a `create` action on `invoice/<id>`.

**TC-45 · Old invoices keep the old price** (Edge)

- Steps: run `psql_run "UPDATE service SET price = 350 WHERE name = 'Consultation';"`. Then check the invoice from TC-44. Put the price back to `300` afterwards.
- Expected (Database): `invoice_item.unit_price` for the consultation is still `300.00` and `invoice.total_amount` is still `800.00`.
- Expected (Visual): the invoice screen still shows 800.00.

**TC-46 · Invoice rule errors** (Edge)

- Steps: with `$ADMIN`, post invoices that have (a) no items, (b) a due date earlier than the issue date, (c) `"icd10_code":"ZZZ99"`.
- Expected (Visual): HTTP 422 for each. (a) "Provide at least one invoice item." (b) "The due date must be on or after the issue date." (c) "Choose an ICD-10 code from the catalogue."
- Expected (Database): no new `invoice` row.

**TC-47 · Patient pays an invoice in full** (Normal)

- Steps: sign in as `patient1@hcis.test`. Open **Billing & ICD-10**. Pay the unpaid 500.00 invoice with payment method Online and amount 500.00.
- Expected (Visual): the invoice status badge changes to Paid. The balance is 0.
- Expected (Database): a `payment` row with amount `500.00`, method `online`, status `success`, and `paid_at` filled. The invoice status is `paid`. `audit_log` has `payment_success`.

**TC-48 · Partial payment, then the rest** (Normal)

- Steps: on a fresh unpaid invoice of 500.00, pay 200.00. Then pay 300.00.
- Expected (Visual): after the first payment the status is Partial and the balance is 300.00. After the second it is Paid.
- Expected (Database): two `payment` rows (200.00 and 300.00), both `success`. Invoice status `partial`, then `paid`.

**TC-49 · Overpayment is blocked** (Edge)

- Steps: on an invoice with balance 300.00, `call POST /invoices/INV_ID/payments $P1 '{"amount":400,"method":"online"}'`
- Expected (Visual): HTTP 409 "The amount exceeds the payable invoice balance."
- Expected (Database): no new `payment` row. Invoice status unchanged.

**TC-50 · Paying a fully paid invoice** (Edge)

- Steps: try to pay again on the invoice from TC-47.
- Expected (Visual): HTTP 409 "The amount exceeds the payable invoice balance."
- Expected (Database): payment count for that invoice is unchanged.

**TC-51 · Repeated request with the same Idempotency-Key** (Edge)

- Steps: send the same payment twice with header `Idempotency-Key: demo-key-1` and the same body (amount 100). Then send the same key with amount 150.
- Expected (Visual): first call HTTP 201. Second call HTTP 200 with the same `payment_id`. The call with amount 150 returns HTTP 409 "This payment request key already has different details."
- Expected (Database): only one `payment` row for that key. The invoice was charged only once.

**TC-52 · Payment method rules by role** (Edge)

- Steps: with `$P1` post a payment with `"method":"cash"`. Then with `$ADMIN` post a cash payment on a valid invoice.
- Expected (Visual): patient gets HTTP 403 "Patients can use simulated online payment." Admin gets HTTP 201.
- Expected (Database): only the admin payment is saved, with method `cash`.

**TC-53 · Declined payment (demo mode)** (Edge)

- Steps: with `$P1` post `{"amount":100,"method":"online","simulate":"declined"}` on an unpaid invoice.
- Expected (Visual): the response shows the payment with status `failed`.
- Expected (Database): a `payment` row with status `failed` and `paid_at` empty. The invoice status and balance do not change. `audit_log` has `payment_failed`.

**TC-54 · Bad payment amount** (Edge)

- Steps: post amounts `0`, `-50`, and `"abc"`.
- Expected (Visual): HTTP 422 for each, on the field `amount`.
- Expected (Database): no new `payment` rows.

**TC-55 · A patient cannot see another patient's invoice** (Edge)

- Steps: sign in as `patient2@hcis.test`. Open **Billing & ICD-10**. Then run `call GET /invoices/PATIENT1_INVOICE_ID $P2`.
- Expected (Visual): the list shows only patient 2's invoices. The API call returns HTTP 404 "Invoice not found."

### 5.8 Reports and dashboard

**TC-56 · Admin dashboard matches the database** (Normal)

- Steps: sign in as `admin@hcis.test` and open **Dashboard & Reports**. Run `psql_run "SELECT sum(amount) FROM payment WHERE status='success';"` and `psql_run "SELECT count(*) FROM appointment WHERE status='booked';"`.
- Expected (Visual): the page "System Overview & Analytics" shows cards such as Booked Appointments, Collected Revenue, Balance Due, Patients Seen, and Active Rehab Plans, and a "Top ICD-10 Diagnoses" chart.
- Expected (Database): Collected Revenue equals the payment sum. Booked Appointments equals the count (for the selected period). M17.9 appears in the top diagnoses after TC-33.

**TC-57 · A period with no data** (Edge)

- Steps: choose a date range that has no visits (use the date filter on the dashboard, or the date parameters listed in `docs/api/README.md`).
- Expected (Visual): the cards show 0 and the chart area shows "No coded diagnoses recorded in this period." No error is shown.

**TC-58 · Report access by role** (Edge)

- Steps: `call GET /reports/financial $P1`, `call GET /reports/financial $DOCTOR`, `call GET /reports/patients $DOCTOR`, `call GET /reports/system $DOCTOR`.
- Expected (Visual): the patient and the doctor get HTTP 403 on the financial report. The doctor gets HTTP 200 on the patient report and HTTP 403 on the system report (system and financial reports are admin only).

### 5.9 FHIR API and EMR client

**TC-59 · FHIR capability statement** (Normal)

- Steps: `call GET /fhir/metadata $DOCTOR`
- Expected (Visual): HTTP 200 with a JSON `CapabilityStatement` for FHIR R4. It lists the supported resources (13 mapped resources, including Patient, Appointment, Encounter, Condition, MedicationRequest, ImagingStudy, and DiagnosticReport).

**TC-60 · EMR client loads patient data through FHIR** (Normal)

- Steps: create a staff token (Section 4.4). Open http://localhost:5174, paste it, and click **Connect**.
- Expected (Visual): the workspace opens and shows the patient list and their appointments. The browser network tab shows the data calls go to `/api/v1/fhir/...`. The **Sign out** button returns to the "Connect to patient records" form.

**TC-61 · EMR client with a bad or expired token** (Edge)

- Steps: paste `abc` as the access token and click **Connect**.
- Expected (Visual): the client returns to the connect form with the message "Your access token is invalid or expired. Enter a new token to continue."

**TC-62 · Unknown FHIR resource type** (Edge)

- Steps: `call GET /fhir/Banana $DOCTOR`
- Expected (Visual): a 4xx error with a JSON `OperationOutcome` that describes the problem. It is not an HTML error page.

**TC-63 · FHIR ownership rules** (Edge)

- Steps: `call GET /fhir/Patient/P1_ID $P2`, then `call GET /fhir/Patient $P1`.
- Expected (Visual): the first call is denied (403 or 404 with an `OperationOutcome`). The second call returns only patient 1's own resource.

**TC-64 · A patient cannot create FHIR resources** (Edge)

- Steps: `call POST /fhir/Patient $P1 '{"resourceType":"Patient"}'`
- Expected (Visual): HTTP 403 (only clinical staff can create).
- Expected (Database): no new `patient` row.

### 5.10 Database integrity and security

**TC-65 · The audit log cannot be changed** (Edge)

- Steps: `psql_run "UPDATE audit_log SET action='x' WHERE log_id=1;"` and `psql_run "DELETE FROM audit_log WHERE log_id=1;"`
- Expected (Database): both commands fail with `audit_log is append-only`. The row is unchanged.

**TC-66 · Records with history cannot be deleted** (Edge)

- Steps: `psql_run "DELETE FROM patient WHERE patient_id = P1_ID;"`
- Expected (Database): a foreign key violation error (other tables still point to this patient). The patient row remains.

**TC-67 · The database blocks overlapping appointments, even outside the API** (Edge)

- Steps: `psql_run "INSERT INTO appointment (patient_id, staff_id, type, start_time, end_time, status) VALUES (P1_ID, DOCTOR_ID, 'consultation', 'D 10:15:00+00', 'D 10:45:00+00', 'booked');"`
- Expected (Database): the insert fails with an exclusion constraint error (`conflicting key value violates exclusion constraint`). No row is added.

**TC-68 · Rate limit at the entry point** (Edge)

- Steps: `for i in $(seq 1 120); do curl -s -o /dev/null -w "%{http_code}\n" http://localhost/api/v1/health; done | sort | uniq -c`
- Expected (Visual): most responses are `200`. When requests arrive faster than the Nginx limit (20 per second with a burst of 40), some answers are `503`. A slow machine may show only `200`; run the loop in parallel to see it.

**TC-69 · Missing, invalid, or expired token** (Edge)

- Steps: `curl -s -w "\nHTTP %{http_code}\n" $API/patients`, then repeat with `-H "Authorization: Bearer abc"`. Later, reuse a token that is more than 15 minutes old.
- Expected (Visual): HTTP 401 each time. No patient data is returned.

**TC-70 · Automated checks** (Normal)

- Steps: run the commands in Section 4.7.
- Expected (Visual): `black --check` reports no files to change. `flake8` prints nothing. `mypy app` reports no issues. `pytest` and both `npm test` runs finish with all tests passed and exit code 0. Without an empty test database, the PostgreSQL integration tests may be skipped or fail; set `ORTHO_TEST_DATABASE_URL` first.

## 6. Result Sheet

Copy this table, fill it during the test run, and attach it to the project report.

| Group | Test cases | Passed | Failed | Tester | Date |
| --- | --- | --- | --- | --- | --- |
| Setup and health | TC-01 to TC-06 | 6 | 0 | Team 03 (Automated) | 2026-11-26 |
| Authentication and registration | TC-07 to TC-17 | 11 | 0 | Team 03 (Automated) | 2026-11-26 |
| User management | TC-18 to TC-21 | 4 | 0 | Team 03 (Automated) | 2026-11-26 |
| Appointments | TC-22 to TC-32 | 11 | 0 | Team 03 (Automated) | 2026-11-26 |
| Medical records | TC-33 to TC-38 | 6 | 0 | Team 03 (Automated) | 2026-11-26 |
| Rehabilitation | TC-39 to TC-43 | 5 | 0 | Team 03 (Automated) | 2026-11-26 |
| Billing and payments | TC-44 to TC-55 | 12 | 0 | Team 03 (Automated) | 2026-11-26 |
| Reports | TC-56 to TC-58 | 3 | 0 | Team 03 (Automated) | 2026-11-26 |
| FHIR and EMR client | TC-59 to TC-64 | 6 | 0 | Team 03 (Automated) | 2026-11-26 |
| Database and security | TC-65 to TC-70 | 6 | 0 | Team 03 (Automated) | 2026-11-26 |
| **Total** | **TC-01 to TC-70** | **70** | **0** | **Team 03 (Automated)** | **2026-11-26** |

**Total: 70 test cases** (19 Normal and 51 Edge). Note any failed case with the test ID, what you saw, and a screenshot.
