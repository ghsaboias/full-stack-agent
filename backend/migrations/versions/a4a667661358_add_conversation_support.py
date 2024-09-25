"""Add conversation support

Revision ID: a4a667661358
Revises: fa1090a0210a
Create Date: 2024-09-25 19:46:33.605607

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a4a667661358'
down_revision = 'fa1090a0210a'
branch_labels = None
depends_on = None

def upgrade():
    # Create the conversation table
    op.create_table('conversation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Check if conversation_id column exists in chat_message table
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = inspector.get_columns('chat_message')
    if 'conversation_id' not in [c['name'] for c in columns]:
        op.add_column('chat_message', sa.Column('conversation_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(None, 'chat_message', 'conversation', ['conversation_id'], ['id'])

def downgrade():
    op.drop_constraint(None, 'chat_message', type_='foreignkey')
    op.drop_column('chat_message', 'conversation_id')
    op.drop_table('conversation')