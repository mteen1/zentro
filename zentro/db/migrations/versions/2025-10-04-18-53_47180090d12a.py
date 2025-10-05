"""add roles for project and users.

Revision ID: 47180090d12a
Revises: d49dc2d0baee
Create Date: 2025-10-04 18:53:16.010216

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# define the enum types (don't auto-create them yet)
project_role_enum = postgresql.ENUM(
    "PROJECT_ADMIN",
    "PROJECT_MANAGER",
    "DEVELOPER",
    "REPORTER",
    "VIEWER",
    name="projectrole",
    create_type=False,
)

user_role_enum = postgresql.ENUM(
    "SUPER_ADMIN",
    "ADMIN",
    "USER",
    name="userrole",
    create_type=False,
)

# revision identifiers, used by Alembic.
revision = "47180090d12a"
down_revision = "d49dc2d0baee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Run the migration."""
    # create the enum types in DB (if they don't already exist)
    project_role_enum.create(op.get_bind(), checkfirst=True)
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # add columns using the already-created postgres ENUM types
    op.add_column(
        "project_users",
        sa.Column(
            "role",
            project_role_enum,
            nullable=True,
            server_default="PROJECT_ADMIN",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "role",
            user_role_enum,
            nullable=True,
            server_default="ADMIN",
        ),
    )

    op.alter_column(
        "users",
        "role",
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        "project_users",
        "role",
        nullable=False,
        server_default=None,
    )

    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)


def downgrade() -> None:
    """Undo the migration."""
    # remove index and columns first
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_column("users", "role")
    op.drop_column("project_users", "role")

    # then drop the enum types from the DB
    user_role_enum.drop(op.get_bind(), checkfirst=True)
    project_role_enum.drop(op.get_bind(), checkfirst=True)
