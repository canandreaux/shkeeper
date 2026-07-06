"""Make invoice external_id unique

Revision ID: f1a6c2d9e0b4
Revises: 9b7c4a1f2e6d
Create Date: 2026-06-29 00:00:00.000000

"""
from alembic import op


revision = "f1a6c2d9e0b4"
down_revision = "9b7c4a1f2e6d"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.create_index(
            "uq_invoice_external_id", "invoice", ["external_id"], unique=True
        )
    else:
        op.create_unique_constraint(
            "uq_invoice_external_id", "invoice", ["external_id"]
        )
