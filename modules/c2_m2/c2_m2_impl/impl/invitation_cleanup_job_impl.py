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

import logging
import threading
from collections.abc import Callable

from modules.c2_m2.c2_m2_impl.internal.services import InvitationCleanupJob

log = logging.getLogger("c2-m2.invitations")


class InvitationCleanupJobImpl(InvitationCleanupJob):
    """Runs the cleanup of expired invitations once an hour in a daemon thread (README 4, 6.8)."""

    def __init__(self, expire_overdue: Callable[[], int], interval_seconds: float = 3600) -> None:
        self.expire_overdue = expire_overdue
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def loop() -> None:
            while not self._stop.wait(self.interval):
                try:
                    self.expire_overdue()
                except Exception:  # noqa: BLE001 - the next run tries again
                    log.exception("cleanup of expired invitations failed")

        self._thread = threading.Thread(target=loop, name="c2-m2-invitation-cleanup", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
