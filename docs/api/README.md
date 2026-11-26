# Phase 2 API contract

The Flask API is mounted at `/api/v1`. Send a bearer access token for billing, reports and FHIR. For an isolated demo, run `seed-demo` and obtain a short-lived token with `demo-fhir-token --role staff`. Team sign-in, refresh and the remaining clinic routes are tracked separately. Money values in the billing and report JSON are decimal strings.

## Billing and reporting

| Method and path relative to `/api/v1` | Role and response |
| --- | --- |
| `GET /services` | Any authenticated role. Returns `items` and paging fields. Admin can request `include_inactive=true`. |
| `POST /services` | Admin. Use `name`, `price` and optional `description`, `is_active` and `service_id`. Creates with 201 or updates the supplied ID with 200. |
| `GET /icd10?q=M17` | Admin or staff. Returns a paged `items` list containing `code`, `description` and `category`. |
| `POST /invoices` | Admin or staff. Provide `patient_id`, `due_date` and `items` with `service_id` and `quantity`. Optional fields include `issue_date`, `appointment_id` and `icd10_code`. Response is invoice details with line-item snapshots. |
| `GET /invoices`, `GET /invoices/{id}` | Admin and staff can read invoices. Patient can read own invoices. The list is paged and supports `patient_id` and `status`. Hidden invoice IDs return 404. |
| `POST /invoices/{id}/payments` | Admin and owning patients. Use the `Idempotency-Key` header and a positive 2-decimal `amount`. A patient submits `method: "online"`. Card and cash return 403 for patients. The response contains `payment` and the updated `invoice`. |
| `GET /reports/system` | Admin. Returns `totals`, `daily` appointment and login counts, and `appointments_by_status`. |
| `GET /reports/patients` | Admin or staff. Returns `totals`, `daily` visits and `diagnoses` grouped by ICD-10 code. |
| `GET /reports/financial` | Admin. Returns `currency`, `totals` and `daily` revenue. Totals include `revenue`, `outstanding` and `open_invoices`. |

List responses contain `items`, `page`, `page_size` and `total`. Use `page` and `page_size` to navigate. Reports accept ISO dates `start` and `end`, use inclusive UTC dates and default to the last 30 days. A repeated payment with the same key and payload returns the original payment with 200. An overpayment or a reused key with conflicting data returns 409. These payments are simulated.

## FHIR R4

Send `Accept: application/fhir+json`. Staff and admins can read `GET /fhir/metadata` for role-specific resources and interactions. `GET /fhir/{type}` returns a search Bundle. `GET /fhir/{type}/{id}` returns a resource. Supported members are Patient, Practitioner, Appointment, Encounter, Condition, MedicationRequest, CarePlan, Procedure, Observation, ImagingStudy, DiagnosticReport, Invoice and PaymentNotice. Searches support `_id`, `_count` up to 100, `_page`, and the mapped patient or subject parameter. For writes send `Content-Type: application/fhir+json`. Staff can create Appointment, Encounter, MedicationRequest, CarePlan, Procedure and Observation. An Encounter carries the coded diagnosis that is exposed as a Condition.

Patient resources are filtered to the authenticated account's own records. Admins can access administrative resources including Patient and Appointment. Clinical resources return 403 for admins. FHIR errors use OperationOutcome. A forbidden cross-patient read may return 404 to conceal the resource ID. A conflicting appointment returns 409.

- [Flask routes](../../backend/app/api/v1)
- [FHIR resource mapping and writers](../../backend/app/fhir)
