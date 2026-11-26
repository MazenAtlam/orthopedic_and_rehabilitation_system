# Phase 2 architecture

| Component | Current responsibility |
| --- | --- |
| `frontend/` | Anas's React and TypeScript clinic screens. The frontend uses mock login and local fixtures in the feature pages. Axios adapters describe the proposed clinic API calls. The application integration is scheduled after this review. |
| `backend/` | Flask validates bearer tokens and resolves roles and ownership from PostgreSQL. Billing, reporting and FHIR are registered. Team auth and the remaining clinic routes have their own owners. |
| `emr-client/` | A separate React client for F15. Uses the FHIR API through the Vite proxy. Stores the access token in memory and enforces visibility via backend responses. |
| PostgreSQL | Stores and enforces clinical, appointment and financial relationships. Alembic owns revisions. Billing and audit writes use database transactions. |
| Nginx and Compose | Compose starts the services. Nginx exposes the clinic UI and API for local development. The separate EMR serves on port 5174 and proxies its own API calls. |

## Data paths to verify during integration

The clinic UI's billing requests must use service IDs and quantities. Invoices keep a snapshot of the unit prices and show the balance after successful simulated payments. The financial report groups successful payments on their posting dates. The system report groups appointments on their start dates. The patient report groups coded visits by visit date and diagnosis. Anas's chart components need to use these fields and the date range the user selected.

The independent EMR requests Patient and the associated FHIR resources using the patient search parameters defined by each resource type. Flask applies the role and ownership before serializing the response. FHIR maps stored study and review data to ImagingStudy and DiagnosticReport. Access to PACS and live inference belongs to the team imaging integration.

- [API contract](../api/README.md)
- [Database and demo seed](../database/README.md)
