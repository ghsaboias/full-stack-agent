"""add foreign key constraint

Revision ID: 4609ceba0a41
Revises: a4a667661358
Create Date: 2024-09-25 16:50:13.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4609ceba0a41'
down_revision = 'a4a667661358'
branch_labels = None
depends_on = None

def upgrade():
    # Create a new table with the desired schema
    op.create_table('new_chat_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('generation_id', sa.String(length=50), nullable=True),
        sa.Column('tokens_prompt', sa.Integer(), nullable=True),
        sa.Column('tokens_completion', sa.Integer(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('image_data', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversation.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data from the old table to the new table
    op.execute('INSERT INTO new_chat_message SELECT id, conversation_id, role, content, timestamp, generation_id, tokens_prompt, tokens_completion, total_cost, image_data FROM chat_message')

    # Drop the old table
    op.drop_table('chat_message')

    # Rename the new table to the original name
    op.rename_table('new_chat_message', 'chat_message')

def downgrade():
    # Create the old table without the foreign key constraint
    op.create_table('old_chat_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('generation_id', sa.String(length=50), nullable=True),
        sa.Column('tokens_prompt', sa.Integer(), nullable=True),
        sa.Column('tokens_completion', sa.Integer(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('image_data', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Copy data from the current table to the old table
    op.execute('INSERT INTO old_chat_message SELECT id, conversation_id, role, content, timestamp, generation_id, tokens_prompt, tokens_completion, total_cost, image_data FROM chat_message')

    # Drop the current table
    op.drop_table('chat_message')

    # Rename the old table to the original name
    op.rename_table('old_chat_message', 'chat_message')