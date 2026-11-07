---
name: implement-module-from-spec
description: Build or extend one portal module in modules/<id>/ from its spec in spec/ so that it works with the other modules on the first merge. Use when asked to implement, replace the stand-in of, or add operations, steps, queries or events to a module such as C3-M1 or c3_m1.
---

# Implement a module from the spec

Follow the steps in this order. The rules in `AGENTS.md` apply throughout. Work only in
`modules/<id>/` and in `tests/test_<id>_*.py`.

## 1. Read the spec

Read in this order, completely:

1. `spec/FRAMEWORK.md`: sections 4 (conventions), 6 (events), 7 (steps) and 7a (test IDs), and the
   flows in section 5 in which your module takes part.
2. `spec/<Module>/README.md` of your module, all sections.
3. `spec/<Module>/openapi.yaml`.
4. `spec/<Module>/open-points.md` and the points with your module in `spec/open-points.md`.
5. For every neighbour in section 11 of your README: the operation you call in the neighbour's
   `openapi.yaml`, so that you use its field names.

Update the spec first: `git -C spec pull --ff-only`.

## 2. List what the module must provide

Write a short list (in your answer or as notes, not as a file in the repository):

- Operations: method, path, `operationId`, `x-permission`, `x-permission-scope` (from `openapi.yaml`).
- Steps (`/steps/...`, README section 8): step name, Python name (`create-company` → `create_company`),
  input fields, preconditions, result fields, event.
- Queries (`/internal/...`, README section 9): `operationId`, Python name
  (`getApplicationInternal` → `get_application_internal`), parameters, response fields.
- Events the module publishes (README section 10, FRAMEWORK 6) and events it receives.
- Configuration variables (README section 4), with the exact names.
- Calls to neighbours (README section 11): target module, operation, needed permission, built-in
  stand-in.
- Error types (README section 12).

## 3. Start from the stand-in

Read `modules/<id>/router.py` and `modules/<id>/interface.py` of the stand-in. Keep every public
function name of `interface.py` and its signature. Other modules and Process Orchestration call
these names. You may rewrite the bodies. Remove `STANDIN = True`.

## 3a. Design the inside of the module

Before you write code, list the files of the module and the job of each, following `AGENTS.md`
"Inside a module" and ADR-0003 (`docs/architecture/decisions/ADR-0003-inside-a-module.md`):

| File | What goes in for this module |
|---|---|
| `router.py`, `schemas.py` | the routes of step 2 and their Pydantic request and response models |
| `interface.py` | the steps and queries of step 2, each delegating to the service |
| `service.py` (or `services/`) | the rules of README sections 6 to 9; dataclasses for the objects of section 5 |
| `store.py` | a repository `Protocol` for the tables of section 5, with an in-memory implementation |
| `gateways.py` | one function per neighbour operation of section 11 |
| `adapters/` | one `Protocol` and implementations per external system of section 11 (only if there are any) |
| `errors.py` | one factory per error type of section 12 |

Keep files under 500 lines and functions under 60 lines and a complexity of 10. Look at C2-M3
(layers), C3-M2 (dataclasses, `errors.py`) and C4-M2 (adapters) for examples.

## 4. Implement

- `interface.py`: one function per step and per query, following the call convention in
  `AGENTS.md`; each one only delegates to the service:
  - step: `def create_company(input: dict) -> dict`, returns
    `{"stepRunId": input["stepRunId"], "state": "DONE", "result": {...}}`;
  - query: `def get_application_internal(**params)`, parameters by their openapi names, returns
    the JSON body.
  - Errors: one factory per error type in `errors.py`, e.g.
    `def invalid_state(detail) -> Problem: return Problem("<module-id>", 409, "invalid-state", ...)`,
    with the names from README section 12 and FRAMEWORK 4.5, then `raise errors.invalid_state(...)`.
    `errors.py` is the only file that builds a `Problem`.
  - No token checks here. The caller in the same process has no token.
- `router.py`: a thin HTTP layer. Create the router with `standin.router(MODULE)` (base path and
  Problem Details). Each route checks the token and the permission with `standin.perm(MODULE,
  method, path)` (or `tokens.require_spec`), checks the scope (`company`, `osp`, `own`,
  FRAMEWORK 4.3), then calls the interface function. Business logic stays out of the router.
  Provide `reset()` and, if you receive events, `on_event(event)`.
- Own data: in `store.py`, behind a repository `Protocol` (in memory is fine for now, PostgreSQL
  later); the service works with dataclasses, never with the store's rows as `dict`s. Clear it in
  `reset()`. Never read or write the data of another module.
- Steps are idempotent (FRAMEWORK 4.4): find the object by the business key from the input,
  create only what is missing, return the same result again, and publish events only when
  something changed.
- Events are CloudEvents (FRAMEWORK 6): `events.publish(MODULE, "<Type>", {...})` with the name
  and exactly the fields of README section 10 in `data`. No secrets. In `on_event(event)`, read the
  name from `event["type"]` and the fields from `event["data"]`. The flat form
  `events.publish({"eventType": ...})` is deprecated.
- Configuration: read the variables of README section 4 with their exact names from `os.environ`
  in `reset()` or at call time. Installation settings with `settings.get(...)`.

## 5. Neighbours

For every call in README section 11:

- Call a neighbour in `gateways.py` only (one function per operation, mapping the answer to a
  dataclass), with `portal_common.neighbours.query("<your-module>", "<neighbour>",
  "<function>", **params)`, for example `neighbours.query("c3-m1", "c1-m2",
  "get_application_internal", applicationId=app_id)`. It resolves the address as FRAMEWORK 4.7
  defines it: `in-process` → direct call of the function in `modules.<neighbour>.interface`; a
  URL → HTTP with the service token. Either way a neighbour error arrives as
  `502 neighbour-rejected` (not retryable) or `502 upstream-error` (retryable).
- Empty address → the built-in stand-in described in section 11; `neighbours.is_standin("<neighbour>")`
  is true then. It answers with the field names of the neighbour's spec, not with names you choose.
- The function name is always the `operationId` in snake_case, also where section 11 names
  another in-process function (for example `get_company` → `query_company`).
- Import only from `modules.<neighbour>.interface`, never from its `router.py` or other files.
- A failed call is an error, not "not found". Only a 404 or an empty list means "not found".

## 6. Acceptance tests

- Write one pytest test per case of README section 13 in `tests/test_<id>_*.py`.
- Use the fixtures and helpers of `tests/conftest.py` (`person_token(...)`, `bearer(...)`) and
  the test data of FRAMEWORK 7a and `testdata/`.
- Check content, not only status codes: field values, the number of events, the state after a
  repetition, the `type` and `retryable` of errors.
- Test each step twice with the same input (idempotency).
- Test at least one call per interface function directly (in-process) and one over HTTP with a
  token.

## 7. Run the checks

```bash
uv run pytest -q tests/test_<id>_*.py
uv run pytest -q
uv run python demo.py
uv run python tools/quality/gate.py --changed
```

All four must pass. Fix every finding of the quality gate; never raise a number in
`tools/quality/baseline.json`. If `demo.py` fails at a step of your module, fix your module. If it fails
in another module, open an issue and do not change that module.

## 8. Open questions

Write every point where the spec is unclear, contradicts itself or is missing into
`modules/<id>/OPEN-QUESTIONS.md`: the question, the spec section, the reading you implemented,
and who could decide it (another module, the spec authors). Do not decide such points silently.

## 9. Final checklist

- [ ] Every operation of `openapi.yaml` that the team planned is implemented with the same path,
      method and permission.
- [ ] `interface.py` has every step and query with the names and signatures of the call
      convention; the stand-in names are kept.
- [ ] The router only checks token, permission and scope and then calls `interface.py`.
- [ ] The files follow `AGENTS.md` "Inside a module": `interface.py` delegates, rules in the service,
      data in the store (dataclasses), neighbours in `gateways.py`, errors in `errors.py`.
- [ ] Errors are `Problem` with the type names of the spec; steps always carry `retryable`.
- [ ] Configuration variables have the names of README section 4.
- [ ] Events are CloudEvents: the names of README section 10 in `type`, its fields in `data`
      (FRAMEWORK 6).
- [ ] No secrets in logs, events or results.
- [ ] Steps are idempotent.
- [ ] Imports from other modules come only from their `interface.py`.
- [ ] Test data comes only from FRAMEWORK 7a and `testdata/`.
- [ ] `uv run pytest -q`, `uv run python demo.py` and `uv run python tools/quality/gate.py` pass.
- [ ] `modules/<id>/OPEN-QUESTIONS.md` lists the open points.
- [ ] Nothing outside `modules/<id>/` and `tests/test_<id>_*.py` changed.
