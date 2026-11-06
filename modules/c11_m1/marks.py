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
"""Per-person state of a notification (README 5 `notification_state`, 7.4, 7.5).

Read and hidden are kept per person, also for staff notifications: one person's marks never change
another's (acceptance 13.9). Every function takes a stored notification of the caller's own inbox.
"""
from __future__ import annotations

from modules.c11_m1 import store
from modules.c11_m1.interface import MODULE
from portal_common.problems import Problem


def is_read(n: dict, sub: str | None) -> bool:
    """README 7.3: `read` for this person."""
    return _row(n, sub).get("readAt") is not None


def is_hidden(n: dict, sub: str | None) -> bool:
    """README 7.5: hidden for this person."""
    return _row(n, sub).get("hiddenAt") is not None


def is_open_task(n: dict) -> bool:
    """README 7.2, 7.5: a task (topic ACTION) that is not done yet."""
    return n["topic"] == "ACTION" and n["done"] is False


def mark_read(n: dict, sub: str | None) -> None:
    """README 7.4: set `read_at`; idempotent, the time of the first read is kept."""
    with store.LOCK:
        if not is_read(n, sub):
            _set(n, sub, readAt=store.now())


def mark_unread(n: dict, sub: str | None) -> None:
    """README 7.4: remove `read_at`; idempotent."""
    with store.LOCK:
        _set(n, sub, readAt=None)


def hide(n: dict, sub: str | None) -> None:
    """README 7.5: hide for this person; an open task gives 409 `task-open`; idempotent."""
    with store.LOCK:
        if is_open_task(n):
            raise Problem(MODULE, 409, "task-open")
        if not is_hidden(n, sub):
            _set(n, sub, hiddenAt=store.now())


def _row(n: dict, sub: str | None) -> dict:
    """The `notification_state` row of one person; empty if they never read or hid the notification."""
    return store.state.get((n["notificationId"], sub), {})


def _set(n: dict, sub: str | None, **fields: str | None) -> None:
    """Set fields of the person's row; the caller holds `store.LOCK`."""
    store.state.setdefault((n["notificationId"], sub), {"readAt": None, "hiddenAt": None}).update(fields)
