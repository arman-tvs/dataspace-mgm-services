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
"""Public interface of C1-M3 Application Review: the steps `open-review` and `close-review`, the
query `getReviewStatusByApplication`, and the decisions of OSP staff that `router.py` calls.

Review cases, checks and the audit log are kept in memory (README 5); one lock stands for the
row lock of 6.8, so two reviewers deciding at the same time produce exactly one decision.
"""
from __future__ import annotations

import datetime as dt
import itertools
import os
import threading
import uuid

from portal_common import events
from portal_common.problems import Problem

from . import calls, checks

MODULE = "c1-m3"
FOUR_EYES = {"CHECK_FAILED", "DOCUMENTS", "ALWAYS"}
AUTO_KINDS = {"ONBOARDING", "TRANSFER"}
IN_REVIEW = ("OPEN", "AWAITING_SECOND_APPROVAL")

cases: dict[str, dict] = {}
by_application: dict[str, str] = {}
audit_log: list[dict] = []
_lock = threading.RLock()
_seq = itertools.count()


def reset() -> None:
    with _lock:
        cases.clear()
        by_application.clear()
        audit_log.clear()


def _now() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def _list(var: str, default: str) -> list[str]:
    return [v.strip() for v in os.environ.get(var, default).split(",") if v.strip()]


def config() -> dict:
    """Configuration of README 4, read at call time; invalid values raise ValueError (6.6)."""
    enabled = _list("ENABLED_CHECKS", ",".join(checks.ORDER))
    four_eyes = _list("FOUR_EYES_CASES", "CHECK_FAILED,DOCUMENTS")
    auto = _list("AUTO_APPROVE_KINDS", "")
    if bad := set(enabled) - set(checks.ORDER):
        raise ValueError(f"ENABLED_CHECKS: unknown checks {sorted(bad)}")
    if bad := set(four_eyes) - FOUR_EYES:
        raise ValueError(f"FOUR_EYES_CASES: unknown cases {sorted(bad)}")
    if bad := set(auto) - AUTO_KINDS:
        raise ValueError(f"AUTO_APPROVE_KINDS: not allowed {sorted(bad)} (REACTIVATION never, 6.6)")
    return {"enabled": enabled, "fourEyes": four_eyes, "auto": auto}


def required_checks(case: dict, cfg: dict) -> list[str]:
    """Enabled checks, plus `CSP_MATCH_EXPECTED` for `TRANSFER` and `REACTIVATION` (6.2), in the order of 6.2."""
    want = set(cfg["enabled"]) | ({"CSP_MATCH_EXPECTED"} if case["kind"] in ("TRANSFER", "REACTIVATION") else set())
    return [k for k in checks.ORDER if k in want]


def _audit(case: dict, operation: str, sub: str | None = None, step: dict | None = None) -> None:
    audit_log.append({"at": _now(), "sub": sub, "processId": (step or {}).get("processId"),
                      "stepRunId": (step or {}).get("stepRunId"), "companyId": case["companyId"],
                      "operation": operation, "reviewCaseId": case["id"], "applicationId": case["applicationId"]})


def _event_fields(case: dict) -> dict:
    return {"applicationId": case["applicationId"], "companyId": case["companyId"], "kind": case["kind"],
            "existingCompany": case["existingCompany"]}


def _approved(case: dict, sub: str | None, comment: str | None, auto: bool = False) -> None:
    now = _now()
    case.update(status="APPROVED", changedAt=now,
                decision={"decidedAt": now, "comment": comment, "decidedBy": sub, "autoApproved": auto})
    data = _event_fields(case)
    if case["kind"] in ("TRANSFER", "REACTIVATION"):
        data["bpn"] = case["cspBpn"]
    events.publish(MODULE, "ApplicationApproved", data)


def view(case: dict, application: dict | None = None) -> dict:
    """`ReviewCase` (openapi); `application` only for `GET /review-cases/{id}`."""
    out = {k: v for k, v in case.items() if not k.startswith("_") and k != "checks"}
    out["checks"] = [case["checks"][k] for k in checks.ORDER if k in case["checks"]]
    if application is not None:
        out["application"] = application
    return out


def _new_case(app: dict, status: str) -> dict:
    now = _now()
    case = {"id": str(uuid.uuid4()), "applicationId": app["id"], "companyId": app["companyId"], "kind": app["kind"],
            "existingCompany": bool(app.get("existingCompany")), "verification": app["verification"],
            "applicantSub": (app.get("applicant") or {}).get("sub"), "status": status, "openedAt": now,
            "cspBpn": None, "checks": {}, "firstApproval": None, "decision": None,
            "closure": {"closedAt": now, "reason": "WITHDRAWN"} if status == "CLOSED" else None,
            "changedAt": now, "_seq": next(_seq)}
    cases[case["id"]] = case
    by_application[app["id"]] = case["id"]
    return case


def _application(application_id: str) -> dict:
    app = calls.get_application(application_id)
    if app is None:
        raise Problem(MODULE, 404, "not-found", detail="application unknown", retryable=False)
    return app


def _four_eyes(case: dict, cfg: dict) -> list[str]:
    reasons = []
    if "CHECK_FAILED" in cfg["fourEyes"] and any(c["result"] == "FAILED" for c in case["checks"].values()):
        reasons.append("CHECK_FAILED")
    if "DOCUMENTS" in cfg["fourEyes"] and case["verification"] == "DOCUMENTS":
        reasons.append("DOCUMENTS")
    if "ALWAYS" in cfg["fourEyes"]:
        reasons.append("ALWAYS")
    return reasons


def _step_input(input: dict) -> str:
    aid = input.get("applicationId")
    if not aid:
        raise Problem(MODULE, 400, "validation", errors=[{"field": "applicationId", "message": "required"}],
                      retryable=False)
    return aid


# ------------------------------------------------------------------------------- steps (README 8)
def open_review(input: dict) -> dict:
    aid, cfg = _step_input(input), config()
    errors: list[str] = []
    with _lock:
        case = cases.get(by_application.get(aid, ""))
        if case is None or case["status"] == "OPEN":
            app = _application(aid)
            if case is None:
                if app["status"] == "SUBMITTED":
                    case = _new_case(app, "OPEN")
                elif app["status"] == "WITHDRAWN":
                    case = _new_case(app, "CLOSED")
                else:
                    raise Problem(MODULE, 409, "invalid-state", detail=f"application is {app['status']}",
                                  retryable=False)
            if case["status"] == "OPEN":
                for key in required_checks(case, cfg):
                    old = case["checks"].get(key)
                    if old and old["result"] != "ERROR":
                        continue
                    result, details = checks.run(key, app)
                    rejected = case.setdefault("_rejected", set())
                    if details.pop(checks.REJECTED, False):
                        rejected.add(key)
                    else:
                        rejected.discard(key)
                    case["checks"][key] = {"checkKey": key, "result": result, "details": details,
                                           "checkedAt": _now(), "attempts": (old or {}).get("attempts", 0) + 1}
                    if key == "CSP_MATCH_EXPECTED":
                        case["cspBpn"] = next((m["bpn"] for m in details.get("cspMatches", []) if m["expected"]), None)
                case["changedAt"] = _now()
                errors = [k for k, c in case["checks"].items() if c["result"] == "ERROR"]
                if not errors and _auto_approve(case, cfg):
                    _approved(case, None, None, auto=True)
        _audit(case, "open-review", step=input)
        if errors and set(errors) <= case.get("_rejected", set()):   # a repetition does not help (OPEN-QUESTIONS 11)
            raise Problem(MODULE, 502, "neighbour-rejected", detail=f"checks with ERROR: {', '.join(errors)}",
                          pendingChecks=errors, retryable=False)
        if errors:
            raise Problem(MODULE, 502, "upstream-error", detail=f"checks with ERROR: {', '.join(errors)}",
                          pendingChecks=errors, retryable=True)
        return {"stepRunId": input.get("stepRunId"), "state": "DONE",
                "result": {"reviewCaseId": case["id"], "applicationId": aid, "status": case["status"],
                           "checks": [{"checkKey": c["checkKey"], "result": c["result"]} for c in view(case)["checks"]]}}


def _auto_approve(case: dict, cfg: dict) -> bool:
    """6.6: kind in AUTO_APPROVE_KINDS, path EBW, every check PASSED, no four-eyes case."""
    return (case["kind"] in cfg["auto"] and case["verification"] == "EBW"
            and all(case["checks"].get(k, {}).get("result") == "PASSED" for k in required_checks(case, cfg))
            and not _four_eyes(case, cfg))


def close_review(input: dict) -> dict:
    aid = _step_input(input)
    with _lock:
        case = cases.get(by_application.get(aid, ""))
        if case is None:
            app = _application(aid)
            if app["status"] != "WITHDRAWN":
                raise Problem(MODULE, 409, "invalid-state", detail=f"application is {app['status']}", retryable=False)
            case = _new_case(app, "CLOSED")
        elif case["status"] == "APPROVED":
            raise Problem(MODULE, 409, "invalid-state", detail="review case already approved", retryable=False)
        elif case["status"] in IN_REVIEW:
            now = _now()
            case.update(status="CLOSED", changedAt=now, closure={"closedAt": now, "reason": input.get("reason") or "WITHDRAWN"})
        _audit(case, "close-review", step=input)
        return {"stepRunId": input.get("stepRunId"), "state": "DONE",
                "result": {"reviewCaseId": case["id"], "applicationId": aid, "status": case["status"]}}


# ------------------------------------------------------------------------------ query (README 9)
def get_review_status_by_application(*, applicationId: str, **_other) -> dict:
    case = cases.get(by_application.get(applicationId, ""))
    if case is None:
        raise Problem(MODULE, 404, "not-found")
    return {"reviewCaseId": case["id"], "applicationId": applicationId, "status": case["status"],
            "decidedAt": (case["decision"] or {}).get("decidedAt")}


# ------------------------------------------------------------------ operations of staff (README 7)
def _case(case_id: str) -> dict:
    case = cases.get(case_id)
    if case is None:
        raise Problem(MODULE, 404, "not-found")
    return case


def list_cases(status: list[str] | None, kind: list[str] | None, verification: list[str] | None,
               application_id: str | None, page: int, size: int) -> dict:
    statuses = status or list(IN_REVIEW)
    found = sorted((c for c in cases.values() if c["status"] in statuses and (not kind or c["kind"] in kind)
                    and (not verification or c["verification"] in verification)
                    and (not application_id or c["applicationId"] == application_id)), key=lambda c: c["_seq"])
    chunk = found[page * size:(page + 1) * size]
    apps = {a["id"]: a for a in calls.list_applications([c["applicationId"] for c in chunk])}
    counts = {"passed": "PASSED", "failed": "FAILED", "notApplicable": "NOT_APPLICABLE", "error": "ERROR"}
    items = []
    for c in chunk:
        item = {k: c[k] for k in ("id", "applicationId", "companyId", "kind", "verification", "status", "openedAt")}
        item["decidedAt"] = (c["decision"] or {}).get("decidedAt")
        item["checkCounts"] = {k: sum(x["result"] == v for x in c["checks"].values()) for k, v in counts.items()}
        if a := apps.get(c["applicationId"]):
            item["application"] = {"legalName": a.get("legalName"), "countryCode": a.get("countryCode"),
                                   "companyRoles": a.get("companyRoles", []), "submittedAt": a.get("submittedAt")}
        items.append(item)
    return {"items": items, "page": page, "size": size, "total": len(found)}


def get_case(case_id: str) -> dict:
    case = _case(case_id)
    return view(case, calls.get_application(case["applicationId"]) or {})


def _decision_allowed(case: dict) -> None:
    if calls.application_status(case["applicationId"]) == "WITHDRAWN":
        raise Problem(MODULE, 409, "application-withdrawn")


def approve(case_id: str, sub: str, comment: str | None) -> dict:
    """7.3, in the order of the README."""
    case, cfg = _case(case_id), config()
    _decision_allowed(case)
    with _lock:
        if case["status"] == "APPROVED":
            return view(case)
        if case["status"] not in IN_REVIEW:
            raise Problem(MODULE, 409, "invalid-state", detail=f"review case is {case['status']}")
        if sub == case["applicantSub"]:
            raise Problem(MODULE, 403, "own-application")
        if case["status"] == "AWAITING_SECOND_APPROVAL" and sub == case["firstApproval"]["approvedBy"]:
            return view(case)
        pending = [k for k in required_checks(case, cfg) if case["checks"].get(k, {}).get("result") in (None, "ERROR")]
        if pending:
            raise Problem(MODULE, 409, "checks-incomplete", pendingChecks=pending)
        csp = case["checks"].get("CSP_MATCH_EXPECTED", {})
        if case["kind"] in ("TRANSFER", "REACTIVATION") and csp.get("result") != "PASSED":
            raise Problem(MODULE, 409, "csp-match-required", cspOutcome=(csp.get("details") or {}).get("cspOutcome"))
        failed = [k for k in checks.ORDER if case["checks"].get(k, {}).get("result") == "FAILED"]
        if case["status"] == "OPEN" and failed and not comment:
            raise Problem(MODULE, 400, "comment-required", failedChecks=failed)
        reasons = _four_eyes(case, cfg)
        if case["status"] == "OPEN" and reasons:
            now = _now()
            case.update(status="AWAITING_SECOND_APPROVAL", changedAt=now,
                        firstApproval={"approvedBy": sub, "approvedAt": now, "comment": comment,
                                       "fourEyesReasons": reasons})
        else:
            _approved(case, sub, comment)
        _audit(case, "approve", sub=sub)
        return view(case)


def decline(case_id: str, sub: str, reason: str) -> dict:
    """7.4, in the order of the README."""
    case = _case(case_id)
    _decision_allowed(case)
    with _lock:
        if case["status"] == "DECLINED":
            return view(case)
        if case["status"] not in IN_REVIEW:
            raise Problem(MODULE, 409, "invalid-state", detail=f"review case is {case['status']}")
        if sub == case["applicantSub"]:
            raise Problem(MODULE, 403, "own-application")
        now = _now()
        case.update(status="DECLINED", changedAt=now,
                    decision={"decidedAt": now, "comment": reason, "decidedBy": sub, "autoApproved": False})
        events.publish(MODULE, "ApplicationDeclined", {**_event_fields(case), "reason": reason})
        _audit(case, "decline", sub=sub)
        return view(case)
