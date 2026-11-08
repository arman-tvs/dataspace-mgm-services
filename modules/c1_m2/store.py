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
"""The data of C1-M2 (README 5): applications with consents and supporting documents, the used attestation IDs and
the audit log, in memory. One lock stands for the row locks and partial unique indexes of 6.11; calls to neighbours
and to the JWKS run outside it."""
from __future__ import annotations

import itertools
import threading

applications: dict[str, dict] = {}
used_jtis: set[str] = set()
audit_log: list[dict] = []
lock = threading.RLock()
seq = itertools.count()


def reset() -> None:
    """Empty tables (the order counter `seq` keeps running, as before)."""
    with lock:
        applications.clear()
        used_jtis.clear()
        audit_log.clear()
