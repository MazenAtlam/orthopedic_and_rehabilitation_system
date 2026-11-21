"""Keep imaging studies and their clinical reviews consistent."""

from alembic import op

revision = "0002_imaging_integrity"
down_revision = "0001_phase2"


def upgrade():
    op.create_unique_constraint("record_id_patient_key", "medical_record", ["record_id", "patient_id"])
    op.create_foreign_key(
        "scan_record_patient_fk", "scan", "medical_record",
        ["record_id", "patient_id"], ["record_id", "patient_id"], ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "cdss_review_has_reviewer", "cdss_result",
        "(review_status = 'pending' AND reviewed_by IS NULL) OR "
        "(review_status IN ('accepted', 'rejected') AND reviewed_by IS NOT NULL)",
    )


def downgrade():
    op.drop_constraint("cdss_review_has_reviewer", "cdss_result", type_="check")
    op.drop_constraint("scan_record_patient_fk", "scan", type_="foreignkey")
    op.drop_constraint("record_id_patient_key", "medical_record", type_="unique")
