"""add product_cache table

Revision ID: a1b2c3d4e5f6
Revises: 990b42ec209b
Create Date: 2026-09-05 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "990b42ec209b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_cache",
        sa.Column("barcode", sa.String, primary_key=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("adapter", sa.String, nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("product_cache")
