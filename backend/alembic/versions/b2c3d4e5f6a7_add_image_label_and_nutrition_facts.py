"""add image label and nutrition_facts table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-05 18:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add label column to images table
    op.add_column("images", sa.Column("label", sa.String, nullable=True))

    # Backfill existing single-image scans: label their one image as "front"
    op.execute("""
        UPDATE images SET label = 'front'
        WHERE id IN (
            SELECT i.id FROM images i
            JOIN (
                SELECT scan_id, COUNT(*) AS cnt FROM images GROUP BY scan_id
            ) counts ON counts.scan_id = i.scan_id
            WHERE counts.cnt = 1
        )
    """)

    # Create nutrition_facts table
    op.create_table(
        "nutrition_facts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("declaration_id", UUID(as_uuid=True), sa.ForeignKey("declarations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("nutrient", sa.String, nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("unit", sa.String, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("raw_text", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("nutrition_facts")
    op.drop_column("images", "label")
