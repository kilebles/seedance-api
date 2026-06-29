"""add image_tasks

Revision ID: c3e8f1a2b4d5
Revises: ba1f055235a8
Create Date: 2026-06-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e8f1a2b4d5'
down_revision: Union[str, Sequence[str], None] = 'ba1f055235a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'image_tasks',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('size_requested', sa.String(length=32), nullable=True),
        sa.Column('watermark', sa.Boolean(), nullable=False),
        sa.Column('seed_requested', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('image_size', sa.String(length=32), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_image_tasks_user_id'), 'image_tasks', ['user_id'], unique=False)
    op.create_index(op.f('ix_image_tasks_status'), 'image_tasks', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_image_tasks_status'), table_name='image_tasks')
    op.drop_index(op.f('ix_image_tasks_user_id'), table_name='image_tasks')
    op.drop_table('image_tasks')
