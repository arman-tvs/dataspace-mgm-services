<!--
 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.

 AI Disclosure: This file was entirely AI-generated.
 The AI-generated portions are made available under CC0-1.0 and not subject
 to the project's license. The human contributor has reviewed and verified
 that the code is correct.

 SPDX-License-Identifier: Apache-2.0 AND CC0-1.0
 Assisted-By: GitHub Copilot
-->

# C2-M2 REST API definitions

This package defines the HTTP contract and endpoints, not their implementation.
Both contracts use OpenAPI 3.1 and the base URL `/api/c2-m2`.

| Contract | Consumers | Operations |
|---|---|---|
| [openapi.yaml](openapi.yaml) | UI and public API clients authenticated with Portal IAM | 22 company, invitation and OSP staff operations |
| [openapi-private.yaml](openapi-private.yaml) | Other modules and Process Orchestration | 4 internal queries and 10 steps; also the CloudEvent schemas |

**Public does not mean anonymous.** Every operation requires a Portal IAM bearer
token and the declared `x-permission` and `x-permission-scope`. Company operations
hide other companies with 404; accepting an invitation acts on the caller's `sub`.
OSP staff operations are public-facing APIs, but require staff permissions.

Private routes remain available under `/internal/...` and `/steps/...` with
`query_c2_m2` and `execute_steps_c2_m2`. The installation's generated OpenAPI/Swagger
continues to document the complete module API, as required by the scaffold.
For a public-only HTTP surface, mount `public_router` rather than the combined
module `router`; its generated OpenAPI contains no queries or steps.
This is a contract and permission boundary, not a network firewall: deployment
ingress must also restrict private paths if required.
In-process consumers continue using [interface.py](../interface.py), without tokens.

## Layers

```
c2_m2_rs_api/                      definitions only, no implementation imports
  openapi.yaml, openapi-private.yaml   the contracts
  endpoint.py                      api (@api.get/post/put/delete), RestApi base, Annotated parameter types
  apis/<use case>_api.py           one abstract interface per use case (12)
  router.py                        create_router(implementations, public=...) -> APIRouter
  contract.py                      load_contract(), operations(), resolve()
  c2_m2_route.py, exception_translator.py   errors as Problem Details (400, not 422)
c2_m2_rs_service/
  producer/impl/<use case>_api_impl.py      one implementation per interface
  routers.py                       binds interfaces to implementations: public_router, private_router, router
  main.py                          standalone service (create_app)
```

| Interface | API | Operations | README |
|---|---|---|---|
| `CompanyUsersApi` | public | list, get, set portal roles, remove | 7.1 to 7.4 |
| `CompanyAppRolesApi` | public | app roles of an app, set app roles of a person | 7.5, 7.6 |
| `CompanyInvitationsApi` | public | list, create, revoke | 7.7 to 7.9 |
| `InvitationAcceptanceApi` | public | accept | 7.10 |
| `OspUsersApi` | public | list, get account, set portal roles, remove | 7.11 to 7.14 |
| `OspCompanyInvitationsApi` | public | list, create, revoke for any company | 7.20 to 7.22 |
| `OspStaffApi` | public | list staff, set staff roles | 7.15, 7.16 |
| `OspStaffInvitationsApi` | public | list, create, revoke | 7.17 to 7.19 |
| `AppClientQueriesApi` | private | app roles, instance clients | 9.1 to 9.3 |
| `CompanyUserQueriesApi` | private | people of a company | 9.4 |
| `AppClientStepsApi` | private | the 7 app client steps | 8.1 to 8.7 |
| `CompanyUserStepsApi` | private | the 3 company user steps | 8.8 to 8.10 |

An interface method declares only where it is exposed and its parameters:

```python
class CompanyUsersApi(RestApi):
    @api.get("/companies/{companyId}/users")
    @abstractmethod
    def list_company_users(self, claims: Claims, company_id: CompanyId, page: PageNumber = 0,
                           size: PageSize = 20, status: StatusFilter = None) -> Page[CompanyUser]: ...
```

and the implementation overrides it with plain types and the same plain defaults:

```python
class CompanyUsersApiImpl(CompanyUsersApi):
    def list_company_users(self, claims: dict, company_id: str, page: int = 0, size: int = 20,
                           status: list[str] | None = None) -> Page[CompanyUser]:
        ...
```

The FastAPI metadata lives in the `Annotated` types of [endpoint.py](endpoint.py) (`Claims`,
`CompanyId`, `PageNumber`, `JsonBody`, ...), never in the defaults; that keeps the override
type-correct. Python names are snake_case, and `alias` keeps the contract's names on the wire
(`company_id` is `{companyId}`). `claims` comes first, so required parameters precede optional ones.

`api` reads like a FastAPI router, but `@api.get(...)` only records the method and path;
it registers nothing. `create_router` takes operationId, summary, tags, permission, scope and the
request/response schemas from the contract, and replaces the `Claims` marker with the
token and permission check of `x-permission`; an endpoint without a `Claims` parameter is
rejected. The implementation gets the claims
and does the rest (scope `company`, then the service call). The interface signature
is what FastAPI sees, so the implementation needs no FastAPI types.

`create_router` fails at start-up when an interface has no implementation or two,
when an implementation does not accept the interface's parameters, or when an
endpoint and the contract disagree. A new operation therefore needs three changes:
the contract (via `sync_openapi`), a method on an interface, and its implementation.

## Running the module on its own

```bash
SETTINGS_FILE=config/osp-a/installation.json BASE_URL=http://localhost:8202 \
DATABASE_URL=postgresql://... IAM_URL=http://localhost:8080/auth IAM_REALM=CX-Central \
  uv run uvicorn --factory modules.c2_m2.c2_m2_rs_service.main:create_app --port 8202
```

It serves both APIs under `/api/c2-m2`, `/health` and Swagger at `/docs`. Neighbours
come from `C3_M1_URL`, `C10_M1_URL` or `MODULE_URLS`; without an address C2-M2 uses
its built-in stand-ins (README 11.2). Without `IAM_URL` (and `TEST_TOOLS` not
`false`) it mounts the scaffold's in-memory test IAM at `/auth`, as the installation
does. Events stay inside the service for now (`OPEN-QUESTIONS.md` 11).
Inside the installation nothing changes: the scaffold mounts [router.py](../router.py).

The YAML files are the distributable API definitions. Generated Swagger uses
interface signatures for path/query parameters and the YAML for body/response
schemas. No schema-only route is added to the business API.

## Updating the contracts

The binding source is [C2-M2-AppAccess/openapi.yaml](../../../spec/C2-M2-AppAccess/openapi.yaml).
Do not edit the split YAML files independently. From the repository root:

```bash
uv run python -m modules.c2_m2.c2_m2_rs_api.sync_openapi
uv run python -m modules.c2_m2.c2_m2_rs_api.sync_openapi --check
uv run pytest -q tests/c2_m2/
```

The generator retains each operation unchanged, copies its transitive component
references and excludes private step/event schemas from the public contract.
The tests check separation, source parity, resolvable references, handler coverage,
public Swagger and authentication on both API surfaces.

The current PostgreSQL implementation requires `DATABASE_URL`. Its SQLAlchemy,
pg8000 and Alembic dependencies are not yet in the shared dependency manifests;
until that separate work is merged, validation can supply them temporarily:

```bash
uv run --with sqlalchemy --with pg8000 --with alembic pytest -q tests/test_c2_m2_rs_api.py
```

Use a dedicated test database. The current module `reset()` does not truncate
PostgreSQL tables, so the older acceptance fixtures do not isolate database state
between cases. A combined acceptance run is not yet green on this backend.
