"""remove the DISPUTED record status: patients restrict a wrong record instead of marking it disputed

Existing DISPUTED records go back to ACTIVE, then the status is removed from the record_status lookup.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-19 12:00:00
"""
from typing import Sequence, Union

from alembic import op


revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE medical_records SET status = 'ACTIVE' WHERE status = 'DISPUTED'")
    op.execute("DELETE FROM record_status WHERE code = 'DISPUTED'")


def downgrade() -> None:
    op.execute("INSERT INTO record_status (code, description) VALUES "
               "('DISPUTED', 'Patient disputes the accuracy of this record.') ON CONFLICT DO NOTHING")
