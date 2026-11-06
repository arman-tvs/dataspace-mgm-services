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
"""HTTP operations on the own inbox (README 7).

The own inbox (README 4, 6.3): personal notifications with the caller's `sub`, plus staff
notifications whose permission is in the token. Read and hidden state is kept per person
(`marks`). A notification outside the own inbox gives 404.
"""
from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response

from modules.c11_m1 import marks, store
from portal_common import problems, spec, sse, tokens
from portal_common.problems import Problem

MODULE = "c11-m1"
router = APIRouter(prefix=spec.module(MODULE).base_path, route_class=problems.route_class(MODULE), tags=[MODULE])


def _perm(method: str, path: str):
    """The permission of the spec operation (`x-permission`, here `view_notifications`); returns the claims."""
    return Depends(tokens.require_spec(MODULE, method, path))


def to_view(n: dict, sub: str | None) -> dict:
    """Schema `Notification` with `read` for the calling person (README 7.3)."""
    return {"notificationId": n["notificationId"], "type": n["type"], "topic": n["topic"],
            "companyId": n["companyId"], "subjectType": n["subjectType"], "subjectId": n["subjectId"],
            "content": n["content"], "forStaff": n["forStaff"], "read": marks.is_read(n, sub),
            "done": n["done"], "createdAt": n["createdAt"], "doneAt": n["doneAt"]}


def own_inbox(claims: dict) -> list[dict]:
    """README 4 and 7.1: the caller's notifications as `Notification` views, hidden ones left out."""
    sub = claims.get("sub")
    with store.LOCK:
        return [to_view(n, sub) for n in store.notifications
                if store.visible_to(n, claims) and not marks.is_hidden(n, sub)]


def _utc(value: str | dt.datetime) -> dt.datetime:
    """A time as an aware datetime; a time without offset counts as UTC (FRAMEWORK 4.1)."""
    t = dt.datetime.fromisoformat(value) if isinstance(value, str) else value
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)


def _matches(v: dict, topic: str | None, ntype: str | None, read: bool | None, done: bool | None,
             since: dt.datetime | None) -> bool:
    """README 7.1 filters; `done` applies to tasks only, so it leaves information out."""
    return ((topic is None or v["topic"] == topic) and (ntype is None or v["type"] == ntype)
            and (read is None or v["read"] == read) and (done is None or v["done"] is done)
            and (since is None or _utc(v["createdAt"]) >= since))


def _find(notification_id: str, claims: dict) -> dict:
    """The stored notification if it is in the caller's inbox, else Problem 404 `not-found` (README 7)."""
    with store.LOCK:
        for n in store.notifications:
            if n["notificationId"] == notification_id and store.visible_to(n, claims):
                return n
    raise Problem(MODULE, 404, "not-found")


@router.get("/notifications")
def list_notifications(claims: dict = _perm("GET", "/notifications"),
                       topic: Literal["INFO", "ACTION"] | None = None,
                       ntype: Annotated[str | None, Query(alias="type")] = None,
                       read: bool | None = None,
                       done: bool | None = None,
                       createdSince: dt.datetime | None = None,
                       sort: Literal["createdAt.desc", "createdAt.asc"] = "createdAt.desc",
                       page: Annotated[int, Query(ge=0)] = 0,
                       size: Annotated[int, Query(ge=1, le=100)] = 20):
    """README 7.1: filters, sorting by `createdAt`, paging as in FRAMEWORK 4.1; invalid filters give 400."""
    since = _utc(createdSince) if createdSince else None
    items = [v for v in own_inbox(claims) if _matches(v, topic, ntype, read, done, since)]
    items.sort(key=lambda v: _utc(v["createdAt"]), reverse=sort == "createdAt.desc")
    return {"items": items[page * size:(page + 1) * size], "page": page, "size": size, "total": len(items)}


@router.get("/notifications/count")
def count_notifications(claims: dict = _perm("GET", "/notifications/count")):
    """README 7.2: counters of the own inbox (hidden ones left out)."""
    items = own_inbox(claims)
    return {"total": len(items),
            "unread": sum(not v["read"] for v in items),
            "openTasks": sum(marks.is_open_task(v) for v in items),
            "unreadInfo": sum(v["topic"] == "INFO" and not v["read"] for v in items)}


@router.get("/notifications/events")
def stream_notification_events(request: Request, claims: dict = _perm("GET", "/notifications/events"),
                               last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None):
    """README 7.6: without `Last-Event-ID` only new events; an id no longer kept gives `resync`."""
    return sse.response(store.BROKER, request, claims, last_event_id,
                        visible=lambda meta: store.stream_visible(meta, claims), on_gap=lambda: [("resync", {})])


@router.get("/notifications/{notificationId}")
def get_notification(notificationId: str, claims: dict = _perm("GET", "/notifications/{notificationId}")):
    """README 7.3: one notification of the own inbox with `read` for the caller."""
    n = _find(notificationId, claims)
    with store.LOCK:
        return to_view(n, claims.get("sub"))


@router.post("/notifications/{notificationId}/read", status_code=204)
def mark_read(notificationId: str, claims: dict = _perm("POST", "/notifications/{notificationId}/read")):
    """README 7.4: set `read_at` for the caller; idempotent, the first time is kept."""
    marks.mark_read(_find(notificationId, claims), claims.get("sub"))
    return Response(status_code=204)


@router.post("/notifications/{notificationId}/unread", status_code=204)
def mark_unread(notificationId: str, claims: dict = _perm("POST", "/notifications/{notificationId}/unread")):
    """README 7.4: remove `read_at` for the caller; idempotent."""
    marks.mark_unread(_find(notificationId, claims), claims.get("sub"))
    return Response(status_code=204)


@router.post("/notifications/{notificationId}/hide", status_code=204)
def hide_notification(notificationId: str, claims: dict = _perm("POST", "/notifications/{notificationId}/hide")):
    """README 7.5: hide for the caller; an open task gives 409 `task-open`; idempotent."""
    marks.hide(_find(notificationId, claims), claims.get("sub"))
    return Response(status_code=204)
