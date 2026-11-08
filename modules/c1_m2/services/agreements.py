#################################################################################
#  Copyright (c) 2026 Technovative Solutions
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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""Versions of the terms (README 7.15, 7.16)."""
from __future__ import annotations

from modules.c1_m2 import catalog, errors, store
from modules.c1_m2.errors import MODULE
from modules.c1_m2.services.checks import check_agreement
from modules.c1_m2.services.common import now_iso, paged
from portal_common import events


def list_agreement_versions(agreement_key: str | None, status: str | None, page: int, size: int) -> dict:
    found = [a for a in catalog.versions() if (not agreement_key or a["agreementKey"] == agreement_key)
             and (not status or a["status"] == status)]
    found.sort(key=lambda a: a["createdAt"], reverse=True)
    found.sort(key=lambda a: a["agreementKey"])
    return paged(found, page, size)


def create_agreement_version(body: dict, sub: str) -> dict:
    """7.16."""
    invalid = check_agreement(body)
    if invalid:
        raise errors.validation(invalid)
    with store.lock:
        versions = catalog.versions()
        if any(a["agreementKey"] == body["agreementKey"] and a["version"] == body["version"] for a in versions):
            raise errors.conflict("this version of the terms already exists")
        for a in versions:
            if a["agreementKey"] == body["agreementKey"]:
                a["status"] = "INACTIVE"
        new = {"agreementKey": body["agreementKey"], "version": body["version"], "party": body["party"],
               "scope": body["scope"], "companyRoles": list(body.get("companyRoles") or []), "title": body["title"],
               "documentUrls": body["documentUrls"], "status": "ACTIVE", "reconsentRequired": body["reconsentRequired"],
               "reconsentDueAt": body.get("reconsentDueAt"),
               "createdAt": now_iso(), "createdBy": sub}
        versions.append(new)
        store.audit_log.append({"at": now_iso(), "sub": sub, "processId": None, "stepRunId": None, "companyId": None,
                          "operation": "createAgreementVersion", "applicationId": None,
                          "objectId": f"{new['agreementKey']}:{new['version']}"})
        events.publish(MODULE, "AgreementVersionActivated", {"agreementKey": new["agreementKey"],
                                                             "version": new["version"], "party": new["party"],
                                                             "reconsentRequired": new["reconsentRequired"],
                                                             "reconsentDueAt": new["reconsentDueAt"]})
        return new
