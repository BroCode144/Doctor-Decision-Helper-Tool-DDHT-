"""intake chat: intake records per booking and the patient's baseline answers

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-15 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'intake_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('patient_id', sa.String(length=32), nullable=False),
        sa.Column('appointment_id', sa.String(length=32), nullable=True),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('codes', sa.JSON(), nullable=True),
        sa.Column('red_flag', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('appointment_id'),
    )
    op.create_index('ix_intake_records_patient_id', 'intake_records', ['patient_id'])
    op.create_table(
        'patient_baselines',
        sa.Column('patient_id', sa.String(length=32), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('patient_id'),
    )


def downgrade() -> None:
    op.drop_table('patient_baselines')
    op.drop_index('ix_intake_records_patient_id', table_name='intake_records')
    op.drop_table('intake_records')
