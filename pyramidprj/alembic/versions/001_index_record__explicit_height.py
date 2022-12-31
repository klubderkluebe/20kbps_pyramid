"""IndexRecord.explicit_height

Revision ID: b534668d3fa1
Revises: 8b7836e7c305
Create Date: 2022-12-31 15:58:29.103862

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b534668d3fa1'
down_revision = '8b7836e7c305'
branch_labels = None
depends_on = None

def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('index_record', sa.Column('explicit_height', sa.Integer(), nullable=True))
    # ### end Alembic commands ###

def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('index_record', 'explicit_height')
    # ### end Alembic commands ###
