#################################################################################
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
"""C1-M3 Application Review: HTTP layer. Checks token and permission (all operations have scope
`osp`, README 6.7) and calls `interface.py`."""
from __future__ import annotations

from typing import Literal

from fastapi import Body, Query
from pydantic import BaseModel, Field

from portal_common import standin

from . import interface
from .interface import MODULE

router = standin.router(MODULE)

Status = Literal["OPEN", "AWAITING_SECOND_APPROVAL", "APPROVED", "DECLINED", "CLOSED"]
Kind = Literal["ONBOARDING", "REACTIVATION", "TRANSFER"]
Verification = Literal["EBW", "DOCUMENTS"]


class ApproveRequest(BaseModel):
    comment: str | None = Field(default=None, min_length=1, max_length=1000)


class DeclineRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


def reset() -> None:
    interface.reset()


def on_startup() -> None:
    interface.config()   # invalid configuration prevents the start (README 4, 6.6)


@router.get("/review-cases")
def list_review_cases(status: list[Status] | None = Query(None), kind: list[Kind] | None = Query(None),
                      verification: list[Verification] | None = Query(None), applicationId: str | None = None,
                      page: int = Query(0, ge=0), size: int = Query(20, ge=1, le=100),
                      _: dict = standin.perm(MODULE, "GET", "/review-cases")):
    return interface.list_cases(status, kind, verification, applicationId, page, size)


@router.get("/review-cases/{reviewCaseId}")
def get_review_case(reviewCaseId: str, _: dict = standin.perm(MODULE, "GET", "/review-cases/{reviewCaseId}")):
    return interface.get_case(reviewCaseId)


@router.post("/review-cases/{reviewCaseId}/approve")
def approve_review_case(reviewCaseId: str, body: ApproveRequest | None = Body(None),
                        claims: dict = standin.perm(MODULE, "POST", "/review-cases/{reviewCaseId}/approve")):
    return interface.approve(reviewCaseId, claims["sub"], body.comment if body else None)


@router.post("/review-cases/{reviewCaseId}/decline")
def decline_review_case(reviewCaseId: str, body: DeclineRequest,
                        claims: dict = standin.perm(MODULE, "POST", "/review-cases/{reviewCaseId}/decline")):
    return interface.decline(reviewCaseId, claims["sub"], body.reason)


@router.post("/steps/open-review")
def step_open_review(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/open-review")):
    return interface.open_review(body)


@router.post("/steps/close-review")
def step_close_review(body: dict = Body(...), _: dict = standin.perm(MODULE, "POST", "/steps/close-review")):
    return interface.close_review(body)


@router.get("/internal/review-cases")
def get_review_status_by_application(applicationId: str,
                                     _: dict = standin.perm(MODULE, "GET", "/internal/review-cases")):
    return interface.get_review_status_by_application(applicationId=applicationId)
