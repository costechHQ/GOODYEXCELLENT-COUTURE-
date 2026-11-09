"""add admin lockout columns

Revision ID: c4d8e1f95a27
Revises: b7e2d4a81c36
Create Date: 2026-11-08 17:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d8e1f95a27'
down_revision: str | Sequence[str] | None = 'b7e2d4a81c36'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('admin_users', sa.Column('failed_login_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.add_column('admin_users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('admin_users', 'locked_until')
    op.drop_column('admin_users', 'failed_login_attempts')
