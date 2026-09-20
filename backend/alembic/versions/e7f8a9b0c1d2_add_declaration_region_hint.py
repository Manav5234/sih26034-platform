"""add heuristic declaration region hint

Revision ID: e7f8a9b0c1d2
Revises: 25920961a42b
Create Date: 2026-09-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "25920961a42b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("declarations", sa.Column("region_hint", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("declarations", "region_hint")
