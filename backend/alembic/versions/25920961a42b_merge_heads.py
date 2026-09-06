"""merge_heads

Revision ID: 25920961a42b
Revises: b2c3d4e5f6a7, c4d5e6f7a8b9
Create Date: 2026-09-07 00:14:00.154559
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '25920961a42b'
down_revision: Union[str, None] = ('b2c3d4e5f6a7', 'c4d5e6f7a8b9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
