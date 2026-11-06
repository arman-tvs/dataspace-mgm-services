#################################################################################
#  Copyright (c) 2026 Contributors to the Eclipse Foundation
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  This program and the accompanying materials are made available under the
#  terms of the Apache License, Version 2.0 which is available at
#  https://www.apache.org/licenses/LICENSE-2.0.
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.
#
#  AI Disclosure: This file was entirely AI-generated.
#  The AI-generated portions are made available under CC0-1.0 and not subject
#  to the project's license. The human contributor has reviewed and verified
#  that the code is correct.
#
#  SPDX-License-Identifier: Apache-2.0 AND CC0-1.0
#  Assisted-By: GitHub Copilot (claude-opus-5-5)
#################################################################################
"""Initial schema of the database c2_m2 (README section 5).

Revision ID: 0001
Revises:
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TS = sa.TIMESTAMP(timezone=True)
ACTOR_TYPES = "actor_type IN ('PERSON', 'PROCESS', 'SYSTEM')"


def upgrade() -> None:
    op.create_table(
        "app_client_template",
        sa.Column("app_id", pg.UUID, primary_key=True),
        sa.Column("provider_company_id", pg.UUID, nullable=False),
        sa.Column("app_name", sa.Text, nullable=False),
        sa.Column("iam_client_id", sa.Text, nullable=False, unique=True),
        sa.Column("iam_client_uuid", sa.Text),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("changed_at", TS, nullable=False),
        sa.CheckConstraint("char_length(app_name) BETWEEN 1 AND 255", name="app_client_template_app_name"),
    )

    op.execute("CREATE SEQUENCE client_number")

    op.create_table(
        "app_instance_client",
        sa.Column("id", pg.UUID, primary_key=True),
        sa.Column("app_id", pg.UUID, sa.ForeignKey("app_client_template.app_id"), nullable=False),
        sa.Column("instance_kind", sa.Text, nullable=False),
        sa.Column("offer_subscription_id", pg.UUID, unique=True),
        sa.Column("customer_company_id", pg.UUID),
        sa.Column("iam_client_id", sa.Text, nullable=False, unique=True),
        sa.Column("iam_client_uuid", sa.Text),
        sa.Column("instance_url", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("changed_at", TS, nullable=False),
        sa.CheckConstraint("instance_kind IN ('SINGLE', 'SUBSCRIPTION')", name="app_instance_client_kind"),
        sa.CheckConstraint("char_length(instance_url) <= 255", name="app_instance_client_url"),
        sa.CheckConstraint("status IN ('PENDING', 'ACTIVE', 'DISABLED')", name="app_instance_client_status"),
    )
    op.create_index("app_instance_client_one_single", "app_instance_client", ["app_id"], unique=True,
                    postgresql_where=sa.text("instance_kind = 'SINGLE' AND status <> 'DISABLED'"))

    op.create_table(
        "company",
        sa.Column("company_id", pg.UUID, primary_key=True),
        sa.Column("bpn", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("changed_at", TS, nullable=False),
        sa.CheckConstraint("bpn ~ '^BPNL[0-9A-Z]{12}$'", name="company_bpn"),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLING', 'DISABLED', 'ENABLING')", name="company_status"),
    )

    op.create_table(
        "company_user",
        sa.Column("id", pg.UUID, primary_key=True),
        sa.Column("user_id", pg.UUID, nullable=False),
        sa.Column("company_id", pg.UUID, sa.ForeignKey("company.company_id"), nullable=False),
        sa.Column("given_name", sa.Text),
        sa.Column("family_name", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("joined_via", sa.Text, nullable=False),
        sa.Column("invitation_id", pg.UUID),
        sa.Column("removal_reason", sa.Text),
        sa.Column("suspended_roles", pg.JSONB),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("changed_at", TS, nullable=False),
        sa.Column("removed_at", TS),
        sa.CheckConstraint("status IN ('ACTIVE', 'DISABLED', 'REMOVED')", name="company_user_status"),
        sa.CheckConstraint("joined_via IN ('ONBOARDING', 'INVITATION')", name="company_user_joined_via"),
        sa.CheckConstraint("removal_reason IN ('REMOVED_BY_COMPANY', 'REMOVED_BY_OSP', 'ACCOUNT_DELETED')",
                           name="company_user_removal_reason"),
    )
    op.create_index("company_user_one_binding", "company_user", ["user_id"], unique=True,
                    postgresql_where=sa.text("status IN ('ACTIVE', 'DISABLED')"))

    op.create_table(
        "invitation",
        sa.Column("id", pg.UUID, primary_key=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("company_id", pg.UUID),
        sa.Column("given_name", sa.Text),
        sa.Column("family_name", sa.Text),
        sa.Column("roles", pg.ARRAY(sa.Text), nullable=False),
        sa.Column("code_hash", sa.Text, nullable=False, unique=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("end_reason", sa.Text),
        sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("expires_at", TS, nullable=False),
        sa.Column("created_by", pg.UUID),
        sa.Column("accepted_by", pg.UUID),
        sa.Column("accepted_at", TS),
        sa.Column("created_at", TS, nullable=False),
        sa.Column("ended_at", TS),
        sa.CheckConstraint("kind IN ('COMPANY', 'STAFF')", name="invitation_kind"),
        sa.CheckConstraint("status IN ('OPEN', 'ACCEPTED', 'REVOKED', 'EXPIRED')", name="invitation_status"),
        sa.CheckConstraint("end_reason IN ('REVOKED', 'COMPANY_DISABLED', 'TOO_MANY_ATTEMPTS')",
                           name="invitation_end_reason"),
    )

    op.create_table(
        "role_assignment_log",
        sa.Column("id", pg.UUID, primary_key=True),
        sa.Column("occurred_at", TS, nullable=False),
        sa.Column("user_id", pg.UUID, nullable=False),
        sa.Column("company_id", pg.UUID),
        sa.Column("role_kind", sa.Text, nullable=False),
        sa.Column("iam_client_id", sa.Text, nullable=False),
        sa.Column("app_id", pg.UUID),
        sa.Column("app_instance_client_id", pg.UUID),
        sa.Column("role_name", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("actor_type", sa.Text, nullable=False),
        sa.Column("actor_sub", pg.UUID),
        sa.Column("process_id", pg.UUID),
        sa.Column("step_run_id", pg.UUID),
        sa.Column("operation", sa.Text, nullable=False),
        sa.CheckConstraint("role_kind IN ('COMPANY_PORTAL', 'STAFF_PORTAL', 'APP')", name="role_assignment_log_kind"),
        sa.CheckConstraint("action IN ('ADDED', 'REMOVED')", name="role_assignment_log_action"),
        sa.CheckConstraint(ACTOR_TYPES, name="role_assignment_log_actor_type"),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", pg.UUID, primary_key=True),
        sa.Column("occurred_at", TS, nullable=False),
        sa.Column("actor_type", sa.Text, nullable=False),
        sa.Column("actor_sub", pg.UUID),
        sa.Column("company_id", pg.UUID),
        sa.Column("process_id", pg.UUID),
        sa.Column("step_run_id", pg.UUID),
        sa.Column("operation", sa.Text, nullable=False),
        sa.Column("object_id", pg.UUID),
        sa.CheckConstraint(ACTOR_TYPES, name="audit_log_actor_type"),
    )


def downgrade() -> None:
    for table in ("audit_log", "role_assignment_log", "invitation", "company_user", "company", "app_instance_client"):
        op.drop_table(table)
    op.execute("DROP SEQUENCE client_number")
    op.drop_table("app_client_template")
