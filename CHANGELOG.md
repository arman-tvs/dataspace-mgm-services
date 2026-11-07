# Changelog

All notable changes to this project will be documented in this file.
See also the overarching [Eclipse Tractus-X changelog](https://eclipse-tractusx.github.io/changelog) for the Tractus-X releases.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository set-up according to the [Tractus-X Release Guidelines](https://eclipse-tractusx.github.io/docs/release): legal documentation, `.tractusx` metadata file, contribution templates, Dependabot and security scans (CodeQL, KICS, Trivy, TruffleHog), container build and documentation structure ([dataspace-mgm-ui#1](https://github.com/eclipse-tractusx/dataspace-mgm-ui/issues/1))
- Eclipse Dash IP check aligned with tractusx-testlab: `dependencies.yml` only checks, the new `dependencies-update.yml` regenerates `DEPENDENCIES` daily, requests IP reviews (secret `DASH_GITLAB_API_TOKEN`) and opens a pull request.
- Hackathon scaffold: all modules of the spec mounted as stand-ins, Process Orchestration (C12-M1), test Portal IAM (Keycloak), EBW stack for tests with a real wallet, `demo.py` and the setup check `check.py`.
- Event inbox `POST /api/v1/events/inbox` (FRAMEWORK 6, OP-54): receives the CloudEvents of split-out modules in structured or binary content mode, with the token of the service account of the publishing module, and delivers each `source` and `id` once. First controller of the new `controllers/` package: one folder per API category and version, as in the Industry Core Hub backend.
- Quality gate `tools/quality/gate.py`, the same for people and coding agents: ruff and mypy (`[tool.ruff]`, `[tool.mypy]` in `pyproject.toml`), at most 500 lines per file and 60 per function, the layers inside a module, `module-map`. Existing findings are frozen per area in `tools/quality/baseline.json` and may only go down. It runs in CI (`.github/workflows/quality.yml`, together with `pytest` and `demo.py --small-iam`), before each commit (`.pre-commit-config.yaml`) and after each file edit of Claude Code (`.claude/settings.json`).

### Changed

- Events are CloudEvents 1.0 (`specversion`, `id`, `source` `urn:<module>`, `type`, `time`, `datacontenttype`, `data`) as proposed in the spec (FRAMEWORK 6, OP-54): `events.publish(module, type, data)`; the flat form `events.publish({"eventType": ...})` is deprecated; consumers read the content from `event["data"]`.

### Fixed

- Align the Docker build and runtime images with the project's required Python 3.12 version.

[Unreleased]: https://github.com/eclipse-tractusx/dataspace-mgm-service/commits/main
