"""Durable local OCR jobs with fenced leases."""

import sqlalchemy as sa
from alembic import op

revision = "0007_ocr"
down_revision = "0006_files"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ocr_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("file_id", sa.String(), sa.ForeignKey("evidence_files.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("retry_of_id", sa.String(), sa.ForeignKey("ocr_jobs.id")),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.String()),
        sa.Column("lease_expires_at", sa.String()),
        sa.Column("error_code", sa.String()),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String()),
    )


def downgrade():
    op.drop_table("ocr_jobs")
