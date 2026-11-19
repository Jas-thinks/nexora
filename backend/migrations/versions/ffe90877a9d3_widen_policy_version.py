"""widen policy_version

Revision ID: ffe90877a9d3
Revises: 644eb0fc7f82
Create Date: 2026-11-19 07:00:15.023358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffe90877a9d3'
down_revision: Union[str, Sequence[str], None] = '644eb0fc7f82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The control-arm label "baseline-rating-matched-v1" is 26 chars; SQLite never enforced the old limit, Postgres does.
    with op.batch_alter_table("daily_challenges") as b:
        b.alter_column("policy_version", existing_type=sa.String(length=20), type_=sa.String(length=40), existing_nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("daily_challenges") as b:
        b.alter_column("policy_version", existing_type=sa.String(length=40), type_=sa.String(length=20), existing_nullable=False)
