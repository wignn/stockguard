"""Immutable submissions, decisions, and reversal requests."""

import sqlalchemy as sa
from alembic import op

revision = "0005_submissions_approvals"
down_revision = "0004_counts_cases"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE investigation_cases SET status='investigating' WHERE status='open'")
    op.execute("UPDATE investigation_cases SET status='resolved' WHERE status='closed'")
    op.drop_index("uq_unresolved_case", table_name="investigation_cases")
    op.create_index(
        "uq_unresolved_case",
        "investigation_cases",
        ["business_id", "product_id", "location_id"],
        unique=True,
        sqlite_where=sa.text("status != 'resolved'"),
    )
    op.create_table(
        "case_submissions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("case_id", sa.String(), sa.ForeignKey("investigation_cases.id"), nullable=False),
        sa.Column("stocktake_id", sa.String(), sa.ForeignKey("stocktakes.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("cause", sa.String(), nullable=False),
        sa.Column("resolution_kind", sa.String(), nullable=False),
        sa.Column("quantity_milli", sa.Integer(), nullable=False),
        sa.Column("movement_kind", sa.String()),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column("missing_evidence_reason", sa.String(), nullable=False),
        sa.Column("submitted_at", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
    )
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("submission_id", sa.String()),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column("movement_id", sa.String(), sa.ForeignKey("stock_movements.id")),
        sa.Column("case_status", sa.String(), nullable=False),
        sa.Column("decided_at", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
    )
    op.create_table(
        "reversal_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column(
            "original_movement_id", sa.String(), sa.ForeignKey("stock_movements.id"), nullable=False
        ),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("business_id", "original_movement_id"),
    )
    op.create_index(
        "uq_movement_source",
        "stock_movements",
        ["business_id", "source_type", "source_id"],
        unique=True,
        sqlite_where=sa.text("source_id IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_movement_source", table_name="stock_movements")
    op.drop_table("reversal_requests")
    op.drop_table("approval_decisions")
    op.drop_table("case_submissions")
    op.drop_index("uq_unresolved_case", table_name="investigation_cases")
    op.execute("UPDATE investigation_cases SET status='open' WHERE status='investigating'")
    op.execute("UPDATE investigation_cases SET status='closed' WHERE status='resolved'")
    op.create_index(
        "uq_unresolved_case",
        "investigation_cases",
        ["business_id", "product_id", "location_id"],
        unique=True,
        sqlite_where=sa.text("status != 'closed'"),
    )
