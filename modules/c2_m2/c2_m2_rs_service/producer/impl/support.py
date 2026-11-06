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
"""What every implementation needs: the module's services and the actor of the call."""
from portal_common import standin

from modules.c2_m2 import module
from modules.c2_m2.c2_m2_api.model.common import Actor
from modules.c2_m2.c2_m2_api.model.utils import MODULE


def services() -> module.C2M2Module:
    return module.current()


def company_actor(claims: dict, company_id: str) -> Actor:
    """Scope `company` (FRAMEWORK 4.3): another company stays invisible (404)."""
    standin.company_scope(MODULE, claims, company_id)
    return Actor.person(claims)


def osp_actor(claims: dict) -> Actor:
    """Scope `osp`: the permission is the whole check; the person is the actor for the audit log."""
    return Actor.person(claims)
