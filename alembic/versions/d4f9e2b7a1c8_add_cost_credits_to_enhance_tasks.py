"""add cost_credits to enhance_tasks

Revision ID: d4f9e2b7a1c8
Revises: c3e8f1a2b4d5
Create Date: 2026-07-08 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4f9e2b7a1c8'
down_revision = 'c3e8f1a2b4d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('enhance_tasks', sa.Column('cost_credits', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('enhance_tasks', 'cost_credits')
