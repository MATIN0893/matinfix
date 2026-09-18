"""add repair reviews

Revision ID: 0008_repair_reviews
Revises: 0007_public_repair_links
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_repair_reviews"
down_revision = "0007_public_repair_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repair_reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("repair_id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["repair_id"], ["repairs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repair_id"),
    )
    op.create_index("ix_repair_reviews_repair_id", "repair_reviews", ["repair_id"], unique=True)
    op.create_index("ix_repair_reviews_workspace_id", "repair_reviews", ["workspace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_repair_reviews_workspace_id", table_name="repair_reviews")
    op.drop_index("ix_repair_reviews_repair_id", table_name="repair_reviews")
    op.drop_table("repair_reviews")
