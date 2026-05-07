"""add name and local_path to generation_tasks

Revision ID: a1b2c3d4e5f6
Revises: 457b06cd11cc
Create Date: 2026-05-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "457b06cd11cc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("generation_tasks", sa.Column("name", sa.String(64), nullable=True))
    op.add_column("generation_tasks", sa.Column("local_path", sa.String(), nullable=True))
    op.create_index("ix_generation_tasks_name", "generation_tasks", ["name"])


def downgrade() -> None:
    op.drop_index("ix_generation_tasks_name", table_name="generation_tasks")
    op.drop_column("generation_tasks", "local_path")
    op.drop_column("generation_tasks", "name")
