"""add review moderation

Revision ID: 0009_review_moderation
Revises: 0008_repair_reviews
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_review_moderation"
down_revision = "0008_repair_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repair_reviews", sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Reviews created before moderation already appeared publicly; preserve that behavior.
    op.execute(sa.text("UPDATE repair_reviews SET approved = 1"))


def downgrade() -> None:
    op.drop_column("repair_reviews", "approved")
