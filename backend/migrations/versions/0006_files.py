"""Private image evidence and explicit associations."""

import sqlalchemy as sa
from alembic import op

revision = "0006_files"
down_revision = "0005_submissions_approvals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "evidence_files",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False, unique=True),
        sa.Column("original_name", sa.String(), nullable=False),
        sa.Column("mime_type", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("business_id", "id"),
    )
    op.create_table(
        "evidence_links",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("file_id", sa.String(), sa.ForeignKey("evidence_files.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("movement_id", sa.String(), sa.ForeignKey("stock_movements.id")),
        sa.Column("case_id", sa.String(), sa.ForeignKey("investigation_cases.id")),
        sa.Column("submission_id", sa.String(), sa.ForeignKey("case_submissions.id")),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("file_id", "target_type", "target_id"),
        sa.CheckConstraint(
            "(movement_id IS NOT NULL) + (case_id IS NOT NULL) + (submission_id IS NOT NULL) = 1",
            name="one_evidence_target",
        ),
    )


def downgrade():
    op.drop_table("evidence_links")
    op.drop_table("evidence_files")
