# Security Best Practices Report

## Executive Summary

The codebase has made meaningful progress (hashed refresh tokens, token versioning, stricter CORS configuration, admin guards), but there are still high-impact gaps around CSRF, trust boundaries for client IP, and auth/session hardening details. The most urgent issue is that cookie-based auth with `SameSite=None` is used without CSRF defense on state-changing endpoints.

---

## Critical / High Severity Findings

### [F-001] Missing CSRF protection for cookie-authenticated state-changing endpoints
- Rule ID: `FASTAPI-CSRF-COOKIE-001`
- Severity: High
- Location: `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:583`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:599`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:2032`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:1145`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:1989`
- Evidence:
  - Session cookies are explicitly cross-site: `samesite="none"` on auth cookies.
  - Credentialed CORS is enabled.
  - There is no CSRF token validation or `Origin`/`Referer` enforcement on POST routes.
- Impact: A malicious site can trigger authenticated POST actions in a victim browser (especially dangerous for admin-only actions if an admin visits attacker-controlled content).
- Fix:
  - Add CSRF protection for cookie-authenticated state-changing requests (double-submit cookie or synchronizer token).
  - Enforce strict `Origin` checks for all non-GET API endpoints.
  - Consider `SameSite=Lax` where cross-site behavior is not required.
- Mitigation (short-term):
  - Add an allowlist-based origin middleware for POST/PUT/DELETE immediately.

### [F-002] Security controls trust unverified `X-Forwarded-For`
- Rule ID: `FASTAPI-TRUST-BOUNDARY-001`
- Severity: High
- Location: `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:82`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:128`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:590`
- Evidence:
  - `_client_ip` uses the first `X-Forwarded-For` value directly.
  - The value drives lockout, rate limiting, and audit events.
- Impact: Attackers can spoof client IP to bypass throttling/lockout and pollute audit logs.
- Fix:
  - Use `request.client.host` unless running behind a trusted proxy that sanitizes forwarding headers.
  - If proxy mode is required, trust forwarded headers only from known proxy IPs.
- Mitigation (short-term):
  - Disable use of `X-Forwarded-For` for auth/rate-limit decisions until trusted-proxy validation is implemented.

### [F-003] OAuth callback does not validate email verification before account linking/creation
- Rule ID: `FASTAPI-OAUTH-IDENTITY-001`
- Severity: High
- Location: `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:640`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:642`
- Evidence:
  - `google_callback` accepts `email` from remote session payload and creates/links local users.
  - No explicit check like `email_verified == true`.
- Impact: If upstream identity payload is incomplete or misconfigured, account linking may trust unverified identities.
- Fix:
  - Enforce explicit verification checks from identity payload before linking user records.
  - Fail closed when verification metadata is missing.
- Mitigation (short-term):
  - Add a defensive guard that requires a positive verification flag before account create/link.

---

## Medium Severity Findings

### [F-004] Access/session tokens still returned in API response bodies
- Rule ID: `REACT-AUTH-TOKEN-HANDLING-001`
- Severity: Medium
- Location: `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:586`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:602`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:625`, `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:666`
- Evidence:
  - Auth endpoints return `{"token": ...}` while also setting HttpOnly cookies.
- Impact: Tokens can be inadvertently exposed via logs, browser instrumentation, client-side telemetry, or future regressions.
- Fix:
  - For browser flows, stop returning tokens in JSON responses and rely on HttpOnly cookies only.
  - Provide a separate API-key/token flow only for explicit non-browser clients.
- Mitigation (short-term):
  - Redact `token` fields from all API logs and monitoring payload capture.

### [F-005] Public sync status endpoint leaks operational metadata
- Rule ID: `FASTAPI-INFO-DISCLOSURE-001`
- Severity: Medium
- Location: `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend/server.py:1997`
- Evidence:
  - `/api/sync/status` is public, returns sync internals and counts.
- Impact: Reveals system behavior and timing useful for reconnaissance and abuse planning.
- Fix:
  - Restrict this endpoint to authenticated operators/admin.
  - Return minimal health metadata publicly if needed.
- Mitigation (short-term):
  - Remove detailed error fields from unauthenticated responses.

---

## Low Severity Findings

### [F-006] Security test coverage does not include new auth hardening controls
- Rule ID: `FASTAPI-TESTING-SECURITY-001`
- Severity: Low
- Location: `/Users/tudorf/Library/CloudStorage/OneDrive-VodafoneGroup/Documents/Codex/AgentHub-main/backend_test.py:150`
- Evidence:
  - Existing tests are mostly functional API checks; no lockout threshold tests, CSRF checks, admin endpoint authz tests, or refresh rotation abuse tests.
- Impact: Regressions in security controls may ship unnoticed.
- Fix:
  - Add dedicated tests for:
    - lockout window and reset behavior,
    - refresh token one-time use rotation,
    - admin-only access controls,
    - CSRF origin/token checks once implemented.

---

## Positive Controls Already Present

- Strict `CORS_ORIGINS` validation on startup (no wildcard with credentials).
- Refresh tokens stored hashed in DB.
- JWT token version invalidation on logout.
- Admin checks on high-impact operational endpoints (`/seed`, imports, `/sync/trigger`).
- Rate limiting exists and now attempts cross-instance behavior via DB.

---

## Secure-by-Default Improvement Plan

1. Implement CSRF defense for cookie-auth APIs (token + origin checks), then make it mandatory on all non-GET endpoints.
2. Replace raw `X-Forwarded-For` trust with trusted-proxy-aware IP extraction.
3. Require `email_verified` in OAuth callback before account linkage.
4. Stop returning tokens in response bodies for browser auth endpoints.
5. Restrict `/api/sync/status` to admin/operator role.
6. Add security regression tests and run them in CI.
