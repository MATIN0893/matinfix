"""add persistent repair status history

Revision ID: 0002_repair_status_history
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_repair_status_history"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repair_status_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("repair_id", sa.String(length=36), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repair_id"], ["repairs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_repair_status_history_workspace_id", "repair_status_history", ["workspace_id"])
    op.create_index("ix_repair_status_history_repair_id", "repair_status_history", ["repair_id"])
    op.create_index("ix_repair_status_history_changed_at", "repair_status_history", ["changed_at"])


def downgrade() -> None:
    op.drop_index("ix_repair_status_history_changed_at", table_name="repair_status_history")
    op.drop_index("ix_repair_status_history_repair_id", table_name="repair_status_history")
    op.drop_index("ix_repair_status_history_workspace_id", table_name="repair_status_history")
    op.drop_table("repair_status_history")
