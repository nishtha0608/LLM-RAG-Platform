"""rich source citations

Revision ID: 40ad3ee983aa
Revises: 28b2966490bd
Create Date: 2026-07-05 11:44:10.477681
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '40ad3ee983aa'
down_revision: str | None = '28b2966490bd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A straight type cast from text[] to json isn't valid Postgres DDL; drop and
    # recreate instead. Old plain-string sources aren't structurally compatible with
    # the new SourceCitation shape anyway, so there's nothing worth preserving.
    op.drop_column('chat_messages', 'sources')
    op.add_column('chat_messages', sa.Column('sources', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'sources')
    op.add_column(
        'chat_messages',
        sa.Column('sources', postgresql.ARRAY(sa.VARCHAR(length=2048)), nullable=True),
    )
