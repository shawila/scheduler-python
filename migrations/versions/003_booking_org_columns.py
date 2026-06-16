"""replace store_email with org_id and admin_user_id in booking tables

Revision ID: 003
Revises: 002
Create Date: 2026-06-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('pending_booking') as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('admin_user_id', sa.Integer(), nullable=True))
        batch_op.drop_column('store_email')

    with op.batch_alter_table('booking') as batch_op:
        batch_op.add_column(sa.Column('org_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('admin_user_id', sa.Integer(), nullable=True))
        batch_op.drop_column('store_email')


def downgrade():
    with op.batch_alter_table('booking') as batch_op:
        batch_op.add_column(sa.Column('store_email', sa.String(120), nullable=True))
        batch_op.drop_column('admin_user_id')
        batch_op.drop_column('org_id')

    with op.batch_alter_table('pending_booking') as batch_op:
        batch_op.add_column(sa.Column('store_email', sa.String(120), nullable=True))
        batch_op.drop_column('admin_user_id')
        batch_op.drop_column('org_id')
