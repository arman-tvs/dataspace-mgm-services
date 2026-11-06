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
#  Assisted-By: GitHub Copilot
#################################################################################
"""OSP staff and their staff roles (README 7.15, 7.16), scope `osp`."""
from abc import abstractmethod

from modules.c2_m2.c2_m2_api.model import Page, StaffMember
from modules.c2_m2.c2_m2_rs_api.endpoint import Claims, JsonBody, PageNumber, PageSize, RestApi, UserId, api


class OspStaffApi(RestApi):
    @api.get("/osp/staff")
    @abstractmethod
    def list_staff(self, claims: Claims, page: PageNumber = 0, size: PageSize = 20) -> Page[StaffMember]: ...

    @api.put("/osp/staff/{userId}/roles")
    @abstractmethod
    def set_staff_roles(self, claims: Claims, user_id: UserId, body: JsonBody) -> StaffMember: ...
