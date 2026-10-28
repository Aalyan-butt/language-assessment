# Stage 2 — backend foundation

This stage implements the secure account layer. It does not yet implement test
submissions, audio uploads, checking, or report generation.

## Implemented endpoints

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/logout`
- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `POST /api/v1/admin/users/bulk`
- `PATCH /api/v1/admin/users/{id}/status`
- `PATCH /api/v1/admin/users/{id}/password`
- `PATCH /api/v1/admin/users/{id}/attempts`

Every protected request uses `Authorization: Bearer <token>`. State-changing
requests also require `X-CSRF-Token`. Admin endpoints validate the role on the
server; hiding a button in the browser is never treated as authorization.

## Account behavior

- Passwords use memory-hard Argon2id hashes with random embedded salts.
- A temporary password must be changed before admin actions are permitted.
- Five failed student logins lock only that account for 120 seconds; administrators remain retryable.
- Sessions expire after two hours without activity.
- Resetting a password revokes all of that user's existing sessions.
- Temporary passwords are accepted from an administrator and shown by the
  frontend once; no API can retrieve an existing password.
- Failed logins and account changes are written to `Audit` without credentials.

## One-time Google setup (performed during Stage 7 deployment)

1. Create a Google Cloud **Desktop app** OAuth client and download its JSON file.
2. Install the pinned dependencies: `python -m pip install -r requirements.txt`.
3. Run `python scripts/setup_google.py --client-secrets client_secret.json`.
4. Sign in with the free Google account that will own the data.
5. Enter the first administrator's temporary password when prompted.
6. Copy the five generated Google environment values into Render.

The setup utility creates the master spreadsheet, all eight tabs, the Drive
root folder, and the first administrator. OAuth secrets and refresh tokens must
never be committed to GitHub.
