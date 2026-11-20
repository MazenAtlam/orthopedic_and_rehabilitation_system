"""Clinical record persistence shared by the portal and FHIR."""

from flask import Blueprint, g
from sqlalchemy import select

from ortho.access import load_actor
from ortho.common import ApiError, as_date, as_int, as_text, audit, body, db, require_roles
from ortho.schema_v1 import icd10_code, medical_record, patient, staff

records = Blueprint("records", __name__, url_prefix="/api/v1")
records.before_request(load_actor)


def clinician_id(connection):
    identity = connection.scalar(select(staff.c.staff_id).where(
        staff.c.user_id == g.actor["user_id"]
    ))
    if identity is None:
        raise ApiError(403, "forbidden", "A linked practitioner profile is required.")
    return identity


def insert_visit(connection, data):
    patient_id = as_int(data.get("patient_id"), "patient_id")
    visit = as_date(data.get("visit_date"), "visit_date")
    code = as_text(data.get("icd10_code"), "icd10_code", maximum=10).upper()
    practitioner = clinician_id(connection)
    if "staff_id" in data and as_int(data["staff_id"], "staff_id") != practitioner:
        raise ApiError(403, "forbidden", "The practitioner must match the signed-in account.")

    if connection.scalar(select(patient.c.patient_id).where(patient.c.patient_id == patient_id)) is None:
        raise ApiError(404, "not-found", "Patient not found.")
    if connection.scalar(select(icd10_code.c.code).where(icd10_code.c.code == code)) is None:
        raise ApiError(422, "code-invalid", "Choose an ICD-10 code from the catalogue.")

    return connection.execute(medical_record.insert().values(
        patient_id=patient_id,
        staff_id=practitioner,
        visit_date=visit,
        icd10_code=code,
        **{
            name: as_text(data.get(name), name, maximum=limit, optional=True)
            for name, limit in (
                ("chief_complaint", 4000), ("affected_area", 100),
                ("diagnosis", 4000), ("notes", 4000),
            )
        },
    ).returning(medical_record)).mappings().one()


@records.post("/records")
@require_roles("staff")
def create_record():
    data = body()
    with db().begin() as connection:
        row = insert_visit(connection, data)
        audit(connection, "create", f"medical_record/{row['record_id']}")
    return dict(row), 201
