"""manually add CarrierAdmin and ShipperAdmin to enum

Revision ID: db96ce9eccf4
Revises: 7b0c9a958823
Create Date: 2025-03-28 09:35:50.231081

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'db96ce9eccf4'
down_revision = '7b0c9a958823'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE user_roles ADD VALUE IF NOT EXISTS 'CarrierAdmin';")
    op.execute("ALTER TYPE user_roles ADD VALUE IF NOT EXISTS 'ShipperAdmin';")

def downgrade():
    # PostgreSQL cannot drop enum values safely
    pass
