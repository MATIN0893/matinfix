"""add comments and photos to repair status history

Revision ID: 0004_status_history_attachments
Revises: 0003_repair_assignments
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_status_history_attachments"
down_revision = "0003_repair_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repair_status_history", sa.Column("comment", sa.Text(), nullable=True))
    op.add_column("repair_status_history", sa.Column("photo_file_id", sa.String(length=256), nullable=True))


def downgrade() -> None:
    op.drop_column("repair_status_history", "photo_file_id")
    op.drop_column("repair_status_history", "comment")
