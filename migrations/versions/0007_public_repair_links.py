"""add public repair tracking tokens

Revision ID: 0007_public_repair_links
Revises: 0006_repair_billing
"""

from secrets import token_urlsafe

from alembic import op
import sqlalchemy as sa

revision = "0007_public_repair_links"
down_revision = "0006_repair_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repairs", sa.Column("public_token", sa.String(length=64), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id FROM repairs WHERE public_token IS NULL")).fetchall()
    for (repair_id,) in rows:
        bind.execute(
            sa.text("UPDATE repairs SET public_token = :token WHERE id = :repair_id"),
            {"token": token_urlsafe(32), "repair_id": repair_id},
        )
    if bind.dialect.name != "sqlite":
        op.alter_column("repairs", "public_token", nullable=False)
    op.create_index("ix_repairs_public_token", "repairs", ["public_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_repairs_public_token", table_name="repairs")
    op.drop_column("repairs", "public_token")
