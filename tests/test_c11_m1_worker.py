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
"""C11-M1 retry policy and delivery worker (README 4): retries on `store.Unavailable`, give-up, sync mode and reset."""
import logging
import threading

import pytest

from modules.c11_m1 import retry, store, worker


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    """conftest does not reset module state; waits are zero so the background tests need no sleeps."""
    monkeypatch.setattr(retry, "FIRST_WAIT", 0.0)
    worker.reset()
    yield
    worker.reset()


def flaky(failures: int, done: threading.Event | None = None):
    """A job that raises `store.Unavailable` `failures` times, then succeeds; returns the job and its calls."""
    calls: list[str] = []

    def job():
        calls.append(threading.current_thread().name)
        if len(calls) <= failures:
            raise store.Unavailable()
        if done:
            done.set()
    return job, calls


def test_waits_double_from_five_seconds_up_to_ten_minutes(monkeypatch):
    monkeypatch.setattr(retry, "FIRST_WAIT", 5.0)
    assert [retry.wait_before(a) for a in range(1, 10)] == [5, 10, 20, 40, 80, 160, 320, 600, 600]


def test_sync_runs_in_the_calling_thread_and_retries():
    worker.set_sync(True)
    job, calls = flaky(2)
    worker.submit(job, label="R16/e1")
    assert calls == [threading.current_thread().name] * 3


def test_gives_up_after_the_last_attempt(caplog):
    worker.set_sync(True)
    job, calls = flaky(99)
    with caplog.at_level(logging.WARNING, logger="portal.c11-m1"):
        worker.submit(job, label="R16/e1")
    assert len(calls) == retry.MAX_ATTEMPTS
    assert [r.getMessage() for r in caplog.records] == ["not delivered: R16/e1 after 10 attempts"]


def test_other_errors_are_logged_and_not_retried(caplog):
    worker.set_sync(True)
    calls = []

    def broken():
        calls.append(1)
        raise ValueError("bug")
    with caplog.at_level(logging.ERROR, logger="portal.c11-m1"):
        worker.submit(broken, label="R7/e2")
    assert calls == [1] and caplog.records[0].exc_info


def test_background_thread_retries_until_success():
    done = threading.Event()
    job, calls = flaky(2, done)
    worker.submit(job, label="R16/e1")   # returns at once: the relay thread must not wait
    assert done.wait(5)
    assert len(calls) == 3 and set(calls) == {"c11-m1-worker"}


def test_reset_drops_waiting_jobs_and_sync_mode(monkeypatch):
    monkeypatch.setattr(retry, "FIRST_WAIT", 600.0)
    job, calls = flaky(5)
    first_try = threading.Event()
    worker.submit(lambda: (first_try.set(), job()), label="R16/e1")
    assert first_try.wait(5)
    worker.set_sync(True)
    worker.reset()   # the retry waits 10 minutes; reset drops it
    assert not worker._jobs and not worker._sync and len(calls) == 1
