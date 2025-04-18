"""Add rate and comment to quote_carrier

Revision ID: 535311fd2577
Revises: f676dadd8dc0
Create Date: 2025-04-01 11:02:26.628540

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '535311fd2577'
down_revision = 'f676dadd8dc0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quote_carrier', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rate', sa.Numeric(precision=10, scale=2), nullable=True))
        batch_op.add_column(sa.Column('comment', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('quote_carrier', schema=None) as batch_op:
        batch_op.drop_column('comment')
        batch_op.drop_column('rate')

    # ### end Alembic commands ###
