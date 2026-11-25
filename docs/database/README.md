# PostgreSQL schema and demo data

Use Alembic from `backend/` with a `DATABASE_URL` pointing to PostgreSQL. `python -m alembic upgrade head` applies both tracked revisions. The application schema has 17 tables plus Alembic's revision table.

| Area | Tables and constraints |
| --- | --- |
| Accounts and clinics | `user`, `patient`, `staff`, `appointment`. User email is unique. Patient and staff profiles reference users. Appointment start must precede end. PostgreSQL excludes overlapping booked slots for the same member of staff with `btree_gist` and a half-open time range. |
| Clinical and rehabilitation | `medical_record`, `prescription`, `treatment_plan`, `rehab_session`, `icd10_code`. Records and plans point to their patient and clinician. The coded diagnosis references the catalogue. |
| Finance | `service`, `invoice`, `invoice_item`, `payment`. The invoice captures prices on the line items. Payments lock the invoice during balance updates. The payment key is unique per invoice. |
| Imaging | `scan`, `cdss_result`, `annotation`. A scan has a unique DICOM Study UID. Revision 0002 enforces that a linked visit belongs to the same patient and that completed reviews have a reviewer. |
| Audit | `audit_log`. The database rejects update, delete and truncate operations. `user_id` references a known account. The login owner still needs to decide how to record attempts whose email has no matching account. |

## Local demo

Set `DEMO_MODE=1` and use a non-production application. On a fresh demo database, run `python -m flask --app wsgi seed-demo`. The migration and seed paths are safe to rerun. Six fictional accounts share the documented demo password. Each stored password is independently hashed with bcrypt. Existing records and their invoice prices are preserved when creating this new fixture set in an older demo database. Use a fresh demo database to reproduce the documented row counts. If only some of the reserved demo accounts already exist, the seed aborts without modifying them.

Patient 1 has an unpaid `500.00` invoice made of two `250.00` Physio sessions and a doctor appointment the day after seeding, 10:00–10:30 UTC. The other prices are `300.00` for Consultation and `400.00` for X-ray imaging. Four sample ICD-10 codes support the default suite. Download the official WHO archive separately to import the full local orthopedic catalogue.

- [Schema](../../backend/app/models/schema_v1.py)
- [Migrations](../../backend/migrations/versions)
- [Demo accounts and prices](../../README.md#demo-accounts)
- [Official catalogue import](../../database/seed/README.md)
