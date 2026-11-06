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
from __future__ import annotations

from modules.c2_m2.c2_m2_impl.internal.model import AppClientTemplate

from .row_mapper import RowMapper


class AppClientTemplateRowMapper(RowMapper):
    TABLE = "app_client_template"
    KEY = "app_id"
    COLUMNS = ("app_id", "provider_company_id", "app_name", "iam_client_id", "iam_client_uuid", "created_at",
               "changed_at")

    @staticmethod
    def to_params(t: AppClientTemplate) -> tuple:
        return (t.app_id, t.provider_company_id, t.app_name, t.iam_client_id, t.iam_client_uuid, t.created_at,
                t.changed_at)

    @classmethod
    def to_model(cls, row: dict) -> AppClientTemplate:
        return AppClientTemplate(app_id=cls.text(row["app_id"]), provider_company_id=cls.text(row["provider_company_id"]),
                                 app_name=row["app_name"], iam_client_id=row["iam_client_id"],
                                 iam_client_uuid=row["iam_client_uuid"], created_at=row["created_at"],
                                 changed_at=row["changed_at"])
