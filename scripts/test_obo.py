#!/usr/bin/env python3
"""End-to-end test: OIDC password grant -> OBO token exchange -> MCP calls

This is a direct Python translation of `scripts/test_obo.ps1`.
It performs:
- OIDC discovery
- Password grant to get a user token
- Token Exchange (OBO) with audience fallbacks
- Probing MCP `/mcp` endpoint with different content-types
- initialize -> tools/list (and alternative method names) using mcp-session-id
- Negative tests (no-auth)

Run: python scripts/test_obo.py
"""

from __future__ import annotations
import base64
import json
import logging
import sys
from typing import Any, Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format="[%(asctime)s][%(levelname)s] %(message)s")
log = logging.getLogger("test_obo")

# Configuration (keep in sync with the PowerShell script)
REALM = "BridgeMCP"
KEYCLOAK_BASE = "http://localhost:8080"
WELL_KNOWN = f"{KEYCLOAK_BASE}/realms/{REALM}/.well-known/openid-configuration"
TOKEN_URL = f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/token"

USER_CLIENT = "mcp-web-client"
USERNAME = "testuser@test.com"
PASSWORD = "testpass123"

GATEWAY_CLIENT = "mcp-gateway"
GATEWAY_SECRET = "7Hh8stp6hZsA61B6Jdd7HM1KzxMKw4qn"

AUDIENCE = "fin-mcp-server"
ALTERNATIVE_AUDIENCES = ["fin-assistant-mcp", "mcp-gateway", "account"]
FIN_ASSISTANT_URL = "http://localhost:3000"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "test-obo/1.0"})

# Helpers

def decode_jwt_payload(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        # base64 padding
        padding = len(payload) % 4
        if padding == 2:
            payload += "=="
        elif padding == 3:
            payload += "="
        payload = payload.replace("-", "+").replace("_", "/")
        data = base64.b64decode(payload)
        return json.loads(data)
    except Exception as e:
        log.warning("Failed to decode JWT payload: %s", e)
        return None


def fetch_oidc_config() -> Optional[Dict[str, Any]]:
    try:
        log.info("Fetching OIDC config from %s", WELL_KNOWN)
        r = SESSION.get(WELL_KNOWN, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.error("Failed to fetch OIDC config: %s", e)
        return None


def token_password() -> str:
    body = {
        "grant_type": "password",
        "client_id": USER_CLIENT,
        "username": USERNAME,
        "password": PASSWORD,
        "scope": "openid profile",
    }
    log.info("Requesting user token via password grant")
    r = SESSION.post(TOKEN_URL, data=body, timeout=10)
    r.raise_for_status()
    j = r.json()
    return j["access_token"]


def token_exchange(subject_token: str, audience: str) -> str:
    body = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "client_id": GATEWAY_CLIENT,
        "client_secret": GATEWAY_SECRET,
        "subject_token": subject_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": audience,
    }
    log.info("Attempting token exchange for audience: %s", audience)
    r = SESSION.post(TOKEN_URL, data=body, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


def parse_sse_json(text: str) -> Optional[Dict[str, Any]]:
    # join lines that start with 'data:'
    try:
        lines = text.splitlines()
        data_lines = [ln[len("data:"):].strip() for ln in lines if ln.strip().startswith("data:")]
        if not data_lines:
            return None
        content = "".join(data_lines)
        return json.loads(content)
    except Exception:
        return None


def call_mcp(url: str, token: str, content_type: str, body: str, extra_headers: Optional[Dict[str, str]] = None) -> requests.Response:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
        "Accept": f"{content_type}, text/event-stream",
        "Connection": "keep-alive",
    }
    # If extra_headers contains mcp-session-id, also send Mcp-Session-Id for compatibility
    if extra_headers:
        headers.update(extra_headers)
        if "mcp-session-id" in extra_headers:
            headers["Mcp-Session-Id"] = extra_headers["mcp-session-id"]
    log.debug("Calling MCP %s with headers: %s", url, headers)
    r = SESSION.post(url, headers=headers, data=body.encode("utf-8"), timeout=10)
    # do not r.raise_for_status() — server may return JSON-RPC error inside 200
    return r


def main():
    log.info("=== ENVIRONMENT CHECK ===")
    # quick connectivity checks
    try:
        kc_ok = SESSION.get(KEYCLOAK_BASE, timeout=3)
        log.info("Keycloak reachable: %s", kc_ok.status_code)
    except Exception as e:
        log.error("Keycloak not reachable: %s", e)

    try:
        fa_ok = SESSION.get(f"{FIN_ASSISTANT_URL}/health", timeout=3)
        log.info("fin-assistant-mcp health: %s", fa_ok.status_code)
    except Exception as e:
        log.warning("fin-assistant-mcp not reachable: %s", e)

    # OIDC config
    oidc = fetch_oidc_config()
    if not oidc:
        log.error("OIDC discovery failed. Exiting.")
        sys.exit(1)

    log.info("Token endpoint: %s", oidc.get("token_endpoint"))

    # STEP1: user token
    try:
        user_token = token_password()
        log.info("User token acquired (len=%d)", len(user_token))
        claims = decode_jwt_payload(user_token)
        if claims:
            log.info("User token claims: sub=%s, aud=%s, azp=%s", claims.get("sub"), claims.get("aud"), claims.get("azp"))
    except Exception as e:
        log.exception("Failed to obtain user token: %s", e)
        sys.exit(2)

    # STEP2: token exchange (OBO)

    obo_token = None
    audiences = [AUDIENCE] + ALTERNATIVE_AUDIENCES
    for aud in audiences:
        try:
            obo_token = token_exchange(user_token, aud)
            log.info("OBO token acquired for audience: %s (len=%d)", aud, len(obo_token))
            selected_aud = aud
            break
        except requests.HTTPError as he:
            log.warning("Audience %s failed: %s", aud, he.response.text if he.response is not None else he)
            continue
        except Exception as e:
            log.warning("Audience %s failed: %s", aud, e)
            continue

    if not obo_token:
        log.error("Token exchange failed for all audiences")
        sys.exit(3)

    # Print the OBO access token
    print("\n=== OBO ACCESS TOKEN ===\n" + obo_token + "\n=======================\n")

    # decode obo
    try:
        claims = decode_jwt_payload(obo_token)
        log.info("OBO token claims: aud=%s, azp=%s", claims.get("aud"), claims.get("azp") if claims else None)
    except Exception:
        pass

    # STEP3: Authenticated endpoint tests
    # quick health checks
    try:
        r = SESSION.get(f"{FIN_ASSISTANT_URL}/health", headers={"Authorization": f"Bearer {obo_token}"}, timeout=5)
        log.info("Health check with token: %s", r.status_code)
    except Exception as e:
        log.warning("Health check request failed: %s", e)

    # Build test initialize + tools payloads
    init_template = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"},
        },
    })

    # Use correct FastMCP tool invocation: tools/call with name and params
    tools_variants = [
        # list_available_statements with params omitted entirely
        json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "mcp_financial-ass_list_available_statements"
            }
        }),
        # list_available_statements with params as null
        json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "mcp_financial-ass_list_available_statements",
                "params": None
            }
        }),
        # list_available_statements with no params (empty dict)
        json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "mcp_financial-ass_list_available_statements",
                "params": {}
            }
        }),
    ]

    media_types = [
        "application/vnd.mcp+json",
        "application/mcp+json",
        'application/json; profile="mcp"',
        "application/json",
    ]


    mcp_success = False
    for mt in media_types:
        log.info("Probing MCP media type: %s", mt)
        # send initialize and wait for a valid session id and 200 response
        try:
            r = call_mcp(f"{FIN_ASSISTANT_URL}/mcp", obo_token, mt, init_template)
            log.info("Initialize response: %s", r.status_code)
            session_id = None
            if r.status_code == 200:
                session_id = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
                if session_id:
                    log.info("Captured MCP session id: %s", session_id)
                    # also try parsing SSE for JSON
                    parsed = parse_sse_json(r.text)
                    if parsed:
                        log.debug("Initialize SSE parsed JSON: %s", parsed)
                    # Only send tool calls after successful initialize, using the same session id
                    for tv in tools_variants:
                        try:
                            headers_extra = {"mcp-session-id": session_id}
                            r2 = call_mcp(f"{FIN_ASSISTANT_URL}/mcp", obo_token, mt, tv, extra_headers=headers_extra)
                            log.info("tools variant response: %s", r2.status_code)
                            if r2.text:
                                parsed = parse_sse_json(r2.text)
                                if parsed:
                                    log.info("Parsed MCP response JSON: %s", json.dumps(parsed, indent=2))
                                    # check for JSON-RPC error
                                    if isinstance(parsed, dict) and parsed.get("error"):
                                        log.warning("RPC Error: %s", parsed.get("error"))
                                    else:
                                        log.info("RPC Result: %s", parsed.get("result"))
                                else:
                                    # server may return plain JSON
                                    try:
                                        js = r2.json()
                                        log.info("Response JSON: %s", json.dumps(js, indent=2)[:1000])
                                    except Exception:
                                        log.debug("Response text (preview): %s", r2.text[:400])
                            # treat 200 as success even if RPC error — we want to see server behaviour
                            if r2.status_code == 200 and not (r2.text and 'Invalid request parameters' in r2.text):
                                mcp_success = True
                                break
                        except Exception as e:
                            log.warning("tools variant failed: %s", e)
                            continue
                    # Only break out of the media type loop if a tool call succeeded
                    if mcp_success:
                        break
                else:
                    log.info("No session id returned from initialize, skipping tool calls.")
            else:
                log.info("Initialize did not return 200 (maybe 400/406): %s", r.status_code)
        except Exception as e:
            log.warning("Initialize failed for mt %s: %s", mt, e)
            session_id = None

    if not mcp_success:
        log.error("All media type probes / RPC variants failed. Check server logs.")
    else:
        log.info("MCP endpoint accepted one of the probed media types and variants.")

    # STEP4: Negative tests — call without auth
    try:
        log.info("Negative test: calling /mcp without auth (standard JSON)")
        r = SESSION.post(f"{FIN_ASSISTANT_URL}/mcp", headers={"Content-Type": "application/json"}, data=json.dumps({"jsonrpc": "2.0", "id": 99, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}))
        log.info("No-auth response: %s", r.status_code)
    except Exception as e:
        log.warning("No-auth negative test failed: %s", e)

    log.info("=== SUMMARY ===")
    log.info("User token client: %s", USER_CLIENT)
    log.info("OBO token audience: %s", selected_aud if 'selected_aud' in locals() else 'unknown')


if __name__ == "__main__":
    main()
