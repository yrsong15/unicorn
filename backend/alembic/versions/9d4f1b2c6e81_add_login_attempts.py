"""add login_attempts

Failed logins per client IP, used to throttle password guessing.

Revision ID: 9d4f1b2c6e81
Revises: 5e2a9c7d1f30
Create Date: 2026-11-11 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = '9d4f1b2c6e81'
down_revision: Union[str, Sequence[str], None] = '5e2a9c7d1f30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'login_attempts',
        sa.Column('ip', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column('failures', sa.Integer(), nullable=False),
        sa.Column('first_failure_at', sa.DateTime(timezone=False), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=False), nullable=True),
        sa.PrimaryKeyConstraint('ip'),
    )


def downgrade() -> None:
    op.drop_table('login_attempts')
