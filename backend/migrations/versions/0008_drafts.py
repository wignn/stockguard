"""Human-reviewed transaction drafts and per-line confirmation."""

import sqlalchemy as sa
from alembic import op

revision = "0008_drafts"
down_revision = "0007_ocr"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "transaction_drafts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("file_id", sa.String(), sa.ForeignKey("evidence_files.id"), nullable=False),
        sa.Column("ocr_job_id", sa.String(), sa.ForeignKey("ocr_jobs.id"), unique=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("receipt_number", sa.String()),
        sa.Column("receipt_date", sa.String()),
        sa.Column("original_ocr", sa.JSON()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "draft_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("draft_id", sa.String(), sa.ForeignKey("transaction_drafts.id"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("suggestion", sa.JSON()),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id")),
        sa.Column("kind", sa.String()),
        sa.Column("quantity", sa.String()),
        sa.Column("unit_price_rupiah", sa.String()),
        sa.Column("occurred_at", sa.String()),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("movement_id", sa.String(), sa.ForeignKey("stock_movements.id"), unique=True),
        sa.UniqueConstraint("draft_id", "position"),
    )


def downgrade():
    op.drop_table("draft_lines")
    op.drop_table("transaction_drafts")
