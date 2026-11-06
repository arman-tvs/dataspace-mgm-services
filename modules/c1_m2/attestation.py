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
"""The verification attestation of C1-M2 (README 6.4): the ten checks in their order, the keys of the
recognised issuer, and the repeated signature check of the queries (9.1). The JWT is never logged."""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time
import unicodedata
from pathlib import Path

import httpx
import jwt

from portal_common import http
from portal_common.problems import Problem

from . import catalog

MODULE = "c1-m2"
TYP = "ebw-attestation+jwt"
DURATION = re.compile(r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")
_VERIFY_SIGNATURE_ONLY = {"verify_signature": True, "verify_exp": False, "verify_nbf": False, "verify_iat": False,
                          "verify_aud": False, "verify_iss": False, "verify_sub": False, "verify_jti": False}

_jwks_lock = threading.Lock()
_jwks: tuple[list[dict], float] | None = None


def now() -> float:
    """Current time; tests shift it (acceptance case 11)."""
    return time.time()


def reset() -> None:
    global _jwks
    with _jwks_lock:
        _jwks = None


def duration_seconds(value: str) -> int:
    """ISO 8601 duration in seconds; raises ValueError for anything else."""
    m = DURATION.match(value or "")
    if not m or not any(m.groups()):
        raise ValueError(f"ATTESTATION_MAX_AGE: not an ISO 8601 duration: {value!r}")
    weeks, days, hours, minutes, seconds = (int(g or 0) for g in m.groups())
    return weeks * 604800 + days * 86400 + hours * 3600 + minutes * 60 + seconds


def config() -> dict:
    """Variables of README 4; an unset value takes the column "Example" (FRAMEWORK 4.8)."""
    return {"issuer": os.environ.get("ATTESTATION_ISSUER", ""),
            "audience": os.environ.get("ATTESTATION_AUDIENCE") or "portal-registration",
            "algorithms": [a.strip() for a in (os.environ.get("ATTESTATION_ALGORITHMS") or "ES256").split(",") if a.strip()],
            "clients": [c.strip() for c in os.environ.get("ATTESTATION_CLIENT_IDS", "").split(",") if c.strip()],
            "maxAge": duration_seconds(os.environ.get("ATTESTATION_MAX_AGE") or "P30D"),
            "skew": int(os.environ.get("ATTESTATION_CLOCK_SKEW_SECONDS") or 60),
            "cacheSeconds": int(os.environ.get("ATTESTATION_JWKS_CACHE_SECONDS") or 300)}


def _fetch_keys() -> list[dict]:
    path = os.environ.get("ATTESTATION_JWKS_FILE")
    if path:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("keys", [])
    cfg = config()
    url = os.environ.get("ATTESTATION_JWKS_URL") or f"{cfg['issuer'].rstrip('/')}/jwks"
    try:
        r = http.request("GET", url, timeout=5)
        if not r.is_success:
            raise Problem(MODULE, 502, "upstream-error", detail=f"JWKS of the issuer answered {r.status_code}", retryable=True)
        return r.json().get("keys", [])
    except (httpx.HTTPError, ValueError) as e:
        raise Problem(MODULE, 502, "upstream-error", detail=f"JWKS of the issuer: {type(e).__name__}", retryable=True) from e


def _key(kid: str | None) -> dict | None:
    """Key for `kid` from the configuration only; a `kid` missing in the cache triggers one reload."""
    global _jwks
    cache_seconds = config()["cacheSeconds"]
    with _jwks_lock:
        cached = _jwks
    keys = cached[0] if cached and time.monotonic() - cached[1] < cache_seconds and not os.environ.get("ATTESTATION_JWKS_FILE") else None
    found = next((k for k in keys or [] if k.get("kid") == kid), None)
    if found is None:
        keys = _fetch_keys()
        with _jwks_lock:
            _jwks = (keys, time.monotonic())
        found = next((k for k in keys if k.get("kid") == kid), None)
    return found


def _invalid(reason: str) -> Problem:
    return Problem(MODULE, 400, "attestation-invalid", reason=reason)


def _signed_payload(token: str, cfg: dict) -> tuple[dict, dict]:
    """Steps 1 to 4 of 6.4; returns header and payload. Used by the checks and by `signature_check`."""
    try:
        header = jwt.get_unverified_header(token)
        payload = jwt.decode(token, options={"verify_signature": False})
    except (jwt.PyJWTError, ValueError, TypeError) as e:
        raise _invalid("format") from e
    if not cfg["issuer"]:   # an address of another system: the installation must set it (FRAMEWORK 4.8)
        raise Problem(MODULE, 502, "upstream-error", detail="ATTESTATION_ISSUER is not set", retryable=False)
    alg = header.get("alg")
    if not isinstance(alg, str) or alg.lower() == "none" or alg not in cfg["algorithms"] or header.get("typ") != TYP:
        raise _invalid("algorithm")
    if payload.get("iss") != cfg["issuer"]:
        raise _invalid("issuer")
    jwk = _key(header.get("kid"))
    if jwk is None:
        raise _invalid("signature")
    try:
        jwt.decode(token, jwt.PyJWK(jwk).key, algorithms=[alg], options=_VERIFY_SIGNATURE_ONLY)
    except (jwt.PyJWTError, ValueError, TypeError) as e:
        raise _invalid("signature") from e
    return header, payload


def _names_equal(a: object, b: object) -> bool:
    """Normalisation of C5-M1 6.5: Unicode NFC, leading and trailing spaces removed, case ignored."""
    return (unicodedata.normalize("NFC", str(a)).strip().casefold()
            == unicodedata.normalize("NFC", str(b)).strip().casefold())


def _text(value: object, maximum: int = 500) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= maximum


def _optional_text(value: object) -> bool:
    return value is None or isinstance(value, str)


def _evidence_valid(evidence: object) -> bool:
    return isinstance(evidence, list) and all(
        isinstance(e, dict) and all(_text(e.get(k)) for k in ("type", "vct", "issuer", "wallet"))
        and isinstance(e.get("status_checked"), bool) for e in evidence)


def _address_valid(address: object) -> bool:
    return address is None or (isinstance(address, dict) and all(
        _optional_text(address.get(k)) for k in ("street_address", "postal_code", "locality", "country")))


def _representation_valid(rep: dict) -> bool:
    return (isinstance(rep.get("confirmed"), bool) and isinstance(rep.get("reasons") or [], list)
            and all(_optional_text(rep.get(k)) for k in ("result", "type", "role", "valid_until", "issuer", "trust")))


def _claims_valid(p: dict) -> bool:
    person, company, rep = p.get("person"), p.get("company"), p.get("representation")
    if not (isinstance(person, dict) and isinstance(company, dict) and isinstance(rep, dict)):
        return False
    if not (_optional_text(company.get("euid")) and _address_valid(company.get("address"))):
        return False
    numbers = isinstance(p.get("verified_at"), (int, float)) and not isinstance(p.get("verified_at"), bool)
    return (numbers and _text(p.get("jti"), 200) and _text(p.get("client_id")) and _text(person.get("given_name"))
            and _text(person.get("family_name")) and _text(company.get("legal_name")) and _text(company.get("ebwoid"))
            and p.get("sub") == company.get("ebwoid") and _representation_valid(rep)
            and _evidence_valid(p.get("evidence")) and catalog.country(company.get("country")) is not None)


def verify(token: str, claims: dict) -> tuple[dict, dict]:
    """The checks of 6.4 in their order; the first failure decides `reason`. Returns header and payload."""
    cfg = config()
    header, p = _signed_payload(token, cfg)
    aud = p.get("aud")
    if cfg["audience"] not in (aud if isinstance(aud, list) else [aud]):
        raise _invalid("audience")
    exp, iat = p.get("exp"), p.get("iat")
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (exp, iat)):
        raise _invalid("claims")
    if exp <= now() - cfg["skew"]:
        raise _invalid("expired")
    if iat > now() + cfg["skew"]:
        raise _invalid("not-yet-valid")
    if p.get("attestation_version") != "0.2":
        raise _invalid("version")
    if p.get("purpose") != "onboarding":
        raise _invalid("purpose")
    if not _claims_valid(p):
        raise _invalid("claims")
    if cfg["clients"] and p.get("client_id") not in cfg["clients"]:
        raise _invalid("client")
    person = p["person"]
    if not claims.get("given_name") or not claims.get("family_name") \
            or not _names_equal(person["given_name"], claims["given_name"]) \
            or not _names_equal(person["family_name"], claims["family_name"]):
        raise _invalid("person")
    return header, p


def usable_at_submission(a: dict) -> bool:
    """6.4 "At submission": not expired and not older than `ATTESTATION_MAX_AGE` from `iat`."""
    cfg, claims = config(), a["_attestationClaims"]
    return claims["exp"] > now() - cfg["skew"] and now() - claims["iat"] <= cfg["maxAge"] + cfg["skew"]


def signature_check(token: str) -> dict:
    """9.1: steps 1 to 4 again, without time check. `VALID`, `INVALID` or `UNAVAILABLE`."""
    checked = dt.datetime.fromtimestamp(now(), dt.UTC).isoformat()
    try:
        _signed_payload(token, config())
    except Problem as p:
        return {"result": "UNAVAILABLE" if p.status == 502 else "INVALID", "checkedAt": checked}
    return {"result": "VALID", "checkedAt": checked}


def _ts(epoch: float | None) -> str | None:
    return dt.datetime.fromtimestamp(epoch, dt.UTC).isoformat() if epoch else None


def summary(header: dict, p: dict) -> dict:
    """`AttestationDetail` without `signatureCheck`, which is added at every query."""
    rep, company = p["representation"], p["company"]
    addr = company.get("address") or None
    return {"attestationId": p["jti"], "issuer": p["iss"], "issuedAt": _ts(p["iat"]), "expiresAt": _ts(p["exp"]),
            "verifiedAt": _ts(p["verified_at"]),
            "person": {"givenName": p["person"]["given_name"], "familyName": p["person"]["family_name"]},
            "representation": {"confirmed": rep["confirmed"], "result": rep.get("result"), "type": rep.get("type"),
                               "role": rep.get("role"), "validUntil": rep.get("valid_until"), "issuer": rep.get("issuer"),
                               "trust": rep.get("trust"), "reasons": list(rep.get("reasons") or [])},
            "keyId": header.get("kid"), "clientId": p["client_id"],
            "company": {"legalName": company["legal_name"], "ebwoid": company["ebwoid"], "euid": company.get("euid"),
                        "countryCode": company["country"],
                        "address": addr and {"streetAddress": addr.get("street_address"), "postalCode": addr.get("postal_code"),
                                             "locality": addr.get("locality"), "country": addr.get("country")}},
            "evidence": [{"type": e.get("type"), "vct": e.get("vct"), "issuer": e.get("issuer"), "wallet": e.get("wallet"),
                          "statusChecked": e.get("status_checked")} for e in p["evidence"]]}
