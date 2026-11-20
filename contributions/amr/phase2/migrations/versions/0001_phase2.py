"""Initial Phase 1 schema for the Phase 2 healthcare prototype."""

from alembic import op

from ortho.schema_v1 import metadata

revision = "0001_phase2"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    for table in metadata.sorted_tables:
        table.create(op.get_bind())

    op.execute("""
        ALTER TABLE appointment ADD CONSTRAINT appointment_staff_no_overlap
        EXCLUDE USING gist
        (staff_id WITH =, tstzrange(start_time, end_time, '[)') WITH &&)
        WHERE (status = 'booked')
    """)
    op.execute("""
        CREATE FUNCTION reject_audit_log_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only' USING ERRCODE = '55000';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION reject_audit_log_mutation()
    """)


def downgrade():
    for table in reversed(metadata.sorted_tables):
        table.drop(op.get_bind())
    op.execute("DROP FUNCTION reject_audit_log_mutation()")
