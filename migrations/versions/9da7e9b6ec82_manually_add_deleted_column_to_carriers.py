"""Manually add deleted column to carriers

Revision ID: 9da7e9b6ec82
Revises: c9041f35e721
Create Date: 2025-04-24 09:52:47.711153

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9da7e9b6ec82'
down_revision = 'c9041f35e721'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('carriers', sa.Column('deleted', sa.Boolean(), nullable=True, server_default=sa.text('false')))

def downgrade():
    op.drop_column('carriers', 'deleted')
