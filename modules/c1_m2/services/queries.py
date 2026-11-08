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
"""Queries for other modules (README 9)."""
from __future__ import annotations

from modules.c1_m2 import attestation, catalog, errors, store
from modules.c1_m2.services.common import public, summary


def get_application_internal(*, applicationId: str, **_other) -> dict:
    a = store.applications.get(applicationId)
    if not a:
        raise errors.not_found()
    detail = None
    if a.get("_attestation"):
        detail = a["_attestation"] | {"signatureCheck": attestation.signature_check(a["_raw"])}
    return public(a) | {"attestation": detail, "requiredAgreements": a["_requiredAgreements"]}


def list_applications_internal(*, applicationId: list[str] | str | None = None, **_other) -> list[dict]:
    """`ApplicationSummary` in the order of the request; unknown IDs are left out."""
    ids = [applicationId] if isinstance(applicationId, str) else applicationId or []
    return [summary(a) for i in ids if (a := store.applications.get(i))]


def list_agreements_internal(*, status: str | None = None, **_other) -> list[dict]:
    wanted = status or "ACTIVE"
    return [a for a in catalog.versions() if a["status"] == wanted]
