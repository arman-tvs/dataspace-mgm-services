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
"""The list query of the own inbox (README 7.1): filters, sorting by `createdAt`, paging (FRAMEWORK 4.1).

Works on the `Notification` views it is given (the caller's inbox), so it knows nothing about who may
see what.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class Filters:
    """README 7.1 filters; `None` means "any". `done` applies to tasks only, so it leaves information out."""
    topic: str | None = None
    ntype: str | None = None
    read: bool | None = None
    done: bool | None = None
    created_since: dt.datetime | None = None

    def __post_init__(self) -> None:
        if self.created_since is not None:   # normalised once, not once per view
            object.__setattr__(self, "created_since", _utc(self.created_since))

    def matches(self, v: dict, created: dt.datetime | None = None) -> bool:
        """True if the view `v` passes every filter that is set; `created` is its parsed `createdAt`, if known."""
        return ((self.topic is None or v["topic"] == self.topic)
                and (self.ntype is None or v["type"] == self.ntype)
                and (self.read is None or v["read"] == self.read)
                and (self.done is None or v["done"] is self.done)
                and (self.created_since is None or (created or _utc(v["createdAt"])) >= self.created_since))


def list_page(views: list[dict], filters: Filters, *, newest_first: bool, page: int, size: int) -> dict:
    """README 7.1: schema `NotificationPage` of the views that match `filters`; each `createdAt` is parsed once."""
    timed = [(created, v) for v in views if filters.matches(v, created := _utc(v["createdAt"]))]
    timed.sort(key=lambda cv: cv[0], reverse=newest_first)
    items = [v for _, v in timed]
    return {"items": items[page * size:(page + 1) * size], "page": page, "size": size, "total": len(items)}


def _utc(value: str | dt.datetime) -> dt.datetime:
    """A time as an aware datetime; a time without offset counts as UTC (FRAMEWORK 4.1)."""
    t = dt.datetime.fromisoformat(value) if isinstance(value, str) else value
    return t if t.tzinfo else t.replace(tzinfo=dt.UTC)
