"""Persist business-scoped AI assistant conversations."""

from alembic import op
import sqlalchemy as sa

revision = "d9137e2a4b10"
down_revision = "c842a135d921"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
    )
    op.create_index("ix_assistant_conversations_user_id", "assistant_conversations", ["user_id"])
    op.create_index("ix_assistant_conversations_business_id", "assistant_conversations", ["business_id"])
    op.create_index(
        "ix_assistant_conversations_owner_updated",
        "assistant_conversations",
        ["business_id", "user_id", "updated_at"],
    )
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("business_id", sa.String(36), sa.ForeignKey("businesses.id"), nullable=False),
        sa.CheckConstraint("role in ('user','assistant')", name="ck_assistant_message_role"),
        sa.UniqueConstraint("conversation_id", "sequence", name="uq_assistant_message_sequence"),
    )
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])
    op.create_index("ix_assistant_messages_business_id", "assistant_messages", ["business_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text('ALTER TABLE "assistant_conversations" ENABLE ROW LEVEL SECURITY'))
        op.execute(sa.text('ALTER TABLE "assistant_messages" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    op.drop_index("ix_assistant_messages_business_id", table_name="assistant_messages")
    op.drop_index("ix_assistant_messages_conversation_id", table_name="assistant_messages")
    op.drop_table("assistant_messages")
    op.drop_index("ix_assistant_conversations_owner_updated", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_business_id", table_name="assistant_conversations")
    op.drop_index("ix_assistant_conversations_user_id", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
