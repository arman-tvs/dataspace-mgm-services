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
"""Retry policy of a delivery job (README 4): when to try again and when to give up.

A job that raises `store.Unavailable` (C2-M2 or C10-M1 not reachable) is tried again after 5 s,
doubling, at most 10 minutes between attempts and at most 10 attempts; after that it is logged as
not delivered. Any other error is logged once and not repeated. Logs carry the job label only
(rule and event id), never names or content.
"""
from __future__ import annotations

import logging
from typing import Callable

from modules.c11_m1 import store

log = logging.getLogger("portal.c11-m1")

FIRST_WAIT = 5.0     # README 4: seconds before the second attempt; tests patch it
MAX_WAIT = 600.0     # README 4: at most 10 minutes between attempts
MAX_ATTEMPTS = 10    # README 4: at most 10 attempts


def wait_before(attempt: int) -> float:
    """README 4: the wait after failed attempt `attempt` (1 = the first), doubling up to `MAX_WAIT`."""
    return min(FIRST_WAIT * 2 ** (attempt - 1), MAX_WAIT)


def attempt(job: Callable[[], None], label: str, number: int) -> bool:
    """Run attempt `number` of `job`; `True` when the job is finished (delivered, failed, or given up)."""
    try:
        job()
    except store.Unavailable:
        if number >= MAX_ATTEMPTS:
            log.warning("not delivered: %s after %d attempts", label, number)
            return True
        log.info("job %s attempt %d: neighbour unavailable, will retry", label, number)
        return False
    except Exception:   # a broken job must not stop the worker thread; logged with its traceback
        log.exception("job %s failed", label)
    return True
