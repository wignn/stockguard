"""Physical count sessions and unresolved discrepancy cases."""

import sqlalchemy as sa
from alembic import op

revision = "0004_counts_cases"
down_revision = "0003_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stocktakes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("location_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("baseline_milli", sa.Integer(), nullable=False),
        sa.Column("baseline_version", sa.Integer(), nullable=False),
        sa.Column("cost_rupiah", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=False),
        sa.Column("finalized_at", sa.String()),
        sa.Column("counted_milli", sa.Integer()),
        sa.Column("difference_milli", sa.Integer()),
        sa.Column("recounted", sa.Boolean(), nullable=False),
        sa.Column("rack_checked", sa.Boolean(), nullable=False),
        sa.Column("storage_checked", sa.Boolean(), nullable=False),
        sa.Column("no_physical_movement", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        sa.ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
        sa.CheckConstraint(
            "baseline_milli >= 0 AND baseline_version >= 0", name="baseline_nonnegative"
        ),
        sa.CheckConstraint(
            "counted_milli IS NULL OR (typeof(counted_milli) = 'integer' AND counted_milli >= 0)",
            name="count_nonnegative",
        ),
    )
    op.create_index(
        "uq_active_stocktake",
        "stocktakes",
        ["business_id", "product_id", "location_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "investigation_cases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("location_id", sa.String(), nullable=False),
        sa.Column(
            "initial_stocktake_id", sa.String(), sa.ForeignKey("stocktakes.id"), nullable=False
        ),
        sa.Column(
            "latest_stocktake_id", sa.String(), sa.ForeignKey("stocktakes.id"), nullable=False
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("difference_milli", sa.Integer(), nullable=False),
        sa.Column("cost_rupiah", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("findings", sa.String(), nullable=False),
        sa.Column("current_submission_id", sa.String()),
        sa.ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        sa.ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
    )
    op.create_index(
        "uq_unresolved_case",
        "investigation_cases",
        ["business_id", "product_id", "location_id"],
        unique=True,
        sqlite_where=sa.text("status != 'closed'"),
    )


def downgrade():
    op.drop_table("investigation_cases")
    op.drop_table("stocktakes")
