"""add batch_id and batch_order

Revision ID: f13f71ffab1a
Revises: a1b2c3d4e5f6
Create Date: 2026-05-13 08:36:31.916330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f13f71ffab1a'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('generation_tasks', sa.Column('batch_id', sa.String(64), nullable=True))
    op.add_column('generation_tasks', sa.Column('batch_order', sa.Integer(), nullable=True))
    op.create_index('ix_generation_tasks_batch_id', 'generation_tasks', ['batch_id'])
    op.create_index('ix_generation_tasks_batch_order', 'generation_tasks', ['batch_order'])


def downgrade() -> None:
    op.drop_index('ix_generation_tasks_batch_order', 'generation_tasks')
    op.drop_index('ix_generation_tasks_batch_id', 'generation_tasks')
    op.drop_column('generation_tasks', 'batch_order')
    op.drop_column('generation_tasks', 'batch_id')
