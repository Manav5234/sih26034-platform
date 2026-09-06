"""add consumer_flags table

Revision ID: c4d5e6f7a8b9
Revises: 990b42ec209b
Create Date: 2026-09-06 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = '990b42ec209b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    flag_status = postgresql.ENUM('NEW', 'ACKNOWLEDGED', 'RESOLVED', 'DISMISSED', name='flag_status', create_type=False)
    flag_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'consumer_flags',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scan_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scans.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('reported_fields', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('reporter_note', sa.Text(), nullable=True),
        sa.Column('reporter_contact', sa.Text(), nullable=True),
        sa.Column('status', flag_status, nullable=False, server_default='NEW', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('reviewed_by_officer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('officers.id'), nullable=True, index=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('officer_notes', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('consumer_flags')
    postgresql.ENUM(name='flag_status').drop(op.get_bind(), checkfirst=True)
