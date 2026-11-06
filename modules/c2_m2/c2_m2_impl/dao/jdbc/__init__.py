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
"""Row mappers between PostgreSQL rows and internal models, and the Alembic migrations of the database `c2_m2`."""
from pathlib import Path

from .app_client_template_row_mapper import AppClientTemplateRowMapper
from .app_instance_client_row_mapper import AppInstanceClientRowMapper
from .audit_log_row_mapper import AuditLogRowMapper
from .company_row_mapper import CompanyRowMapper
from .company_user_row_mapper import CompanyUserRowMapper
from .invitation_row_mapper import InvitationRowMapper
from .role_assignment_log_row_mapper import RoleAssignmentLogRowMapper
from .row_mapper import RowMapper

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

__all__ = ["MIGRATIONS_DIR", "AppClientTemplateRowMapper", "AppInstanceClientRowMapper", "AuditLogRowMapper",
           "CompanyRowMapper", "CompanyUserRowMapper", "InvitationRowMapper", "RoleAssignmentLogRowMapper",
           "RowMapper"]
