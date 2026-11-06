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
"""Closing of tasks (README 6.2, last paragraph; acceptance 13.2, 13.6, 13.7).

A closing event sets `done` on the open tasks of its rule for the same object: the fields of
`Rule.closers` in the event's `data` equal those in the task's `content`. Every closing event is also
remembered for 24 hours, because it can arrive before the event of its task (a quick approval, or
events delivered out of order). A task is then created `done` if the event that creates it did not
occur later than the remembered closer (CloudEvents attribute `time`). After a retrigger the same
step can fail again; that failure is later than the retrigger, so its new task stays open (13.6).

An event without a valid `time` counts as received now (OPEN-QUESTIONS.md).
"""
from __future__ import annotations

import datetime as dt
import logging

from modules.c11_m1 import rules, store
from modules.c11_m1.rules import Rule

log = logging.getLogger("portal.c11-m1")

REMEMBER_FOR = dt.timedelta(hours=24)   # README 6.2
_remembered: list[dict] = []            # {rule, key, time, until}; guarded by store.LOCK


def _now() -> dt.datetime:
    """The clock of this module; tests replace it."""
    return dt.datetime.now(dt.UTC)


def _parse(time: str | None) -> dt.datetime:
    """CloudEvents `time` (RFC 3339) as an aware datetime; missing or invalid counts as now."""
    if time:
        try:
            parsed = dt.datetime.fromisoformat(time)
        except ValueError:
            log.warning("event time is not RFC 3339, counted as now")
        else:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)
    return _now()


def _matches(values: dict, key: dict) -> bool:
    """Same object: every field of the closer has the same value."""
    return all(values.get(f) == v for f, v in key.items())


def handle(event: dict) -> None:
    """README 6.2: close the open tasks this event closes and remember it as a closer for 24 hours."""
    event_type, data = event.get("type"), event.get("data") or {}
    at = _parse(event.get("time"))
    done_at = at.isoformat()
    for rule in rules.RULES:
        for closer, fields in rule.closers:
            if closer != event_type or any(data.get(f) is None for f in fields):
                continue
            key = {f: data[f] for f in fields}
            store.close_tasks(rule.id, lambda n, key=key: _matches(n["content"], key), done_at=done_at)
            _remember(rule.id, key, at)


def _remember(rule_id: str, key: dict, at: dt.datetime) -> None:
    now = _now()
    with store.LOCK:
        _remembered[:] = [r for r in _remembered if r["until"] > now]
        _remembered.append({"rule": rule_id, "key": key, "time": at, "until": now + REMEMBER_FOR})


def closed_before(rule: Rule, data: dict, time: str | None) -> bool:
    """README 6.2: True if a remembered closer of `rule` for the same object is not earlier than `time`."""
    created, now = _parse(time), _now()
    with store.LOCK:
        return any(r["rule"] == rule.id and r["until"] > now and _matches(data, r["key"]) and created <= r["time"]
                   for r in _remembered)


def reset() -> None:
    """Forget the remembered closing events (tests, `/scaffold/reset`)."""
    with store.LOCK:
        _remembered.clear()
