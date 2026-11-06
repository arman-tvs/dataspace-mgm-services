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

from modules.c2_m2.c2_m2_api.model.constants import InstanceClientStatus, InstanceKind
from modules.c2_m2.c2_m2_impl.internal.model import AppInstanceClient

from .row_mapper import RowMapper


class AppInstanceClientRowMapper(RowMapper):
    TABLE = "app_instance_client"
    KEY = "id"
    COLUMNS = ("id", "app_id", "instance_kind", "offer_subscription_id", "customer_company_id", "iam_client_id",
               "iam_client_uuid", "instance_url", "status", "created_at", "changed_at")

    @staticmethod
    def to_params(ic: AppInstanceClient) -> tuple:
        return (ic.id, ic.app_id, str(ic.instance_kind), ic.offer_subscription_id, ic.customer_company_id,
                ic.iam_client_id, ic.iam_client_uuid, ic.instance_url, str(ic.status), ic.created_at, ic.changed_at)

    @classmethod
    def to_model(cls, row: dict) -> AppInstanceClient:
        return AppInstanceClient(id=cls.text(row["id"]), app_id=cls.text(row["app_id"]),
                                 instance_kind=InstanceKind(row["instance_kind"]),
                                 offer_subscription_id=cls.text(row["offer_subscription_id"]),
                                 customer_company_id=cls.text(row["customer_company_id"]),
                                 iam_client_id=row["iam_client_id"], iam_client_uuid=row["iam_client_uuid"],
                                 instance_url=row["instance_url"], status=InstanceClientStatus(row["status"]),
                                 created_at=row["created_at"], changed_at=row["changed_at"])
