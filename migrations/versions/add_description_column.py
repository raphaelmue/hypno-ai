"""Add description column

Revision ID: add_description_column
Revises: initial_schema
Create Date: 2025-07-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_description_column'
down_revision: Union[str, None] = 'initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the description column to the routines table
    op.add_column('routines', sa.Column('description', sa.String(), nullable=True))


def downgrade() -> None:
    # Drop the description column from the routines table
    op.drop_column('routines', 'description')