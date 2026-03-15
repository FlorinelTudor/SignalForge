# Progress

## Lessons Learned

- Treat API, DB, and frontend as one release unit to avoid breaking flows (CORS, env vars, URL mismatches).
- Buildpacks require explicit runtime and dependency files (e.g., requirements.txt, .python-version).
- Stripe flows are easier when success/cancel URLs and price IDs are versioned early.
- Trust scoring needs explainable components and anti-gaming protections from day one.
- DNS and SSL setup are recurring blockers; document the exact steps per provider.

## Problems We Faced

- Buildpack detection failed due to missing requirements.txt and Python version pin.
- Pip install failures from private or missing dependencies.
- React build failures from peer dependency conflicts and ESLint warnings in CI.
- CORS blocking frontend requests to the API.
- MongoDB connection failures (TLS, DNS, and URI encoding issues).
- DNS misconfiguration for custom domains and HTTPS propagation delays.

## Recent Security Improvements

- Added strict input validation and search sanitization to reduce injection risk.
- Removed hardcoded JWT fallback and made `JWT_SECRET` required at startup.
- Added `.env.example` and updated ignore rules to keep real secrets out of Git.
- Added rate limiting middleware and security headers.
- Added login lockout controls for repeated failed auth attempts.
- Added refresh-token rotation and hashed refresh token storage (`token_hash`).
- Added JWT `token_version` checks so logout invalidates old access tokens.
- Enforced admin-only access for seed/import/sync trigger endpoints.
- Enforced explicit `CORS_ORIGINS` and blocked wildcard with credentials.
- Removed localStorage bearer token usage; frontend now uses cookie-based auth.
- Added CSRF protection for state-changing API calls (origin allowlist + double-submit token check).
- Added CSRF token cookie issuance on auth flows and automatic `X-CSRF-Token` header from frontend.
- Hardened proxy trust boundary: forwarded IP headers are ignored unless trusted proxy mode is explicitly configured.
- Added OAuth email verification enforcement gate before account creation/linking.
- Removed token values from auth JSON responses for browser flows (cookie-only session auth).
- Restricted `/api/sync/status` to admin access and audit logging.

## Security Gaps Closed

- CORS wildcard + credentials misconfiguration risk.
- Persistent bearer token exposure via localStorage.
- Refresh token plaintext storage in database.
- Multi-instance bypass risk for per-process-only throttling.
- Missing immediate access token revocation on logout.
- Missing CSRF controls for cookie-based auth with `SameSite=None`.
- Public operational sync metadata exposure via `/api/sync/status`.
- Untrusted `X-Forwarded-For` use in lockout/rate-limit decisions.

## Follow-up Tasks

- Verify `CORS_ORIGINS` is set correctly in Koyeb for production domains.
- Set `TRUST_PROXY_HEADERS` and `TRUSTED_PROXY_IPS` correctly for production proxy topology.
- Confirm identity provider payload includes an email verification flag in all environments.
- Redeploy backend + frontend after env updates.
- Add CI security checks (`pip-audit`, `npm audit`, dependency bot).
- Add integration tests for refresh rotation, lockout behavior, admin guards, and CSRF validation.
