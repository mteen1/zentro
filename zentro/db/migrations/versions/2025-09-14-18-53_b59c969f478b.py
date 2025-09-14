"""drop dummy.

Revision ID: b59c969f478b
Revises: 2b7380507a71
Create Date: 2025-09-14 18:53:42.772257

"""
from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = "b59c969f478b"
down_revision = "2b7380507a71"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Drop the dummy_model table
    op.drop_table('dummy_model')

def downgrade() -> None:
    # Recreate the table if needed (optional)
    op.create_table('dummy_model',
        sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
        sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), autoincrement=False, nullable=True),
        sa.PrimaryKeyConstraint('id', name='dummy_model_pkey')
    )
