"""Add member_id to invoice

Revision ID: 9b7c4a1f2e6d
Revises: e4f8a9b2c1d8
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "9b7c4a1f2e6d"
down_revision = "e4f8a9b2c1d8"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name in ("mysql", "mariadb"):
        op.execute(
            "ALTER TABLE invoice "
            "ADD COLUMN member_id VARCHAR(512) NULL AFTER external_id"
        )
    else:
        op.add_column("invoice", sa.Column("member_id", sa.String(512), nullable=True))


def downgrade():
    op.drop_column("invoice", "member_id")
