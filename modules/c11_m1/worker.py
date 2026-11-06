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
"""Delivery jobs with retries (README 4). STARTER VERSION: runs a job once, at once.

Still to do (owner: Tanvir): a background thread that repeats a job after `store.Unavailable`
with growing waits (5 s, doubling, at most 10 minutes, at most 10 attempts), then logs the job as
not delivered; `set_sync(True)` keeps the current behaviour for tests.
"""
from __future__ import annotations

import logging
from typing import Callable

from modules.c11_m1 import store

log = logging.getLogger("portal.c11-m1")


def submit(job: Callable[[], None], *, label: str) -> None:
    """Run `job`; it may raise `store.Unavailable` when a neighbour does not answer."""
    try:
        job()
    except store.Unavailable:
        log.warning("job %s not delivered: neighbour unavailable", label)


def set_sync(on: bool) -> None:
    """Tests: run jobs in the calling thread."""


def reset() -> None:
    """Drop queued jobs."""
