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
"""Calls of the core services API with their audit entry (README 5, 11.1).

Every call writes an audit entry with the HTTP status and the CSP's error type only; a call without an
answer writes the audit type of `CspUnreachable` and answers 502 `upstream-error` (retryable, README 12).
Services call `csp_calls.call(...)` through the module, so a test can replace `call`.
"""
from __future__ import annotations

from modules.c3_m2 import errors, store
from modules.c3_m2.adapters import csp
from modules.c3_m2.adapters.csp import CspAnswer, JsonObject


def call(operation: str, method: str, path: str, body: JsonObject | None = None, params: JsonObject | None = None,
         *, company_id: str | None = None, bpn: str | None = None) -> CspAnswer:
    """One call of the core services API (README 11.1), audited."""
    try:
        status, answer = csp.request(method, path, body, params)
    except csp.CspUnreachable as e:
        store.record_audit(operation, company_id, bpn, None, e.kind)
        raise errors.upstream_error(str(e)) from e
    store.record_audit(operation, company_id, bpn, status, csp.csp_type(answer))
    return status, answer
