"""add agent task coordination tables.

Revision ID: 9c0b79d1f3aa
Revises: add_soft_delete_chats
Create Date: 2026-05-09 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9c0b79d1f3aa"
down_revision = "add_soft_delete_chats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    op.create_table(
        "agent_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("endpoint_url", sa.String(length=1000), nullable=True),
        sa.Column("agent_card", sa.JSON(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("auth_scheme", sa.String(length=100), nullable=True),
        sa.Column("trust_level", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_agent_profiles_slug"), "agent_profiles", ["slug"], unique=True)

    op.create_table(
        "agent_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_modes", sa.JSON(), nullable=False),
        sa.Column("output_modes", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_profile_id"], ["agent_profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_skills_agent_profile_id"),
        "agent_skills",
        ["agent_profile_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_skills_name"), "agent_skills", ["name"], unique=False)

    op.create_table(
        "agent_task_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("context_id", sa.String(length=200), nullable=False),
        sa.Column("remote_task_id", sa.String(length=200), nullable=True),
        sa.Column("protocol", sa.String(length=50), nullable=False),
        sa.Column("state", sa.String(length=50), nullable=False),
        sa.Column("active_agent_id", sa.Integer(), nullable=True),
        sa.Column("delegated_by_agent_id", sa.Integer(), nullable=True),
        sa.Column("delegated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["active_agent_id"], ["agent_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["delegated_by_agent_id"],
            ["agent_profiles.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["delegated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index(
        op.f("ix_agent_task_links_active_agent_id"),
        "agent_task_links",
        ["active_agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_task_links_context_id"),
        "agent_task_links",
        ["context_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_task_links_remote_task_id"),
        "agent_task_links",
        ["remote_task_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_task_links_state"), "agent_task_links", ["state"], unique=False)
    op.create_index(
        op.f("ix_agent_task_links_task_id"),
        "agent_task_links",
        ["task_id"],
        unique=True,
    )

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_link_id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("mime_type", sa.String(length=200), nullable=True),
        sa.Column("parts", sa.JSON(), nullable=False),
        sa.Column("uri", sa.String(length=1000), nullable=True),
        sa.Column("created_by_agent_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_agent_id"], ["agent_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_link_id"], ["agent_task_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id"),
    )
    op.create_index(
        op.f("ix_agent_artifacts_artifact_id"),
        "agent_artifacts",
        ["artifact_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_agent_artifacts_task_link_id"),
        "agent_artifacts",
        ["task_link_id"],
        unique=False,
    )

    op.create_table(
        "agent_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("task_link_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=200), nullable=False),
        sa.Column("source_agent_id", sa.Integer(), nullable=True),
        sa.Column("target_agent_id", sa.Integer(), nullable=True),
        sa.Column("correlation_id", sa.String(length=200), nullable=True),
        sa.Column("causation_id", sa.String(length=200), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_agent_id"], ["agent_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_agent_id"], ["agent_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_link_id"], ["agent_task_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_events_causation_id"),
        "agent_events",
        ["causation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_events_correlation_id"),
        "agent_events",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_events_project_id"), "agent_events", ["project_id"], unique=False)
    op.create_index(
        op.f("ix_agent_events_task_id"),
        "agent_events",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_events_task_link_id"),
        "agent_events",
        ["task_link_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_events_type"), "agent_events", ["type"], unique=False)

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_link_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("sender_agent_id", sa.Integer(), nullable=True),
        sa.Column("sender_user_id", sa.Integer(), nullable=True),
        sa.Column("parts", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sender_agent_id"], ["agent_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sender_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_link_id"], ["agent_task_links.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index(
        op.f("ix_agent_messages_message_id"),
        "agent_messages",
        ["message_id"],
        unique=True,
    )
    op.create_index(op.f("ix_agent_messages_role"), "agent_messages", ["role"], unique=False)
    op.create_index(
        op.f("ix_agent_messages_task_link_id"),
        "agent_messages",
        ["task_link_id"],
        unique=False,
    )


def downgrade() -> None:
    """Undo the migration."""
    op.drop_index(op.f("ix_agent_messages_task_link_id"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_role"), table_name="agent_messages")
    op.drop_index(op.f("ix_agent_messages_message_id"), table_name="agent_messages")
    op.drop_table("agent_messages")
    op.drop_index(op.f("ix_agent_events_type"), table_name="agent_events")
    op.drop_index(op.f("ix_agent_events_task_link_id"), table_name="agent_events")
    op.drop_index(op.f("ix_agent_events_task_id"), table_name="agent_events")
    op.drop_index(op.f("ix_agent_events_project_id"), table_name="agent_events")
    op.drop_index(op.f("ix_agent_events_correlation_id"), table_name="agent_events")
    op.drop_index(op.f("ix_agent_events_causation_id"), table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index(op.f("ix_agent_artifacts_task_link_id"), table_name="agent_artifacts")
    op.drop_index(op.f("ix_agent_artifacts_artifact_id"), table_name="agent_artifacts")
    op.drop_table("agent_artifacts")
    op.drop_index(op.f("ix_agent_task_links_task_id"), table_name="agent_task_links")
    op.drop_index(op.f("ix_agent_task_links_state"), table_name="agent_task_links")
    op.drop_index(op.f("ix_agent_task_links_remote_task_id"), table_name="agent_task_links")
    op.drop_index(op.f("ix_agent_task_links_context_id"), table_name="agent_task_links")
    op.drop_index(op.f("ix_agent_task_links_active_agent_id"), table_name="agent_task_links")
    op.drop_table("agent_task_links")
    op.drop_index(op.f("ix_agent_skills_name"), table_name="agent_skills")
    op.drop_index(op.f("ix_agent_skills_agent_profile_id"), table_name="agent_skills")
    op.drop_table("agent_skills")
    op.drop_index(op.f("ix_agent_profiles_slug"), table_name="agent_profiles")
    op.drop_table("agent_profiles")
