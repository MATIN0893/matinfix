"""add repair pricing and payment status

Revision ID: 0006_repair_billing
Revises: 0005_inventory
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_repair_billing"
down_revision = "0005_inventory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repairs", sa.Column("quoted_price", sa.Integer(), nullable=True))
    op.add_column("repairs", sa.Column("final_price", sa.Integer(), nullable=True))
    op.add_column("repairs", sa.Column("payment_status", sa.String(length=16), nullable=False, server_default="unpaid"))
    op.add_column("repairs", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_repairs_payment_status", "repairs", ["payment_status"])


def downgrade() -> None:
    op.drop_index("ix_repairs_payment_status", table_name="repairs")
    op.drop_column("repairs", "paid_at")
    op.drop_column("repairs", "payment_status")
    op.drop_column("repairs", "final_price")
    op.drop_column("repairs", "quoted_price")
