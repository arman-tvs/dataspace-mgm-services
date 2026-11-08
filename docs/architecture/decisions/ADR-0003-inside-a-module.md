# ADR-0003: Inside a module: layers, data, building blocks and limits, enforced by one gate

**Status:** proposed (7 Nov 2026).

## Context

The spec (FRAMEWORK 1-4) and `AGENTS.md` define the **outside** of a module: its contract in `openapi.yaml`, its own
database, events through an outbox, neighbours only through their interface, the call convention of `interface.py`.
Nothing defined the **inside**. After the hackathon the 13 module folders have four different layouts, from all logic
in `interface.py` (C3-M1: 1281 lines, 72 `Problem(...)` built by hand) to a layered module (C2-M3), and plain
`dict`s carry most of the data (C3-M1 83, C4-M2 80 functions return `dict`), so mypy cannot see wrong field names,
the main reason merges break.

Most code is written with coding agents (Claude Code, Copilot, Codex, others). Agents follow written rules closely and
improvise where there are none; like people, they keep a rule reliably only when a check fails. So the conventions
below are written down here and enforced by one gate that runs the same way for every author.

## Decision

### 1. Layers, imports point down only

```
modules/<id>/
  router.py     HTTP only: token, permission, scope, then interface      (AGENTS.md call convention 5)
  schemas.py    Pydantic request and response models of openapi.yaml
  interface.py  facade: the steps and queries of the spec, dict in / dict out, delegates to the service
  service.py    rules, preconditions, idempotency (FRAMEWORK 4.4); a services/ package when it grows
  store.py      Repository: a Protocol with an in-memory and a PostgreSQL implementation
  gateways.py   one typed function per neighbour operation (README section 11)
  adapters/     external systems that are not modules, each behind a Protocol
  errors.py     one factory per error type of README section 12
  config.py     the variables of README section 4, read at call time
```

| Layer | May not import |
|---|---|
| router | service, store, gateways, adapters |
| schemas | router, interface, service, store, gateways, adapters |
| interface | router, store, gateways, adapters |
| service | router, interface |
| store, gateways, adapters | router, interface, service, and each other |
| errors | any other layer |

Service, store, gateways and errors do not import `fastapi`, `pydantic` or `starlette`: HTTP stays at the edge.
In `interface.py`, every step and query is a one-line `def` that calls the service (`def register_company(input:
dict) -> dict: return registration.register_company(input)`), not a re-export (`from .service import ...`):
`module-map` counts only functions defined with `def`, and the signatures of the call convention stay visible.
Inside a subpackage (`services/`, `adapters/`), import the module's own files absolutely
(`from modules.<id> import errors, store`), not with `from .. import`: `tests/test_interfaces.py` reads a two-dot
import as a foreign module. One dot within the same subpackage (`from .common import ...`) is fine.
Protocols ("ports") are used only where something is really exchanged: the store (memory and PostgreSQL) and external
systems (Keycloak, wallet providers, the CSP). Neighbour modules and events need no own port, because
`portal_common.neighbours` and `portal_common.events` already hide in-process, HTTP and stand-in (FRAMEWORK 4.7).

### 2. Data

| Where | Type |
|---|---|
| `schemas.py` (HTTP) | Pydantic models, camelCase as in `openapi.yaml` |
| `interface.py` | `dict` in and out (call convention) |
| service, store | dataclasses (`@dataclass(slots=True)`, `frozen=True` for values), `StrEnum` or `Literal` for status values, snake_case |
| gateways | map the neighbour's `dict` to a dataclass (or a `TypedDict` for read-only data) |

camelCase names of the spec appear only at the edges (schemas, interface, gateways). Modules that pass `dict`s today
may move in two steps: `dict` -> `TypedDict` (mypy checks the keys, no runtime change) -> dataclass.

**Types: parse at the edge, precise types inside.** Unknown data becomes typed data once, where it enters the module,
and every function after that has precise types:

| Place | Type of a parameter or return value |
|---|---|
| `schemas.py` | Pydantic models from `openapi.yaml`: unknown JSON becomes typed data here |
| `interface.py` | `dict` in and out (call convention), checked once at the start of each step |
| `gateways.py`, `adapters/` | the answer of a neighbour or external system becomes a dataclass or `TypedDict` here |
| service, store, validation, errors | precise types only: `str`, `int`, dataclasses, `TypedDict`s, `Literal` / `StrEnum`; an extra field of a `Problem` is a named parameter, not `**ext` |
| `object` | only for a function whose job is to check unknown input (`def required(input: dict[str, object], field: str) -> str`); the check narrows it right there |
| `Any` | never in a function signature (ruff `ANN401` in the gate): it switches type checking off |

### 3. Building blocks

**Repository with a Protocol** (`store.py`, as C2-M3 `repository.py`, C4-M2 `store.py`): chosen in `reset()`,
returns dataclasses. The event of a change is written in the same transaction as the change (README section 4:
"stored in the same transaction as the change"), as C2-M3 does with `transaction()` and `add_event()`.

```python
class CompanyStore(Protocol):
    def get(self, company_id: str) -> Company | None: ...
    def add(self, company: Company) -> None: ...
    def transaction(self) -> AbstractContextManager[None]: ...
    def add_event(self, event_type: str, data: dict) -> None: ...
```

**Gateway per neighbour** (`gateways.py`, as C2-M3): the only file that imports `portal_common.neighbours`; handles
the built-in stand-in and maps the answer.

```python
def application(application_id: str) -> Application:
    """C1-M2 `getApplicationInternal` (README 11.1)."""
    found = neighbours.query(MODULE, "c1-m2", "get_application_internal", applicationId=application_id)
    return Application.from_spec(found)
```

**Error factories** (`errors.py`, as C3-M2): one function per row of README section 12; the only file that builds
`Problem(...)`; `retryable` is decided once.

```python
def invalid_state(detail: str) -> Problem:
    """409: a precondition of a step is missing."""
    return Problem(MODULE, 409, "invalid-state", detail=detail, retryable=False)
```

**Adapter per external system** (`adapters/`, as C2-M3 `iam/port.py`, C4-M2 providers, C3-M2 `csp_client.py`): a
Protocol and one class per implementation (the real one and an in-memory or stand-in one), chosen by the
configuration of README section 4 in `reset()`, never by `if provider == ...`.

### 4. Limits (balanced)

At most 500 lines per file, 60 lines and a complexity of 10 per function; type hints on every function (mypy); ruff
rules `E, F, W, I, B, UP, C90, SIM` and `ANN401` with a line length of 120.

### 5. Cases found while testing on five modules

The rules above were tested by refactoring C3-M2, C3-M1, C2-M3, C4-M2 and C1-M2 (branches in a fork, no behaviour
change). These cases came up; they are part of the decision:

| Case | Rule |
|---|---|
| A webhook of an external system (C4-M2 SAP DIV callbacks) | It is a route: in `router.py`, calling `interface` or the service. The adapter may parse the external format, but does not own a FastAPI router. |
| A built-in stand-in that calls back into the module (C4-M2) | The adapter may not import the service. The service registers its callbacks in the adapter (a small `Callbacks` dataclass passed to `register_callbacks(...)` in `reset()` or at import): a callback port. |
| A module with only an in-memory store (C1-M2) | `store.py` holds the module's data as plain module state until a second implementation exists; a `Protocol` with one implementation is ceremony. It is still the only file that holds data. |
| Validating a token or document of an external system (C1-M2, C3-M1 `attestation.py`; C4-M2 `did.py`) | An adapter: it talks to an external system (JWKS, DID resolution). Put it in `adapters/`. |
| Selecting one of several adapters by configuration (C4-M2 `providers.py`) | The registry lives in `adapters/__init__.py` (`get(name)`, `enabled()`), not in a separate top-level file. |
| `service.py` and `services/` side by side (C4-M2) | One of them: a module that outgrows `service.py` moves it into `services/`. Tests that patch `service.x` move with it. |
| A file whose name has no layer (`calls.py`, `crypto.py`, `iam/`) | Rename it to its layer (`gateways.py`, `adapters/crypto.py`, `adapters/iam/`) so the layer rules apply. The gate does not flag files without a layer yet. |
| Parameters a function accepts and ignores (C2-M3 queries; the call convention passes every openapi parameter) | `**_other: object` is fine: `object` for "accepted, not used". |
| A FastAPI dependency helper (C2-M3 `dependencies.perm`, FastAPI types `Depends()` as `Any`) | Type it with what the handler receives (for example `-> dict` for the claims) and say so in the docstring; no `# noqa`. |
| `Any` inside a type (`dict[str, Any]`, `Callable[..., Any]`) | Counts as `Any`: inside a module use `dict[str, object]`, a `TypedDict` or a dataclass. `ANN401` only catches a bare `Any`; review checks the rest. |
| A local list of field errors called `errors` (C3-M1, C1-M2) | Call it `invalid`: `errors` is the module of error factories. Shared helpers get names that do not collide with common locals (`now_iso`, `paged`, not `now`, `page`). |
| Tests that reach into internals (`service.now`, `interface.store`, `find_spec("...accounts")`) | Tests use `interface.py`, the router, the store's functions and the patch points the module documents; then a refactor changes no test. A moved string (C4-M2 audit operation names) needs a test that pins it. |
| Line length in existing code of another team (C1-M2) | Wrap by hand only the lines a change touches; a repository-wide `ruff format` commit is a separate decision (issue). |

### 6. Enforcement: one gate for everyone

`tools/quality/gate.py` checks ruff, mypy, the limits, the layers (`layers`, `neighbours`, `problems`) and
`module-map` per area. Existing findings are frozen in `tools/quality/baseline.json`; the gate fails when a count goes
up, and `--update-baseline` only lowers. It runs:

| Where | Covers |
|---|---|
| CI (`.github/workflows/quality.yml`), required status check | everyone; cannot be skipped |
| pre-commit (`.pre-commit-config.yaml`) | everyone who commits |
| `AGENTS.md` and the skills: "finish only when the gate passes" | every agent that reads `AGENTS.md` |
| Claude Code hook (`.claude/settings.json`) | Claude Code, after each file edit; other tools get a one-line wrapper |

## Alternatives

| Option | Why not |
|---|---|
| Hexagonal for everything (ports for store, neighbours, events, external systems) | Wraps `portal_common` again in every module; more files per spec change; little gain over the ports kept above. |
| Facade + service only | `service.py` becomes the next 1000-line file; data access and neighbour calls stay mixed with the rules. |
| Only limits, no layout | Layouts keep diverging (four styles in 13 modules today). |
| Pydantic everywhere | Validates again inside, ties the rules to Pydantic, slower for in-memory stores. |
| Strict limits (300 lines, complexity 8, mypy --strict, naming rules) | About three times the backlog; the naming rules conflict with the call convention (`applicationId=` parameters). |
| Fix all modules before enforcing | Blocks the gate for weeks; the ratchet locks in each step instead. |

## Consequences

- No spec change: the spec defines the outside of a module only; the call convention is unchanged.
- Existing modules keep working; they improve module by module, each step lowers the baseline. C2-M3 is the closest
  to the layout; C3-M2 to the data and error conventions.
- `develop` must be green before the gate becomes a required check (2 failing tests, `demo.py` stops in C2-M2).
- Moving to full hexagonal later stays possible: layers that only import downward can be turned into ports.
- Tested before the decision on five modules, all with unchanged module tests, full suite and `demo.py`: C3-M2
  6 -> 0, C2-M3 76 -> 0, C4-M2 69 -> 0, C1-M2 130 -> 24, C3-M1 174 -> 47 findings; what is left is mainly router return
  types, which need Pydantic response models in `schemas.py`.

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2026 Contributors to the Eclipse Foundation
- Source URL: https://github.com/eclipse-tractusx/dataspace-mgm-services/blob/main/docs/architecture/decisions/ADR-0003-inside-a-module.md
