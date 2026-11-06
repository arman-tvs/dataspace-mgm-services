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
"""HTTP operations on the own inbox (README 7). STARTER VERSION: 7.1 without filters, and 7.6.

Still to do (owner: Tanvir): filters, sorting and paging of 7.1, and 7.2 to 7.5 (count, read one,
read/unread, hide with 409 `task-open`, 404 for a notification outside the own inbox). Operations
not defined here answer 501 through the scaffold fallback until then.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from modules.c11_m1 import store
from portal_common import problems, spec, sse, tokens

MODULE = "c11-m1"
router = APIRouter(prefix=spec.module(MODULE).base_path, route_class=problems.route_class(MODULE), tags=[MODULE])


def _perm(method: str, path: str):
    """The permission of the spec operation (`x-permission`, here `view_notifications`); returns the claims."""
    return Depends(tokens.require_spec(MODULE, method, path))


def to_view(n: dict, sub: str | None) -> dict:
    """Schema `Notification` with `read` for the calling person (README 7.3)."""
    st = store.state.get((n["notificationId"], sub), {})
    return {"notificationId": n["notificationId"], "type": n["type"], "topic": n["topic"],
            "companyId": n["companyId"], "subjectType": n["subjectType"], "subjectId": n["subjectId"],
            "content": n["content"], "forStaff": n["forStaff"], "read": st.get("readAt") is not None,
            "done": n["done"], "createdAt": n["createdAt"], "doneAt": n["doneAt"]}


def own_inbox(claims: dict) -> list[dict]:
    """README 4: personal notifications of `sub` plus staff ones of the token's permissions, not hidden."""
    sub = claims.get("sub")
    with store.LOCK:
        return [to_view(n, sub) for n in store.notifications
                if store.visible_to(n, claims) and not store.state.get((n["notificationId"], sub), {}).get("hiddenAt")]


@router.get("/notifications")
def list_notifications(claims: dict = _perm("GET", "/notifications")):
    """README 7.1, newest first."""
    items = sorted(own_inbox(claims), key=lambda n: n["createdAt"], reverse=True)
    return {"items": items, "page": 0, "size": len(items), "total": len(items)}


@router.get("/notifications/events")
def stream_notification_events(request: Request, claims: dict = _perm("GET", "/notifications/events"),
                               last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None):
    """README 7.6: without `Last-Event-ID` only new events; an id no longer kept gives `resync`."""
    return sse.response(store.BROKER, request, claims, last_event_id,
                        visible=lambda meta: store.stream_visible(meta, claims), on_gap=lambda: [("resync", {})])
