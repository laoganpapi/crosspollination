---
name: auth-permissions
description: Authentication and authorization for a multi-tenant product — sessions, credentials, invite-token security, membership-based access control, tenancy isolation. Load when the task involves login, sessions, invite links, roles, permissions checks, or tenant data isolation. Not for infrastructure secrets management or SSO/enterprise identity.
---

# Auth and permissions

## Session model

- First-party web app: server-side sessions win. Opaque random session id (≥128 bits, CSPRNG) in a cookie, session record in the database. Instantly revocable, no crypto to misconfigure.
- Cookie flags, non-negotiable: `HttpOnly; Secure; SameSite=Lax`, `__Host-` prefix. CSRF token on state-changing requests if any cross-site POST exists.
- JWTs are for service-to-service and third-party API access, not first-party browser sessions — no revocation without rebuilding sessions anyway, plus algorithm-confusion foot-guns.
- Rotate the session id on login and privilege change; absolute plus idle timeouts; logout deletes the server record.

## Credentials

- Best effort-to-security for a small product: magic link or email OTP as primary (email is the identity anchor; no password storage), passkeys offered as the upgrade.
- If passwords: argon2id or bcrypt cost ≥12, breached-password list check, no composition rules, no forced rotation, rate-limit and lock on failures, uniform "if an account exists…" responses against enumeration.
- Exactly one recovery path, secured as strongly as login — recovery is the real attack surface.

## Invite tokens

Treat like password-reset tokens:

- ≥32 random bytes, base64url. Store only the hash, with group, role, inviter, `expires_at`, `used_at`, `revoked_at`.
- Single-use: `used_at` set in the same transaction that creates the membership; a unique constraint on membership backstops replays.
- Expiry in days; revocable by the inviter; active invites listed in the UI.
- Redemption requires an authenticated session — the link lands on login, then attaches. Never grant tenancy from the URL alone.
- Rate-limit the redemption endpoint like a login endpoint. Never log tokens; POST them rather than letting them ride in URLs and Referer headers.

## Authorization

- For small groups, one `memberships` table is the whole model: `(user_id, group_id, role, UNIQUE(user_id, group_id))`, role as text + CHECK. No policy engine.
- Deny by default: one central `require_membership(user, group, min_role)` helper every handler calls. Not-allowed returns 404, not 403 — don't confirm existence.
- Object-level checks on every request. Broken object-level access (IDOR) has topped the OWASP list since 2021; the canonical bug is fetching by client-supplied id with no membership join.
- Derived outcomes are computed server-side: a majority decision is tallied from vote rows; roles gate who may propose or close, never what the outcome is.

## Tenancy isolation

- Every tenant-owned table carries `group_id` — denormalized even on grandchildren, making the mandatory filter cheap and composite indexes `(group_id, …)` natural.
- The safe path is the default: query helpers that require a group scope; unscoped queries are a review reject.
- The load-bearing control at small scale: scoped queries plus tests that log in as tenant A and hit every endpoint with tenant B's ids. Row-level security is an optional second net.

## Audit

- Append-only audit log (actor, action, target, group, timestamp, IP) for privileged actions: role changes, invites created/revoked, member removal, decision finalization, logins. No UPDATE or DELETE grants on it.

## Mistake checklist

Authz in the UI only · one endpoint missing its object check · plaintext invite tokens · tokens without expiry · role read from the client · 403s confirming existence · no rate limit on login/redeem · recovery weaker than login · secrets in git history
