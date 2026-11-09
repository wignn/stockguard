"""Catalog and stock ledger."""

import sqlalchemy as sa
from alembic import op

revision = "0002_catalog_ledger"
down_revision = "0001_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "products",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), sa.ForeignKey("businesses.id"), nullable=False),
        sa.Column("sku", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("unit", sa.String(), nullable=False),
        sa.Column("step_milli", sa.Integer(), nullable=False),
        sa.Column("cost_rupiah", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("business_id", "sku"),
        sa.UniqueConstraint("business_id", "id"),
        sa.CheckConstraint(
            "typeof(step_milli) = 'integer' AND step_milli > 0", name="step_positive"
        ),
        sa.CheckConstraint(
            "typeof(cost_rupiah) = 'integer' AND cost_rupiah >= 0", name="cost_nonnegative"
        ),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_table(
        "stock_balances",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("location_id", sa.String(), nullable=False),
        sa.Column("quantity_milli", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("business_id", "product_id", "location_id"),
        sa.ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        sa.ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
        sa.CheckConstraint(
            "typeof(quantity_milli) = 'integer' AND quantity_milli >= 0",
            name="quantity_nonnegative",
        ),
        sa.CheckConstraint("version >= 0", name="version_nonnegative"),
    )
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("business_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("location_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("quantity_milli", sa.Integer(), nullable=False),
        sa.Column("cost_rupiah", sa.Integer(), nullable=False),
        sa.Column("balance_after_milli", sa.Integer(), nullable=False),
        sa.Column("balance_version", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.Column("posted_at", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("source_id", sa.String()),
        sa.UniqueConstraint("business_id", "id"),
        sa.UniqueConstraint("business_id", "product_id", "location_id", "balance_version"),
        sa.ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        sa.ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
        sa.CheckConstraint(
            "typeof(quantity_milli) = 'integer' AND quantity_milli != 0", name="quantity_nonzero"
        ),
        sa.CheckConstraint(
            "typeof(cost_rupiah) = 'integer' AND cost_rupiah >= 0", name="cost_nonnegative"
        ),
        sa.CheckConstraint(
            "typeof(balance_after_milli) = 'integer' AND balance_after_milli >= 0",
            name="balance_nonnegative",
        ),
        sa.CheckConstraint("balance_version > 0", name="version_positive"),
    )


def downgrade():
    op.drop_table("stock_movements")
    op.drop_table("stock_balances")
    op.drop_table("products")
