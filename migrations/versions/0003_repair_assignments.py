"""add repair assignments

Revision ID: 0003_repair_assignments
Revises: 0002_repair_status_history
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_repair_assignments"
down_revision = "0002_repair_status_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repair_assignments",
        sa.Column("repair_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("master_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["repair_id"], ["repairs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["master_id"], ["masters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("repair_id"),
    )
    op.create_index("ix_repair_assignments_workspace_id", "repair_assignments", ["workspace_id"])
    op.create_index("ix_repair_assignments_master_id", "repair_assignments", ["master_id"])


def downgrade() -> None:
    op.drop_index("ix_repair_assignments_master_id", table_name="repair_assignments")
    op.drop_index("ix_repair_assignments_workspace_id", table_name="repair_assignments")
    op.drop_table("repair_assignments")
