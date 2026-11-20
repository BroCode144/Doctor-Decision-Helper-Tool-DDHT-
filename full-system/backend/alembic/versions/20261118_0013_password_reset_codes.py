"""email codes get a purpose: confirming an address ("verify") or resetting a forgotten password ("reset")

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-18 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('email_codes', sa.Column('purpose', sa.String(length=16), server_default='verify', nullable=False))


def downgrade() -> None:
    op.execute("DELETE FROM email_codes WHERE purpose <> 'verify'")
    op.drop_column('email_codes', 'purpose')
