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
"""Event handling of C11-M1 (README 4, 6.2, 6.4, 11.1): one CloudEvent in, notifications out.

Order per event: drop a repeated `id`; close tasks (`closing`); remember the applicant; apply the
rules of the event `type` that the OSP has not switched off (`DISABLED_RULES`); forget the applicant
when the application has ended. Personal notifications for roles of a company need a neighbour
call, so they run as a job of `worker` (retried on `store.Unavailable`); the applicant and staff
notifications are stored at once. Logs carry rule ids and event ids only, never `content`.
"""
from __future__ import annotations

import logging
import os

from modules.c11_m1 import closing, recipients, rules, store, worker
from modules.c11_m1.rules import Rule

log = logging.getLogger("portal.c11-m1")

_APPLICATION_ENDED = ("ApplicationCompleted", "ApplicationDeclined", "ApplicationWithdrawn")


def disabled_rules() -> set[str]:
    """`DISABLED_RULES` (README 4), read at every event so a test can change it."""
    return {r.strip().upper() for r in os.environ.get("DISABLED_RULES", "").split(",") if r.strip()}


def handle(event: dict) -> None:
    """Process one CloudEvent of the relay (FRAMEWORK 6) once per `source` and `id` (README 6.4;
    CloudEvents identifies an event by both, so two modules may use the same `id`)."""
    event_id, event_type = event.get("id"), event.get("type")
    if not event_id or not event_type:
        log.warning("event without id or type ignored")
        return
    key = store.event_key(event)
    with store.LOCK:
        if key in store.processed:
            return
        store.processed[key] = {"type": event_type, "receivedAt": store.now(), "status": "DONE"}
    data = event.get("data") or {}

    # The event is already marked processed, so no step may raise past this point: a failing part
    # is logged and marks the event FAILED, and the other parts still run.
    _guarded(key, "closing", lambda: closing.handle(event))
    _guarded(key, "applicant", lambda: _remember_applicant(event_type, data))

    off = disabled_rules()
    for rule in rules.for_event(event_type):
        if rule.id not in off:
            _guarded(key, f"rule {rule.id}", lambda rule=rule: _apply(rule, event))
    _guarded(key, "applicant", lambda: _forget_applicant(event_type, data))


def _guarded(key: tuple[str, str], part: str, run) -> None:
    """Run one part of the event handling; on an error log it and mark the event FAILED (README 6.4)."""
    try:
        run()
    except Exception:   # one broken part must not stop the others of the same event
        log.exception("%s failed for event %s", part, key[1])
        with store.LOCK:
            store.processed[key]["status"] = "FAILED"


def _remember_applicant(event_type: str, data: dict) -> None:
    """README 5 table `applicant`: the `sub` of the person who submitted the application."""
    if event_type == "ApplicationSubmitted" and data.get("applicationId") and data.get("applicantSub"):
        with store.LOCK:
            store.applicants[data["applicationId"]] = data["applicantSub"]


def _forget_applicant(event_type: str, data: dict) -> None:
    """README 5 table `applicant`: the row goes when the application has ended."""
    if event_type in _APPLICATION_ENDED:
        with store.LOCK:
            store.applicants.pop(data.get("applicationId"), None)


def _applicant(data: dict) -> str | None:
    """README 6.1 "applicant": from the table `applicant`, else `applicantSub` of the event."""
    application_id = data.get("applicationId")
    with store.LOCK:
        known = store.applicants.get(application_id) if isinstance(application_id, str) else None
    return known or data.get("applicantSub")


def _apply(rule: Rule, event: dict) -> None:
    data = event.get("data") or {}
    if rule.recipients == "applicant":
        sub = _applicant(data)
        if not sub:
            log.info("rule %s: no applicant known for event %s", rule.id, event["id"])
            return
        _store(rule, event, receiver_sub=sub)
    elif rule.recipients.startswith("staff:"):
        _store(rule, event, receiver_permission=rule.recipients.removeprefix("staff:"))
    else:
        worker.submit(lambda: _deliver(rule, event), label=f"{rule.id}/{event['id']}")


def _deliver(rule: Rule, event: dict) -> None:
    """Worker job: one personal notification per person; repeatable, since `add_notification` dedups."""
    for sub in dict.fromkeys(recipients.resolve(rule.recipients, event.get("data") or {})):
        _store(rule, event, receiver_sub=sub)


def _store(rule: Rule, event: dict, **receiver: str) -> None:
    """Decide `done` and store under one lock; `closing.handle` holds the same lock, so a closer
    is either remembered before or closes the task after (README 6.2). Recipients are resolved outside."""
    with store.LOCK:
        store.add_notification(event, rule, done=_created_done(rule, event), **receiver)


def _created_done(rule: Rule, event: dict) -> bool | None:
    """README 6.2: a task is created `done` if a remembered closer is not earlier than the task event."""
    if rule.topic != "ACTION":
        return None
    return closing.closed_before(rule, event.get("data") or {}, event.get("time"))
