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
"""Delivery jobs with retries (README 4).

A job is one recipient query plus the notifications it creates. `submit` hands it to one daemon
thread and returns at once, because the event relay thread calls it. A job that raises
`store.Unavailable` (C2-M2 or C10-M1 not reachable) runs again after 5 s, doubling, at most
10 minutes between attempts and at most 10 attempts; after that it is logged as not delivered.
`set_sync(True)` runs every attempt at once in the calling thread (tests).
"""
from __future__ import annotations

import heapq
import itertools
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from modules.c11_m1 import store

log = logging.getLogger("portal.c11-m1")

FIRST_WAIT = 5.0     # README 4: seconds before the second attempt; tests patch it
MAX_WAIT = 600.0     # README 4: at most 10 minutes between attempts
MAX_ATTEMPTS = 10    # README 4: at most 10 attempts


@dataclass(order=True)
class _Job:
    due: float
    seq: int
    run: Callable[[], None] = field(compare=False)
    label: str = field(compare=False)
    attempt: int = field(compare=False, default=1)


_cond = threading.Condition()
_jobs: list[_Job] = []           # heap ordered by `due`
_seq = itertools.count()
_thread: threading.Thread | None = None
_stop = threading.Event()
_sync = False


def wait_before(attempt: int) -> float:
    """README 4: the wait after failed attempt `attempt` (1 = the first), doubling up to `MAX_WAIT`."""
    return min(FIRST_WAIT * 2 ** (attempt - 1), MAX_WAIT)


def submit(job: Callable[[], None], *, label: str) -> None:
    """Run `job` in the background, retried on `store.Unavailable`; never blocks the caller.

    `label` names the job in the log (rule and event id, never names or content).
    """
    if _sync:
        _run_now(job, label)
        return
    with _cond:
        _ensure_thread()
        heapq.heappush(_jobs, _Job(time.monotonic(), next(_seq), job, label))
        _cond.notify()


def set_sync(on: bool) -> None:
    """Tests: run jobs in the calling thread, all attempts without waiting."""
    global _sync
    _sync = on


def reset() -> None:
    """Stop the thread, drop queued jobs and leave sync mode."""
    global _thread, _sync, _stop
    with _cond:
        _stop.set()
        _jobs.clear()
        _cond.notify_all()
        thread, _thread = _thread, None
        _stop = threading.Event()
        _sync = False
    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=5)


def _ensure_thread() -> None:
    """Start the worker thread on first use; the caller holds `_cond`."""
    global _thread
    if _thread is None or not _thread.is_alive():
        _thread = threading.Thread(target=_loop, args=(_stop,), name="c11-m1-worker", daemon=True)
        _thread.start()


def _loop(stop: threading.Event) -> None:
    """Take due jobs one by one; a job that needs another attempt goes back with its wait."""
    while True:
        with _cond:
            while not stop.is_set() and (not _jobs or _jobs[0].due > time.monotonic()):
                _cond.wait(_jobs[0].due - time.monotonic() if _jobs else None)
            if stop.is_set():
                return
            job = heapq.heappop(_jobs)
        if _attempt(job.run, job.label, job.attempt):
            continue
        with _cond:
            if not stop.is_set():
                heapq.heappush(_jobs, _Job(time.monotonic() + wait_before(job.attempt), next(_seq),
                                           job.run, job.label, job.attempt + 1))


def _run_now(job: Callable[[], None], label: str) -> None:
    """Sync mode: all attempts at once in the calling thread."""
    attempt = 1
    while not _attempt(job, label, attempt):
        attempt += 1


def _attempt(job: Callable[[], None], label: str, attempt: int) -> bool:
    """Run one attempt; `True` when the job is finished (delivered, failed, or given up)."""
    try:
        job()
    except store.Unavailable:
        if attempt >= MAX_ATTEMPTS:
            log.warning("not delivered: %s after %d attempts", label, attempt)
            return True
        log.info("job %s attempt %d: neighbour unavailable, will retry", label, attempt)
        return False
    except Exception:   # a broken job must not stop the worker thread; logged with its traceback
        log.exception("job %s failed", label)
    return True
