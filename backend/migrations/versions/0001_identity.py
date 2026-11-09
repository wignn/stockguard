"""Identity, membership, and audit records."""

from alembic import op
from sqlalchemy import JSON, Boolean, Column, ForeignKey, MetaData, String, Table, UniqueConstraint

revision = "0001_identity"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    metadata = MetaData()
    Table(
        "businesses",
        metadata,
        Column("id", String, primary_key=True),
        Column("name", String, nullable=False),
        Column("timezone", String, nullable=False),
        Column("is_demo", Boolean, nullable=False),
    )
    Table(
        "users",
        metadata,
        Column("id", String, primary_key=True),
        Column("username", String, nullable=False, unique=True),
        Column("password_hash", String, nullable=False),
        Column("active", Boolean, nullable=False),
    )
    Table(
        "locations",
        metadata,
        Column("id", String, primary_key=True),
        Column("business_id", String, ForeignKey("businesses.id"), nullable=False),
        Column("name", String, nullable=False),
        UniqueConstraint("business_id"),
        UniqueConstraint("business_id", "id"),
    )
    Table(
        "memberships",
        metadata,
        Column("id", String, primary_key=True),
        Column("user_id", String, ForeignKey("users.id"), nullable=False),
        Column("business_id", String, ForeignKey("businesses.id"), nullable=False),
        Column("role", String, nullable=False),
        UniqueConstraint("user_id", "business_id"),
    )
    Table(
        "sessions",
        metadata,
        Column("id", String, primary_key=True),
        Column("user_id", String, ForeignKey("users.id"), nullable=False),
        Column("token_hash", String, nullable=False, unique=True),
        Column("csrf_token", String, nullable=False),
        Column("issued_at", String, nullable=False),
        Column("expires_at", String, nullable=False),
        Column("revoked", Boolean, nullable=False),
    )
    Table(
        "audit_events",
        metadata,
        Column("id", String, primary_key=True),
        Column("business_id", String, ForeignKey("businesses.id"), nullable=False, index=True),
        Column("user_id", String, ForeignKey("users.id"), nullable=False),
        Column("action", String, nullable=False),
        Column("entity_type", String, nullable=False),
        Column("entity_id", String, nullable=False),
        Column("occurred_at", String, nullable=False),
        Column("changes", JSON, nullable=False),
        Column("request_id", String),
    )
    metadata.create_all(op.get_bind())


def downgrade():
    for name in ["audit_events", "sessions", "memberships", "locations", "users", "businesses"]:
        op.drop_table(name)
