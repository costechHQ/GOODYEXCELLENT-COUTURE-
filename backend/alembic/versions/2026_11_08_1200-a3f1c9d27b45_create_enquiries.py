"""create enquiries

Revision ID: a3f1c9d27b45
Revises: ecf95f018c21
Create Date: 2026-11-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f1c9d27b45"
down_revision: str | Sequence[str] | None = "ecf95f018c21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "enquiries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.Enum("consultation", "order", "laundry", "general", name="enquirytype"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("preferred_contact", sa.Enum("whatsapp", "call", "email", name="contactmethod"), nullable=True),
        sa.Column("service", sa.String(length=120), nullable=True),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("preferred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("garment_type", sa.String(length=200), nullable=True),
        sa.Column("occasion", sa.String(length=200), nullable=True),
        sa.Column("needed_by", sa.Date(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("fabric_preference", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.Enum("new", "contacted", "in_progress", "completed", "closed", name="enquirystatus"),
            server_default="new",
            nullable=False,
        ),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_enquiries_type"), "enquiries", ["type"], unique=False)
    op.create_index(op.f("ix_enquiries_status"), "enquiries", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_enquiries_status"), table_name="enquiries")
    op.drop_index(op.f("ix_enquiries_type"), table_name="enquiries")
    op.drop_table("enquiries")
    # Alembic does not drop PostgreSQL enum types itself; without this, a later upgrade fails.
    op.execute("DROP TYPE enquirystatus")
    op.execute("DROP TYPE contactmethod")
    op.execute("DROP TYPE enquirytype")
