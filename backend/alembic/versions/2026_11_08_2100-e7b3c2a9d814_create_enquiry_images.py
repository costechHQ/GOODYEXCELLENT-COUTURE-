"""create enquiry_images

Revision ID: e7b3c2a9d814
Revises: d5a9f3b27e61
Create Date: 2026-11-08 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b3c2a9d814"
down_revision: str | Sequence[str] | None = "d5a9f3b27e61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "enquiry_images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enquiry_id", sa.Integer(), nullable=False),
        sa.Column("image_id", sa.String(length=32), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("widths", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["enquiry_id"], ["enquiries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("image_id"),
    )
    op.create_index(op.f("ix_enquiry_images_enquiry_id"), "enquiry_images", ["enquiry_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_enquiry_images_enquiry_id"), table_name="enquiry_images")
    op.drop_table("enquiry_images")
