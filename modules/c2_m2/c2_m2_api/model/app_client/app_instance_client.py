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
from modules.c2_m2.c2_m2_api.model.constants import InstanceClientStatus, InstanceKind

from modules.c2_m2.c2_m2_api.model.api_model import ApiModel


class AppInstanceClient(ApiModel):
    """Returned by the instance client steps 8.2 to 8.5 and the queries 9.2 and 9.3."""
    id: str
    app_id: str
    instance_kind: InstanceKind
    offer_subscription_id: str | None = None
    customer_company_id: str | None = None
    iam_client_id: str
    instance_url: str
    status: InstanceClientStatus
    created_at: str
    changed_at: str | None = None
