# Security review

## Implemented controls

- Argon2id password hashes with per-password random embedded salts.
- No plaintext or reversibly encrypted password storage.
- Random session tokens; only HMAC-SHA256 token hashes are stored.
- Two-hour inactivity expiry and session revocation on logout/reset.
- Five-failure student-account lock for 120 seconds; administrator accounts are not locked out.
- Server-side role checks and ownership checks on every protected endpoint.
- CSRF nonce on all mutations and administrator reads.
- Exact frontend CORS origin.
- 20 MB request limit and 6 MB-per-recording limit.
- MP3 MIME and signature validation.
- Pydantic length, type and email validation.
- HTML escaping in dashboard and generated reports.
- Raw Sheet writes to prevent formula injection; only server-built hyperlink
  formulas use `USER_ENTERED`.
- CSV formula-injection protection for values beginning `=`, `+`, `-` or `@`.
- Audit records for logins, exports, account changes and teacher overrides.
- `X-Frame-Options`, no-sniff, no-referrer, no-store and restrictive browser
  permissions headers.
- OAuth secrets, refresh token and `.env` excluded by `.gitignore`.
- Private Drive files shared only with active administrator emails.

## Design decisions

A static GitHub Pages value cannot be a secret, so the original “shared secret
in the page” requirement was intentionally replaced by authenticated bearer
sessions, CSRF nonces, strict origins and server-side authorization.

The public LanguageTool API is not used because it disallows routine automated
traffic. The checker is deterministic and local to the Python backend.

## Operational responsibilities

- Keep the Google owner account protected by multi-factor authentication.
- Do not commit `.env`, OAuth JSON or copied setup output.
- Remove administrators immediately when access is no longer required.
- Review Audit and Jobs for repeated login failures or storage failures.
- Back up the master Sheet periodically through Google Drive.
- Rotate `APP_SECRET` and revoke OAuth credentials after suspected exposure.
- Treat placement output as educational data and follow local privacy policy.

## Known residual risks

- A free Render instance can sleep or be unavailable.
- Google Sheets is not a high-concurrency relational database; large groups
  should submit in waves.
- Rule-based language checking can produce false positives and false negatives.
- Browser-derived signal metrics can be manipulated and never determine final
  placement; teachers must confirm speaking and task relevance.
