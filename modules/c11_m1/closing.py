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

Remembered closers are indexed by rule and object (`_by_key`) and expire in arrival order
(`_expiry`), so checking a new task costs the same however many closers are remembered; every
process end (`ProcessCompleted`) is one of them.

An event without a valid `time` counts as received now (OPEN-QUESTIONS.md).
"""
from __future__ import annotations

import datetime as dt
import logging
from collections import deque

from modules.c11_m1 import rules, store
from modules.c11_m1.rules import Rule

log = logging.getLogger("portal.c11-m1")

REMEMBER_FOR = dt.timedelta(hours=24)   # README 6.2

Key = tuple[str, tuple[str, ...], tuple]   # (rule id, closer fields, their values): one object of one rule


def _closer_table() -> dict[str, list[tuple[str, tuple[str, ...]]]]:
    """Closing event type -> (rule id, fields) from the fixed rule table (README 6.2)."""
    table: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for rule in rules.RULES:
        for closer, fields in rule.closers:
            if (rule.id, fields) not in table.setdefault(closer, []):
                table[closer].append((rule.id, fields))
    return table


_CLOSERS = _closer_table()
# Guarded by store.LOCK: remembered closers per object as (until, event time), and their expiry order.
_by_key: dict[Key, list[tuple[dt.datetime, dt.datetime]]] = {}
_expiry: deque[tuple[dt.datetime, Key]] = deque()


def _now() -> dt.datetime:
    """The clock of this module; tests replace it."""
    return dt.datetime.now(dt.UTC)


def _parse(time: object) -> dt.datetime:
    """CloudEvents `time` (RFC 3339) as an aware datetime; missing or invalid counts as now."""
    if isinstance(time, str) and time:
        try:
            parsed = dt.datetime.fromisoformat(time)
        except ValueError:
            log.warning("event time is not RFC 3339, counted as now")
        else:
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.UTC)
    elif time is not None:
        log.warning("event time is not a string, counted as now")
    return _now()


def _key(rule_id: str, fields: tuple[str, ...], data: dict) -> Key | None:
    """The object of `data` for these closer fields; None if a field is missing or not an ID string
    (FRAMEWORK 4.1), so a malformed event closes nothing instead of failing the whole event."""
    values = tuple(data.get(f) for f in fields)
    if not all(isinstance(v, str) and v for v in values):
        return None
    return rule_id, fields, values


def handle(event: dict) -> None:
    """README 6.2: close the open tasks this event closes and remember it as a closer for 24 hours."""
    data = event.get("data") or {}
    at = _parse(event.get("time"))
    done_at = at.isoformat()
    for rule_id, fields in _CLOSERS.get(event.get("type"), ()):
        key = _key(rule_id, fields, data)
        if key is None:
            continue
        match = dict(zip(fields, key[2]))
        # One lock with engine._store: a new task is either created after the closer is
        # remembered (and so created done) or exists before and is closed here.
        with store.LOCK:
            store.close_tasks(rule_id, lambda n, match=match: all(n["content"].get(f) == v for f, v in match.items()),
                              done_at=done_at)
            _remember(key, at)


def _remember(key: Key, at: dt.datetime) -> None:
    """Keep the closer for `REMEMBER_FOR` from now; the caller holds `store.LOCK`."""
    now = _now()
    _forget_expired(now)
    until = now + REMEMBER_FOR
    _by_key.setdefault(key, []).append((until, at))
    _expiry.append((until, key))


def _forget_expired(now: dt.datetime) -> None:
    """Drop closers older than 24 hours, oldest first; the caller holds `store.LOCK`."""
    while _expiry and _expiry[0][0] <= now:
        _, key = _expiry.popleft()
        kept = [e for e in _by_key.get(key, ()) if e[0] > now]
        if kept:
            _by_key[key] = kept
        else:
            _by_key.pop(key, None)


def closed_before(rule: Rule, data: dict, time: str | None) -> bool:
    """README 6.2: True if a remembered closer of `rule` for the same object is not earlier than `time`."""
    created, now = _parse(time), _now()
    with store.LOCK:
        _forget_expired(now)
        for fields in dict.fromkeys(fields for _, fields in rule.closers):
            key = _key(rule.id, fields, data)
            if key and any(until > now and created <= at for until, at in _by_key.get(key, ())):
                return True
    return False


def reset() -> None:
    """Forget the remembered closing events (tests, `/scaffold/reset`)."""
    with store.LOCK:
        _by_key.clear()
        _expiry.clear()
