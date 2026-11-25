# Phase 2 progress report

Team 03 · Orthopedic and Rehabilitation System · Amr Fekry · 25 November 2026

## Feature status

| Feature | Phase 2 status | Evidence |
| --- | --- | --- |
| F09 Service catalogue and invoicing | Backend verified | Consultation 300.00 EGP, Physio session 250.00 EGP and X-ray imaging 400.00 EGP. The default patient has an unpaid 500.00 EGP invoice. The Decimal unit tests and PostgreSQL tests cover invoice totals and price snapshots. |
| F10 Simulated payments | Backend verified | The owning patient can pay online. Cash and card return HTTP 403 for patients. The API verifies partial and full settlement, ownership, idempotency and simultaneous balance updates. |
| F11 Reporting and analytics | Report API verified. Clinic charts pending | The three report endpoints return dated aggregates and enforce their role permissions. Anas's analytics screen currently displays hardcoded metrics and a sample visits chart. |
| F13 PostgreSQL, migrations, demo and audit | Verified for the isolated backend | Two Alembic revisions, 17 application tables, six demo accounts and an idempotent seed. Tested the password hashes and confirmed the seed is disabled outside development demo mode. |
| F14 FHIR R4 | Backend verified | Capability statement, resources, owned-patient scope and coded writes. The appointment slot unit checks cover overlapping and touching ranges. PostgreSQL integration checks verify actual conflict rejection. |
| F15 Independent FHIR EMR | Standalone verified | Chromium verified the role-specific EMR views and confirmed that data requests used only FHIR through the Vite proxy. The clinic frontend login remains a separate integration dependency. |
| B1 ICD-10 | Backend verified | Use `q=M17` with the four fixtures. The local WHO import added 679 codes when tested. Coded encounters, billing and report aggregation are covered. |

## Problems and decisions

- The previous demo used four accounts and different service prices. The new fixture matches the documented six-account contract. The known password is enabled only for the fictional seed. Real web sign-in still needs Hussein's authentication routes.
- The workbook uses the simulated online payment method for patients, explicit idempotency keys and the default catalogue search term. Its recorded results describe isolated tests. The integrated dashboard and end-to-end clinic cases depend on the team connection.
- The audit log currently requires a known user ID. Hussein owns the design decision for unknown-email login attempts.
- Mazen removed the Conventional Commits check in commit `e2bc573` during the CI work in PR #5. The commit records the removal without a reason. The following fix in `7a628f4` removed the reference to the deleted job. The team should decide whether to restore that rule.
- Anas removed the tracked Vite cache in `76b5a03`. The ignore rule prevents the cache from being committed again.

## Frontend review and next work

Anas's React frontend builds and passes TypeScript and ESLint. It has mock sign-in, route guards and screens for analytics, user management, appointments, clinical records, rehabilitation and billing. The user management, clinical, rehabilitation and appointment screens currently operate on local state or fixtures. The patient landing route uses the general analytics screen, so the patient-specific F12 dashboard still needs to show appointments, records, rehabilitation and invoices.

- **Anas** should build the F11 chart views for appointment load, diagnoses and revenue from the three documented report payloads. Add date filters and loading, empty and error states. The billing screens need catalogue-based prices, service IDs and quantities, and a patient online payment flow. Align paged `items` responses, decimal amounts, role permissions, and payment idempotency. Add frontend workflow tests and review the patient dashboard.
- **Amr** should help verify billing, reports and ICD-10 against the clinic UI during the integration pass, then record the integrated acceptance tests. The database, billing, reporting and independent EMR can already be tested separately with demo tokens.
- **Hussein and the team** should finish the login, registration, refresh and role-specific clinic endpoints, decide how to audit unknown users, and run the signed-in patient and rehabilitation journeys. The Phase 2 review did not connect the clinic frontend to the backend.

## Pull requests and test evidence

49 backend tests passed, including nine unit cases. The six EMR Jest tests and the independent EMR and clinic frontend builds passed.

- [Amr's merged backend and independent EMR](https://github.com/MazenAtlam/orthopedic_and_rehabilitation_system/pull/6)
- [Anas's merged clinic frontend](https://github.com/MazenAtlam/orthopedic_and_rehabilitation_system/pull/11)
- [Team CI changes](https://github.com/MazenAtlam/orthopedic_and_rehabilitation_system/pull/5)
- [Phase 2 review changes](https://github.com/MazenAtlam/orthopedic_and_rehabilitation_system/compare/develop...codex/amr-phase2-demo-contract)
- [Executed test cases](../../testing/test-cases.xlsx)
- [API contract](../../api/README.md)
