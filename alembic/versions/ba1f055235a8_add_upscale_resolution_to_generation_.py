"""add upscale_resolution to generation_tasks

Revision ID: ba1f055235a8
Revises: 7286c2e95b70
Create Date: 2026-05-18 13:13:51.253815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ba1f055235a8'
down_revision: Union[str, Sequence[str], None] = '7286c2e95b70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('generation_tasks', sa.Column('upscale_resolution', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('generation_tasks', 'upscale_resolution')
