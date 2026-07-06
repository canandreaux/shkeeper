"""Drop invoice external_id unique constraint

Revision ID: a2c4e6f8b0d1
Revises: f1a6c2d9e0b4
Create Date: 2026-06-29 00:00:00.000000

"""
from alembic import op


revision = "a2c4e6f8b0d1"
down_revision = "f1a6c2d9e0b4"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        op.drop_index("uq_invoice_external_id", table_name="invoice")
    else:
        op.drop_constraint("uq_invoice_external_id", "invoice", type_="unique")
