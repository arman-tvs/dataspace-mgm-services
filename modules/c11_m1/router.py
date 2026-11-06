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
#  Assisted-By: Claude Code (claude-opus-5-5)
#################################################################################
"""C11-M1 Notifications: the module contract of the scaffold (`router`, `reset`, `on_event`).

The work happens in the other files of the folder: `rules` (R1 to R17), `engine` (one event in),
`closing` (tasks done), `recipients` (who gets a personal notification), `worker` (retries),
`store` (the inbox) and `api` (README 7).
"""
from __future__ import annotations

from modules.c11_m1 import closing, engine, store, worker
from modules.c11_m1.api import router

notifications = store.notifications   # the same list object; store.reset() clears it in place

__all__ = ["router", "reset", "on_event", "notifications"]


def reset() -> None:
    """Fresh state for tests and `/scaffold/reset`."""
    store.reset()
    closing.reset()
    worker.reset()


def on_event(event: dict) -> None:
    """Subscriber of the event relay (FRAMEWORK 6); C11-M1 runs before C12-M1 (scaffold registry)."""
    engine.handle(event)
