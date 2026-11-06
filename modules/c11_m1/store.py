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
"""Data of C11-M1 Notifications (README 5), kept in memory for the hackathon.

The shared contract of the team: the other files of the module read and write the inbox only
through this module. Three threads use it (event relay, worker, HTTP
requests), so every read-modify-write runs under `LOCK`; slow work (neighbour calls) never does.
"""
from __future__ import annotations

import datetime as dt
import threading
import uuid
from typing import TYPE_CHECKING, Callable

from portal_common import sse, tokens

if TYPE_CHECKING:
    from modules.c11_m1.rules import Rule

LOCK = threading.RLock()
notifications: list[dict] = []           # README 5 `notification`; items carry `sourceEventId` (tests/test_sse.py)
state: dict[tuple[str, str], dict] = {}  # README 5 `notification_state`: (notificationId, sub) -> {readAt, hiddenAt}
applicants: dict[str, str] = {}          # README 5 `applicant`: applicationId -> applicantSub
SEEN_MAX = 10_000   # events and dedup keys remembered, oldest dropped first (as RECEIVED_MAX of portal_common.events)
processed: dict[tuple[str, str], dict] = {}   # README 5 `processed_event`: (source, id) -> {type, receivedAt, status}
_dedup: dict[tuple[str, str, str, str], None] = {}   # README 5 `dedup_key`: (rule, source, event id, receiver)
BROKER = sse.Broker()                    # README 7.6 stream events of the own inbox


class Unavailable(Exception):
    """A neighbour (C2-M2, C10-M1) is not reachable; the worker retries the job (README 4)."""


def event_key(event: dict) -> tuple[str, str]:
    """The identity of a CloudEvent: `source` and `id` together (FRAMEWORK 6)."""
    return str(event.get("source")), str(event.get("id"))


def first_seen(event: dict) -> bool:
    """README 6.4: record the event as processed; False if it was processed before (at-least-once delivery)."""
    key = event_key(event)
    with LOCK:
        if key in processed:
            return False
        _remember(processed, key, {"type": event.get("type"), "receivedAt": now(), "status": "DONE"})
    return True


def mark_failed(event: dict) -> None:
    """README 5 `processed_event.status`: a part of the event handling failed."""
    with LOCK:
        row = processed.get(event_key(event))
        if row is not None:
            row["status"] = "FAILED"


def _remember(seen: dict, key: tuple, value: object) -> None:
    """Add `key`, dropping the oldest entries above `SEEN_MAX` (memory stays bounded); the caller holds `LOCK`."""
    seen[key] = value
    while len(seen) > SEEN_MAX:
        del seen[next(iter(seen))]


def now() -> str:
    """The current time in ISO 8601 UTC (FRAMEWORK 4.1)."""
    return dt.datetime.now(dt.UTC).isoformat()


def add_notification(event: dict, rule: Rule, *, receiver_sub: str | None = None,
                     receiver_permission: str | None = None, done: bool | None = None) -> dict | None:
    """README 6.2: one notification of `rule` for one receiver; `None` if it already exists (6.4).

    Exactly one of `receiver_sub` (personal) and `receiver_permission` (staff) is given. `done` counts
    only for tasks (topic ACTION); for information it is `None`.
    """
    if (receiver_sub is None) == (receiver_permission is None):
        raise ValueError("give exactly one of receiver_sub and receiver_permission")
    data = event.get("data") or {}
    receiver = receiver_sub if receiver_sub is not None else f"permission:{receiver_permission}"
    key = (rule.id, *event_key(event), receiver)
    is_task = rule.topic == "ACTION"
    created = now()
    with LOCK:
        if key in _dedup:
            return None
        _remember(_dedup, key, None)
        n = {
            "notificationId": str(uuid.uuid4()), "sourceEventId": event.get("id"), "rule": rule.id,
            "type": rule.ntype, "topic": rule.topic,
            "receiverSub": receiver_sub, "receiverPermission": receiver_permission,
            "companyId": data.get(rule.company_field) if rule.company_field else None,
            "subjectType": rule.subject_type,
            "subjectId": data.get(rule.subject_field) if rule.subject_field else None,
            "content": dict(data), "forStaff": receiver_permission is not None,
            "done": bool(done) if is_task else None, "createdAt": created,
            "doneAt": created if is_task and done else None,
        }
        notifications.append(n)
    BROKER.publish("notification-created", {   # README 7.6: no content, only IDs, types and states
        "notificationId": n["notificationId"], "type": n["type"], "topic": n["topic"],
        "forStaff": n["forStaff"], "done": n["done"], "createdAt": n["createdAt"]}, _meta(n))
    return n


def close_tasks(rule_id: str, match: Callable[[dict], bool], done_at: str | None = None) -> list[dict]:
    """README 6.2: set `done` on the open tasks of `rule_id` that `match`; publish `notification-done`."""
    closed = []
    with LOCK:
        for n in notifications:
            if n["rule"] == rule_id and n["topic"] == "ACTION" and n["done"] is False and match(n):
                n["done"], n["doneAt"] = True, done_at or now()
                closed.append(n)
    for n in closed:
        BROKER.publish("notification-done", {"notificationId": n["notificationId"], "doneAt": n["doneAt"]}, _meta(n))
    return closed


def visible_to(n: dict, claims: dict) -> bool:
    """README 4 and 6.3: personal notifications of the caller, and staff ones whose permission is in the token."""
    if n["receiverSub"] is not None:
        return n["receiverSub"] == claims.get("sub")
    return n["receiverPermission"] in tokens.permissions(claims)


def stream_visible(meta: dict, claims: dict) -> bool:
    """README 7.6: the same rule for a stream event, from its `meta`."""
    if "sub" in meta:
        return meta["sub"] == claims.get("sub")
    return meta.get("permission") in tokens.permissions(claims)


def reset() -> None:
    """Forget everything (tests, `/scaffold/reset`); clears the lists and dicts in place."""
    with LOCK:
        notifications.clear()
        state.clear()
        applicants.clear()
        processed.clear()
        _dedup.clear()
    BROKER.reset()


def _meta(n: dict) -> dict:
    return {"sub": n["receiverSub"]} if n["receiverSub"] is not None else {"permission": n["receiverPermission"]}
