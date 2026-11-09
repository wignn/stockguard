"""Durable request idempotency results."""

import sqlalchemy as sa
from alembic import op

revision = "0003_idempotency"
down_revision = "0002_catalog_ledger"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("request_hash", sa.String(), nullable=False),
        sa.Column("result_id", sa.String(), nullable=False),
        sa.UniqueConstraint("business_id", "user_id", "operation", "key"),
    )


def downgrade():
    op.drop_table("idempotency_records")
