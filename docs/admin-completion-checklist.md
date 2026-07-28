# Admin panel completion checklist

The admin panel is considered production-complete when the following checks are true.

## Product scope

- Dashboard, sales, customers, leads, support/AI communications, catalog, content, marketing, automation, analytics, integrations and settings are mounted in the SPA.
- Public reviews always enter moderation before publication.
- The Bitrix review-sync module is backed up, installed and configured; Bitrix remains the only review moderation authority.
- Mobile API contracts are unchanged.
- Telegram/community messages are not imported into the CRM support inbox.
- Known system values have RU/EN labels; unknown values are displayed exactly as received.
- Product and variant images can be uploaded from the merchandising drawer.
- Banner mobile/desktop images, swipe, autoplay, impressions, clicks and internal routes are supported.
- Analytics includes daily/monthly app opens and top-product sales/view/conversion metrics.

## Security

- Admin login uses isolated admin tokens and HttpOnly refresh cookies.
- MFA is confirmed for every active administrator.
- Roles and permissions cover the production sections.
- Only the initial owner is bootstrapped directly; later staff use expiring, one-time email invitations.
- Invitation tokens are stored only as hashes, rotated on resend and never placed in API paths.
- Superadministrator assignment requires explicit confirmation and is audited.
- SMTP delivery is configured and a real invitation/acceptance/MFA flow has been verified.
- SMTP password-reset delivery is configured and the one-time reset flow has been verified.
- Production CORS does not allow wildcard origins.
- Dangerous writes are blocked when `ADMIN_READ_ONLY=true`.
- All material admin changes write audit events.
- AI Chat is read-only, access is audited and action tokens never reach the admin client.
- Support and AI attachments are returned through authenticated routes.

## Operations

- Order status transitions are explicit and audited.
- Recovery jobs are idempotent and run through Redis workers.
- Campaign launches snapshot recipients before sending.
- Automation rules are disabled by default until reviewed.
- Production readiness reports API/database, queue, worker, integration, backup, route, RBAC and security state.
- Support first-response/resolution SLA scanning runs in the automation worker.
- The private support attachment volume is persistent and included in backup/retention procedures.

## Quality gates

- Backend admin platform tests pass.
- Frontend tests pass.
- TypeScript check passes.
- Production frontend build passes.
- Server health endpoints return 200.
- Protected admin API endpoints return 401 without credentials.
- The support → admin reply → mobile read → lead stage flow passes against PostgreSQL.
- `/analytics` and `/readiness` load through the public HTTPS admin domain.
- Product stock matches MoySklad with `MOY_SKLAD_STOCK_RESERVE=0`.
- MoySklad order sync validates that the configured organization is the Khakimov legal entity.
- The packaged Bitrix module passes PHP lint and archive integrity checks before any installation.
