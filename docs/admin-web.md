# Elixir Shop Admin

`admin-web` is a separate desktop-first React application for store operations. It is served through the same origin as the FastAPI admin API, so the HttpOnly refresh cookie never needs cross-origin access.

## Local development

1. Start PostgreSQL, Redis and the backend.
2. Apply the migration: `cd backend && alembic upgrade head`.
3. If the database has no administrator yet, bootstrap the first superadministrator from an existing registered application user:

   `cd backend && python -m src.scripts.bootstrap_admin admin@example.com`

4. Start the SPA: `cd admin-web && npm install && npm run dev`.
5. Open `http://localhost:4173`. The first sign-in requires TOTP setup.

All later employees must be added from Settings → Staff through an email invitation. Direct staff creation is disabled after the initial bootstrap.

The Vite server proxies `/api` to `http://127.0.0.1:8000`. Override this with `ADMIN_API_PROXY_TARGET` in `admin-web/.env` when needed.

## Production

Run `docker compose up -d --build admin-web worker-admin-jobs worker-admin-automation`. The job worker consumes idempotent long-running operations from Redis; the automation worker scans enabled order rules and SLA deadlines. The web container serves the SPA on `127.0.0.1:8080` and proxies `/api`, `/media` and `/health` to `backend-api`. Put the existing HTTPS reverse proxy in front of port 8080.

`backend-api` and `worker-admin-jobs` must share the `backend/private_media` volume. The worker writes completed exports there, while the API stores private support attachments under `private_media/support`; both are served through authenticated download routes.

Production backend settings:

- `ADMIN_COOKIE_SECURE=true`
- `ADMIN_READ_ONLY=true` during the staging/read-only rollout
- `ADMIN_JOB_MAX_ATTEMPTS=3`
- `ADMIN_JOB_STALE_SECONDS=600`
- `ADMIN_JOB_RECOVERY_INTERVAL_SECONDS=30`
- `ADMIN_AUTOMATION_INTERVAL_SECONDS=60`
- `ADMIN_PUBLIC_HOST=admin-elixirshop.devsivanschostakov.org`
- `ADMIN_INVITATION_EXPIRE_HOURS=72`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` and `SMTP_FROM_NAME` configured for outbound invitations
- `CORS_ALLOWED_ORIGINS` limited to production origins (the admin itself uses same-origin requests)

After validation, turn `ADMIN_READ_ONLY` off section by section operationally. Administrators can be disabled and their sessions revoked from Settings → Staff.

## Staff roles and email invitations

The admin uses seven fixed system roles. An employee can receive several roles and gets the union of their permissions. Fixed roles keep access review predictable; a one-off permission should not be added to a person directly.

| Role | Operational scope |
| --- | --- |
| Super administrator | Full access, staff and role management, security settings and audit. Assign on its own. |
| Sales and CRM | Orders, customer profiles, leads, tasks, Support Inbox, AI Chat visibility, analytics and exports. |
| Support | Support conversations, customer/order context, internal notes, tasks, leads, AI Chat visibility and SLA monitoring. |
| Content and storefront | Products, merchandising, categories, banners, business content and review moderation. |
| Marketing | Segments, campaign setup and launch, trigger communication settings, referrals, marketing analytics and exports. |
| Logistics and operations | Order fulfillment, recovery actions, integrations, operational tasks, order automation and incident resolution. |
| Analyst / auditor | Cross-functional read-only access, analytics, exports and the audit log. |

Only the superadministrator has `staff.manage`. Granting `superadmin` requires a separate confirmation and cannot be combined with other roles because it already includes every permission. Role changes take effect on the next API request because permissions are loaded from PostgreSQL for every authenticated admin context.

### Invite a new employee

1. Open Settings → Staff and select Invite staff member.
2. Enter the employee's work email.
3. Select the smallest role set that covers the employee's actual duties. Use several roles only for a genuinely cross-functional employee.
4. If Super administrator is selected, read and confirm the full-access warning.
5. Send the invitation. The email contains a one-time link valid for 72 hours by default.
6. Track the invitation in Invitation history. A pending or expired invitation can be resent; resending rotates the token and extends the deadline. A pending invitation can be revoked.

If the email is not registered in Elixir Shop, the recipient enters name, surname and a new password. If a customer account already uses the email, the recipient must enter that account's current password. In both cases the email link proves control of the address, creates the admin record and assigns the selected roles. The recipient is then sent to the normal admin login and must configure TOTP MFA on first sign-in.

The invitation token is never stored in plaintext. PostgreSQL stores only its SHA-256 hash. The browser receives the token in the URL fragment, and the SPA sends it in a request body, keeping it out of API paths. Creation, resending, revocation, acceptance and subsequent role/status changes are retained in the admin audit log. Only one unaccepted, non-revoked invitation can exist per email.

### Change or remove access

- Use Edit roles on an active employee to replace their complete role set.
- Disable Active to block the employee immediately; each protected request rechecks both the user and admin status.
- An administrator cannot disable their own account or remove their own superadministrator role.
- Revoke the employee's active sessions from the security/session control when account compromise is suspected.
- Never share a superadministrator account. Invite a named person so every action has an attributable audit actor.

## Order recovery and job reliability

Order recovery actions are available to staff with `orders.recover`: payment status recheck, idempotent MoySklad order sync and delivery creation. Each command creates an `integration_run`, is protected by an idempotency key, records the requesting administrator in the audit log and runs outside the API process.

The admin worker uses a Redis processing list so a job is not lost when the process stops after receiving it. Interrupted and stale runs are recovered from PostgreSQL, transient failures retry with bounded exponential backoff, and permanent validation errors stop immediately. Operations → Integrations shows queue depth, running/retrying counts, failures in the last 24 hours and stale runs. Failed runs can be restarted explicitly without rewriting the original history row.

## Table workspace and exports

Orders, customers, products, reviews and the audit log keep filters, page and visible columns in the URL. Staff can save the current filters and columns as a private or shared database-backed view. Creating, updating and deleting a view is audited.

Row selection enables exports of either the complete filtered result or only selected records. CSV and XLSX files are created by the reliable admin worker, limited to 20,000 rows, checked against a server-side column/filter allowlist and protected from spreadsheet formula injection. A completed file can be downloaded only by the employee who requested it or a superadministrator. Review moderation additionally supports checked, concurrency-protected bulk publish/reject operations.

## Reviews

Review submission is public and rate-limited. Signed-in users keep their profile identity; guests are stored as guests. Every new review starts unpublished and appears in Content → Reviews. Only a user with `reviews.moderate` can publish or reject it. Public product endpoints and rating aggregates include only published, non-rejected reviews.

## CRM tasks, segments and campaigns

Tasks are persistent team records linked to an optional customer and order. They have an assignee, priority, due date and audited status changes. Overdue open tasks appear in the dashboard attention center, and a customer task can be created directly from the 360° profile.

Communications contains two deliberately separate workspaces. Support Inbox receives only the application's private support conversations; Telegram/community messages are not imported. Operators can reply with a visible employee identity, add internal notes, assign ownership and priority, monitor SLA and create a linked task or lead. AI Chat is read-only: it exposes the existing AI conversation, model usage, interactive recommendations and the customer's recorded AI action timeline. Every AI conversation view is audited, action tokens are stripped, and attachments are served only through authenticated admin routes.

Leads are commercial opportunities rather than orders or conversations. The pipeline supports `new`, `contacted`, `interested`, `waiting`, `converted` and `lost`, with owner, score, priority, next action, product/category context, notes and immutable stage history. A lost lead requires a reason; a converted lead requires an order belonging to the same customer.

Customer segments store validated filters for activity, verification, push reachability, order count and paid LTV. Segments can be private or shared. The admin panel shows both the full audience and the active customers currently reachable through push.

Push campaigns are created as drafts and can be launched immediately or scheduled. Before confirmation, the API recalculates the push-reachable audience and rejects the launch if it changed. Launch creates an immutable recipient snapshot (maximum 50,000), an audited background job and per-recipient delivery state. Completed campaigns show sent, skipped and failed counts. Existing restock, inactive-customer, abandoned-cart and review-reminder processors can be enabled or disabled from Marketing → Automations. Their message templates, internal deep links and timing/cooldown settings are database-backed, validated and audited.

Marketing CRM is intentionally minimalistic but operational: administrators can apply predefined push templates, preview a campaign against a segment before launch, store goal/UTM metadata, inspect delivery/click/failure metrics and open the recipient list. Referral analytics are calculated server-side, so summary cards are not limited by the first page of referral profiles.

## Analytics and reports

Analytics is a read-only owner view available from `/analytics`. It covers sales, customers, products, discounts and marketing for 7, 30, 90 or 365 days. Each section has compact summary cards, operational tables and a CSV download. Reports are generated from live PostgreSQL data and use the same authenticated admin namespace, without changing mobile API contracts.

## Operational automation, SLA and alerts

Order rules use a validated allowlist of conditions and actions. A rule can create an assigned task, enqueue one of the existing idempotent recovery operations, or send a deduplicated customer push. New rules are always disabled; enabling, editing, manual execution and deletion are audited. Each matching order state produces at most one execution record, and the automation worker processes bounded batches.

Task SLA is independent from the optional manual due date. Four priority policies define response and resolution times. A task captures its SLA deadlines when it is created or reprioritized, tracks first work and completion, and creates an operational alert once when breached. The automation screen shows per-employee open work, breaches and 30-day completion compliance.

Final integration failures, broken order rules and SLA breaches appear in a persistent alert center. Read state is stored per administrator; operational staff with `alerts.manage` can resolve an incident. A later successful integration run automatically resolves the matching failure alert. Dashboard widget composition is stored per administrator in PostgreSQL.

## Production readiness and controlled activation

Readiness is available from the admin sidebar and from `GET /api/v1/admin/integrations/production-readiness`. It summarizes API/database availability, Redis queue state, worker heartbeats, integration configuration, active alerts, public host and mutation mode. The screen is intentionally read-only and can be used before enabling catalog edits, moderation, order operations or automation rules.

The job worker and automation worker write heartbeat timestamps to Redis. A missing heartbeat is shown as unknown until the worker has completed at least one loop after deployment.

Backup freshness is reported only when `ADMIN_BACKUP_STATUS_PATH` points to a mounted JSON file with `last_success_at`, for example:

```json
{ "last_success_at": "2026-07-22T18:00:00+00:00" }
```

Step 5 automation presets can be created from Automation → Order rules. They are created disabled, assigned to the current administrator and only create internal staff tasks. They do not send customer push notifications or call external delivery/payment/MoySklad operations until an administrator explicitly edits, enables or runs a rule.
