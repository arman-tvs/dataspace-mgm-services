# Instructions for coding agents

For coding agents (Claude Code, Codex, GitHub Copilot) and the people who use them.
`CLAUDE.md` is a link to this file. `.github/copilot-instructions.md` (the Dataspace Captain) defers to the
rules of this file.

## What this repository is

The Eclipse Tractus-X Data Space Management Service, the backend of the new portal, at the hackathon
as one Python application (Python 3.12, FastAPI).
Every module of the spec has a folder `modules/<id>/` and runs as a stand-in at first. Each team
replaces the stand-in of its module with its implementation. `demo.py` runs the flows across all
modules and shows whether they work together.

Green module tests are not enough: the module must work with the other modules on the first merge.
Merges break on field names between modules, missing service tokens, own error formats, own
variable names, own test data and silent errors. The rules below prevent this.

## Rules

1. Work only in your team's folder `modules/<id>/` (for example `modules/c3_m1/`). Outside it, you
   may only add your module tests as `tests/test_<id>_*.py` (for example `tests/test_c3_m1_steps.py`).
2. Never change another team's module, `portal_common/`, `controllers/`, `scaffold/`, `tools/`, `iam/`, `ebw/`, `testdata/`,
   `config/` or `spec/`. If something there is wrong or missing, open an issue and work with the
   current state.
3. The spec in `spec/` is the contract. Read `spec/FRAMEWORK.md`, then the `README.md`,
   `openapi.yaml` and `open-points.md` of your module. Paths, methods, field names, permissions,
   error types and events come from there. Do not invent names.
4. Use `portal_common` for shared tasks. Never build your own version of them:
   - `tokens`: token check; `tokens.require_spec(module, method, path)` takes the permission from
     `x-permission` in `openapi.yaml`; `tokens.service_token(module)` for calls to neighbours.
   - `problems`: `Problem` and `problems.route_class(module)` (validation errors 400, never 422;
     unhandled errors 500 as Problem Details).
   - `settings`: installation settings (FRAMEWORK 4.8), for example `settings.get("ospCompanyId")`.
   - `events`: `events.publish(MODULE, "<Type>", {data})` publishes a CloudEvent (FRAMEWORK 6) and
     returns it; `MODULE` is the module id in `interface.py` (for example `"c3-m1"`).
   - `sse`: Server-Sent Events for the UI, `sse.Broker()` and `sse.response(...)` (paths ending in `/events`).
   - `neighbours`: `neighbours.query(caller, target, function, **params)` calls a neighbour's
     interface function in-process or over HTTP with service token, with the shared error rule.
   - `standin`: `standin.router(module)`, `standin.perm(...)`, `standin.step_reply(...)`.
5. Follow the call convention below exactly.
6. Configuration variables: use the names exactly as in section 4 ("Configuration") of your module
   README. Read them from the process environment in `reset()` or at call time, never at import.
   `config/osp-*/module-config.json` sets the values per installation. Do not read the address
   variable of a neighbour yourself; `portal_common.neighbours` resolves it. It reads
   `<MODULE>_URL` (for example `C3_M1_URL`) and `MODULE_URLS`, not yet the names of section 4
   (`COMPANY_URL`, `REVIEW_URL`, ...). `neighbours.is_standin("<neighbour>")` tells you when to
   answer with your built-in stand-in (empty address).
7. Test data only from FRAMEWORK 7a and `testdata/` (helpers in `tools/testdata.py`). Do not
   create other IDs for objects that 7a lists.
8. Events: names and fields as in FRAMEWORK section 6 and section 10 of your README. Every event is
   a CloudEvent (FRAMEWORK 6, OP-54). Publish with `events.publish(MODULE, "<Type>", {data})`; the
   fields of section 10 go into `data`. Receive events in `on_event(event)` in `router.py`: the name
   is `event["type"]`, the id `event["id"]`, the fields are in `event["data"]`. The flat form
   `events.publish({"eventType": ...})` is deprecated.
9. No secrets (passwords, client secrets, tokens, API keys) in logs, events or step results
   (FRAMEWORK 4.6).
10. If the spec is unclear or contradicts itself, do not guess silently. Write the question in
    `modules/<id>/OPEN-QUESTIONS.md`, implement the reading the spec supports most directly, and
    name that reading there.

## Call convention between modules (binding)

1. Every module `modules/<id>/` (id like `c1_m2`) has `interface.py` with its public functions.
   Other modules import ONLY from there: `from modules.c1_m2.interface import get_application_internal`.
2. Names: step = step name in snake_case (`create-company` → `create_company`); query =
   operationId in snake_case (`getApplicationInternal` → `get_application_internal`).
3. Signatures: step `def create_company(input: dict) -> dict` (input = JSON body of
   `POST /steps/<step>` incl. `processId`, `stepRunId`; returns `{stepRunId, state, result}`);
   query `def get_application_internal(**params)` (path and query parameters by their openapi
   names, for example `applicationId=...`; returns the JSON body). No token in-process.
4. Errors: raise `portal_common.problems.Problem` with `type`, `status`, `retryable`. Example:
   `raise Problem("c3-m1", 409, "invalid-state", detail="...", retryable=False)` gives the `type`
   `urn:c3-m1:problem:invalid-state`.
5. The router is a thin HTTP layer (token, permission, then the interface function).
6. Neighbour address per FRAMEWORK 4.7: `in-process` → direct call of the interface function;
   URL → HTTP with service token (`portal_common.neighbours`); empty → built-in stand-in
   (`neighbours.is_standin(target)`). If README section 11 names an in-process function that
   differs from this convention (for example `get_company`), the convention wins.
7. C12 finds steps and queries by these names. Stand-in modules expose the same functions, so a
   team replaces the stand-in folder and nothing else changes.

The folder name uses `c3_m1`; the spec, the URL path, `Problem` and `service_token` use `c3-m1`.

## The module folder

`interface.py` (public functions), `router.py` (`router` under `/api/<id>`, `reset()`, optional
`on_event(event)` and `on_startup()`; remove `STANDIN = True`), an empty `__init__.py`. Further
files of the module (for example `service.py`, data files) belong in the same folder.
Operations you have not implemented yet are added from the spec (steps answer `DONE`, others 501).

APIs of the installation that belong to no module live in `controllers/`, laid out as in the Industry
Core Hub backend: one folder per API category and version, one file per controller,
`controllers/fastapi/routers/<category>/v1/<name>_api.py` with its own `router`, mounted under
`/api/v1` by `controllers/fastapi/__init__.py`. The first one is the event inbox
`POST /api/v1/events/inbox` (FRAMEWORK 6, OP-54): split-out modules deliver their CloudEvents there.
Module APIs never go there; they stay in `modules/<id>/router.py` under `/api/<module>`.

## Inside a module

The spec defines the outside of a module; the inside follows
[ADR-0003](docs/architecture/decisions/ADR-0003-inside-a-module.md). In short:

| File | Job | May not import |
|---|---|---|
| `router.py` | HTTP only: token, permission, scope, then `interface` | service, store, gateways, adapters |
| `schemas.py` | Pydantic request and response models of `openapi.yaml` | other layers |
| `interface.py` | facade: the steps and queries, `dict` in and out, delegates to the service | store, gateways, adapters |
| `service.py` (or `services/`) | rules, preconditions, idempotency; dataclasses, no `fastapi`/`pydantic` | router, interface |
| `store.py` | repository: a `Protocol` with an in-memory and a PostgreSQL implementation | service and above |
| `gateways.py` | one typed function per neighbour operation; the only file that imports `portal_common.neighbours` | service and above |
| `adapters/` | external systems that are not modules, each behind a `Protocol` | service and above |
| `errors.py` | one factory per error type of README section 12; the only file that builds `Problem(...)` | other layers |

- Data: dataclasses inside, Pydantic only in `schemas.py`, `dict` only at `interface.py`; camelCase only at the edges.
- Types: parse at the edge, precise types inside. Never `Any` in a signature (the gate rejects it); `object` only for
  a function that checks unknown input and narrows it right there.
  A module that passes `dict`s may go `dict` -> `TypedDict` -> dataclass step by step.
- Limits: at most 500 lines per file, 60 lines and a complexity of 10 per function, type hints on every function.
- In `interface.py` write each step and query as a one-line `def` that calls the service; do not re-export with
  `from .service import ...` (`module-map` counts only functions defined with `def`).
- HTTP layer (FastAPI): request bodies and responses are Pydantic models of `schemas.py` that follow `openapi.yaml`
  (never `body: dict = Body(...)`), `operation_id=` is the spec's `operationId`, handlers are sync `def`, token and
  permission are dependencies. The gate compares the generated OpenAPI with `openapi.yaml` (`contract`). Reference:
  C3-M2.
- Every file has a layer name (`gateways.py`, not `calls.py`; token validation and DID resolution in `adapters/`);
  webhooks of external systems are routes in `router.py`; a stand-in adapter calls back through a registered port,
  never by importing the service. More cases: ADR-0003 section 5.
- Tests use `interface.py`, the router and the store's functions, not internals, so a refactor changes no test.
- In a subpackage (`services/`, `adapters/`) import the module's own files absolutely, `from modules.<id> import
  store`, not `from .. import store` (`tests/test_interfaces.py` reads that as a foreign module).
- Examples in the code base: C2-M3 for the layers, C3-M2 for dataclasses and `errors.py`, C4-M2 for adapters.

## Quality gate

`uv run python tools/quality/gate.py` checks every rule above, plus ruff and mypy, the same way for people and every
coding agent. Existing findings are frozen in `tools/quality/baseline.json`; the gate fails when a count goes up.

- **Coding agents:** after every change run `uv run python tools/quality/gate.py --changed` and fix every finding
  before you finish. Never raise a number in `baseline.json`, never commit with `--no-verify`.
- **After a cleanup:** `uv run python tools/quality/gate.py --update-baseline` lowers the numbers; commit the file.
- It also runs before each commit (`uvx pre-commit install`, once per clone), after each file edit of Claude Code
  (`.claude/settings.json`) and in CI (`.github/workflows/quality.yml`), where it cannot be skipped.

## Definition of done

1. Your module tests pass: `uv run pytest -q tests/test_<id>_*.py`.
2. All tests pass: `uv run pytest -q`.
3. `uv run python demo.py` ends with exit code 0.
4. Open questions are in `modules/<id>/OPEN-QUESTIONS.md`.
5. `uv run python tools/quality/gate.py` passes (no new findings).
6. A pull request from the team branch `team/<n>` of the team's fork (`<fork-owner>/dataspace-mgm-services`) to `main`
   of `eclipse-tractusx/dataspace-mgm-services`, opened in the merge window at 14:45. A Tractus-X committer merges it.

## Commits

- The code is meant for Eclipse Tractus-X. The Eclipse Foundation requires a signed Eclipse
  Contributor Agreement (ECA) for the email address in the `Author` field of each commit. The ECA
  fulfils the sign-off of the Developer Certificate of Origin; Eclipse does not require a separate
  `Signed-off-by` line.
- The Eclipse Project Handbook asks contributors to disclose AI assistance. For AI-assisted
  commits, add the trailer `Assisted-by: <tool> (<model>)`, for example
  `Assisted-by: GitHub Copilot (GPT-4o-2024-08-06)`.
- A person reviews every AI-generated change before it is committed.
- Every new file starts with the license header of `CONTRIBUTING.md` ("License headers", TRG 7.02):
  the `#` banner with `Copyright (c) 2026 Contributors to the Eclipse Foundation` and the Apache-2.0
  notice. Written with AI help: keep the paragraph "AI Disclosure", `SPDX-License-Identifier:
  Apache-2.0 AND CC0-1.0` and `Assisted-By: <tool> (<model>)`, e.g. `Assisted-By: Claude Code
  (claude-opus-5-5)`. Written without AI help: leave out the AI disclosure and the `Assisted-By` line,
  and write `SPDX-License-Identifier: Apache-2.0`. Copy the header of an existing file.

## How to run

```bash
git clone https://github.com/tx-arena-events/portal-backend-spec.git spec   # once; update: git -C spec pull --ff-only
uv sync                       # behind a TLS proxy: UV_SYSTEM_CERTS=1 uv sync (older uv: UV_NATIVE_TLS=1)
uv run pytest -q              # all tests
docker compose up -d          # once: Keycloak, the test Portal IAM of C2-M5 (iam/README.md)
uv run python demo.py         # CSP stand-in, OSP A and OSP B, scenarios 1 to 4; exit code 0 = green
uv run python demo.py --serve # keep the processes running (OSP A :8000, OSP B :8001, Swagger at /docs)
```

A token of a test person: `uv run python iam/test/get-token.py erika`. The Portal IAM is Keycloak: teams of
C2-M2 and C2-M3 call its Admin API with the service accounts `svc-c2-m2` and `svc-c2-m3`.

## Skills

The skills live once, in `.agents/skills/<name>/SKILL.md` (with tested scripts in `scripts/`). GitHub Copilot, OpenAI
Codex, OpenCode, Cursor and Gemini CLI load them from there, Claude Code through the link `.claude/skills`. Any other
agent can use them too: "read `.agents/skills/<name>/SKILL.md` and follow it". Use the matching skill instead of
improvising, and finish every skill that changes code only when the quality gate passes.

| Skill | Use when |
|---|---|
| `implement-module-from-spec` | you build or extend a module from its spec |
| `review-module` | you check a module before a pull request, or review one |
| `merge-guard` | you check a branch before its pull request: paths, license headers, commits, secrets, the gate |
| `module-map` | you want to know which modules are stand-ins, what a folder answers itself, call-convention findings |
| `portal-spec-sources` | you look up a path, permission, step, query, event or section of the spec |
| `flow-trace` | you follow a Process Orchestration flow: which step runs next, why a process waits |
| `portal-token-inspect` | you explain a 401, 403 or 404 from a person's token |
| `contract-seam` | you check what the UI expects against what the backend spec defines |
| `dependencies-and-dash` | you add a dependency or the Eclipse Dash check fails |

The catalog with details is `.agents/skills/README.md`. Agents: the Dataspace Captain lives once in
`.agents/agents/dataspace-captain/`; `tools/agents/build.py` writes its Claude Code and GitHub Copilot files (do not
edit those by hand; the gate checks them).
