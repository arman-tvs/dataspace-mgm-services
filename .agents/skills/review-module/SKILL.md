---
name: review-module
description: Review one portal module in modules/<id>/ against its spec in spec/ and the rules in AGENTS.md, and report a findings list. Use before a pull request, after implementing a module, or when asked to review, check or audit a module such as C3-M1 or c3_m1.
---

# Review a module

Review the module in `modules/<id>/` and its tests in `tests/test_<id>_*.py`. Read the spec of
the module (`README.md`, `openapi.yaml`, `open-points.md`) and `spec/FRAMEWORK.md` sections 4, 6
and 7a first. Do not change code during the review. Report what you find.

## Checklist

1. **Operations:** every implemented path and method exists in `openapi.yaml`, with the same
   `operationId`, request fields and response fields. No paths that the spec does not have.
2. **Permissions:** every route checks the token and the `x-permission` of the operation
   (`standin.perm` or `tokens.require_spec`, not a hard-coded name). The scope of
   `x-permission-scope` is checked as in FRAMEWORK 4.3: `company` → another company's object
   gives 404; `own` → `sub` must own the object.
3. **Errors:** every error is a `portal_common.problems.Problem` with a type name from README
   section 12 or FRAMEWORK 4.5. Validation errors give 400, not 422. Every step error carries
   `retryable` (`true` only for temporary errors). No own exception handlers or error formats.
4. **Call convention:** `interface.py` exists and has every step (`create-company` →
   `create_company(input: dict) -> dict`) and every query (`operationId` in snake_case,
   `**params` by openapi names). The names of the stand-in are kept. Steps return
   `{stepRunId, state, result}`. The router only checks token, permission and scope, then calls
   the interface function.
5. **Imports:** the module imports from other modules only `modules.<other>.interface`. No
   imports from another module's `router.py` or internal files. No changes outside
   `modules/<id>/` and `tests/test_<id>_*.py`.
6. **Neighbours:** HTTP calls go through `portal_common.neighbours` (service token, error rule).
   No own HTTP client for module calls, no call without token. A failed neighbour call is not
   treated as "not found". The built-in stand-in uses the field names of the neighbour's spec.
7. **Configuration:** variable names exactly as in README section 4. Read in `reset()` or at call
   time, not at import. Installation settings through `portal_common.settings`. No own names for
   neighbour addresses.
8. **Events:** event names and fields match FRAMEWORK section 6 and README section 10. Published
   as CloudEvents with `portal_common.events.publish(MODULE, "<Type>", {data})`, the fields in
   `data`; no flat `{"eventType": ...}` events (deprecated). `on_event` reads `event["type"]` and
   `event["data"]`. Events only when something changed.
9. **Secrets:** no passwords, client secrets, tokens or API keys in logs, events, step results or
   error details (FRAMEWORK 4.6).
10. **Idempotency (FRAMEWORK 4.4):** each step finds its object by a business key from the input,
    creates only what is missing, returns the same result on repetition and publishes no second
    event. Preconditions of README section 8 are checked.
11. **Test data:** IDs and persons from FRAMEWORK 7a and `testdata/`. No own IDs for objects that
    7a lists.
12. **Tests:** every case of README section 13 has a test. Tests check content (field values,
    number of events, state after repetition, error `type` and `retryable`), not only status
    codes. Steps are tested twice with the same input.
13. **Silent failures:** no `except` that hides an error, no success result with empty content
    (for example a step `DONE` without the object it should create).
14. **Checks run:** `uv run pytest -q`, `uv run python demo.py` and
    `uv run python tools/quality/gate.py` pass. Run all three and report the result. If one fails,
    decide first whether the module or the kit (`demo.py`, a kit test, a stand-in) contradicts the
    spec, and quote the spec section.
15. **Open questions:** points where the code chooses a reading of an unclear spec are listed in
    `modules/<id>/OPEN-QUESTIONS.md`.
16. **Layers (ADR-0003, `AGENTS.md` "Inside a module"):** `interface.py` only delegates; the rules
    are in the service, data in the store behind a `Protocol`, neighbour calls in `gateways.py`,
    external systems in `adapters/` behind a `Protocol`, every `Problem` built in `errors.py`.
    Imports point down only; service and store import no `fastapi` or `pydantic`.
17. **Data:** dataclasses inside, Pydantic only in `schemas.py`, `dict` only at `interface.py`;
    camelCase only at the edges. No `dict[str, Any]` passed between service and store.
18. **Readability:** files under 500 lines, functions under 60 lines and a complexity of 10, type
    hints on every function; names that say what a thing is; no duplicated logic (the same mapping
    or check written twice); comments that explain why, with the spec section. The gate counts the
    first three; judge the rest by reading.

## Output

Return a findings list, most severe first. One line per finding:

`<severity> | <checklist no.> | <file>:<line> | <what is wrong> | <spec reference> | <proposed fix>`

Severity: `blocker` (breaks the merge or a flow), `high` (wrong behaviour), `medium`, `low`.
End with the result of `uv run pytest -q`, `uv run python demo.py` and
`uv run python tools/quality/gate.py`, and the number of findings per severity. If there are no findings for a checklist item, do not list it.
