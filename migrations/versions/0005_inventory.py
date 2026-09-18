"""add inventory parts and repair usage

Revision ID: 0005_inventory
Revises: 0004_status_history_attachments
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_inventory"
down_revision = "0004_status_history_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_parts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "sku", name="uq_inventory_workspace_sku"),
    )
    op.create_index("ix_inventory_parts_workspace_id", "inventory_parts", ["workspace_id"])
    op.create_table(
        "repair_part_usage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("repair_id", sa.String(length=36), nullable=False),
        sa.Column("part_id", sa.String(length=36), nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repair_id"], ["repairs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["part_id"], ["inventory_parts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repair_id", "part_id", name="uq_repair_part_usage"),
    )
    op.create_index("ix_repair_part_usage_workspace_id", "repair_part_usage", ["workspace_id"])
    op.create_index("ix_repair_part_usage_repair_id", "repair_part_usage", ["repair_id"])
    op.create_index("ix_repair_part_usage_part_id", "repair_part_usage", ["part_id"])


def downgrade() -> None:
    op.drop_index("ix_repair_part_usage_part_id", table_name="repair_part_usage")
    op.drop_index("ix_repair_part_usage_repair_id", table_name="repair_part_usage")
    op.drop_index("ix_repair_part_usage_workspace_id", table_name="repair_part_usage")
    op.drop_table("repair_part_usage")
    op.drop_index("ix_inventory_parts_workspace_id", table_name="inventory_parts")
    op.drop_table("inventory_parts")
