# Telegram weight-loss mentor

The original ordinary AI assistant retains its original prompt, tools, model selection,
conversation, phone/subscription checks and usage accounting. The user enters the
mentor explicitly from the main menu or `/mentor`. Mentor history and profile context
are separate. Leaving, choosing an ordinary AI assistant, or `/start` exits mentor mode.

## Current menu

- **Питание**: Добавить еду, Итоги за сегодня, Что поесть?
- **Мой прогресс**: Записать вес, Посмотреть динамику.
- **Мой план**: План на сегодня, Скорректировать план.
- **Мой профиль**: Мои данные и цель, Напоминания.

Every section has a return to the mentor menu. Ordinary replies show one menu button.
The full four-section keyboard is not repeated under every answer. AI actions run
through the existing phone, model and quota checks. Photos/voice retain the original
premium-model availability. Purchase requests expose the bot's Telegram WebApp button.

The initial introduction asks one question at a time and remembers the last menu
question so a short answer such as “19” is meaningful. Opening the menu itself does
not restart onboarding. Plain text remains available throughout. `/new_chat` inside
the mentor resets its conversation but preserves the stored profile and journal.

## Backend

All endpoints have prefix `/api/v1/integrations/telegram-ai` and require signed service
requests. HMAC binds timestamp, nonce, method, path and exact body; Redis rejects replay.
Identity, source message and request key come from the bot, never model arguments.

- `/profile/context`, `/profile/update`: confirmed self-reported profile facts.
- `/dashboard`: profile, today's confirmed meals/totals, recent weight history,
  latest meal draft, timezone and daily reminder settings.
- `/journal/draft`: creates an estimated meal draft; corrections replace a prior
  owned draft. Request retries are idempotent. Model tools cannot confirm a meal.
- `/journal/action`: owned `confirm` / `cancel`, invoked by the actual user button.
  Only confirmed meals count toward daily totals. Old replaced drafts cannot be saved.
- `/reminder/settings`: user-selected daily reminder time and IANA timezone; off by default.
- `/reminder/due`: trusted delivery worker claims due notifications once. Expired
  notifications older than 30 minutes are skipped; failures after claim may be missed
  rather than duplicated. Blocked bots disable that user's reminder.
- `/catalog`: read-only search/details and public prices/availability.

New weight updates automatically append idempotent timestamped measurements. Old profile
values are still displayed, but an unrecorded historical trend is never invented.
Daily meal boundaries follow the configured timezone (Europe/Moscow until changed).
Nutrition values are estimates, not clinical measurements; plans do not invent medical
prescriptions. A user may correct the profile in natural language.

Migrations: `c4e6a8b0d2f4` creates `telegram_ai_profiles`; `d5f7a9c1e3b5` adds
`telegram_ai_journal` and `telegram_ai_reminder_settings`. Data lives on the application
server. The bot's private SQLite file `data/telegram_mentor_modes.sqlite3` (0600)
stores only selected mode, mentor conversation IDs and the current navigation question.
Previously confirmed companion profile/weight data can seed the simple profile;
pending legacy cards are never imported. Legacy `/mentor/*` endpoints are retained
but the new menu does not invoke that older workflow.

The purchase button reads Telegram `getChatMenuButton`, with
`TELEGRAM_SHOP_WEBAPP_URL=https://elixirlink.online/` as fallback. App product IDs
are not assumed to match WebApp IDs; destination assortment/pricing may differ.

## Configuration and source

Existing environment values are preserved:

```
# Application
TELEGRAM_AI_BRIDGE_ENABLED=true
TELEGRAM_AI_BRIDGE_SECRET=<dedicated shared secret, at least 32 characters>
# Bot
TELEGRAM_AI_API_URL=https://api-elixirshop.devsivanschostakov.org
TELEGRAM_AI_BRIDGE_SECRET=<same secret>
TELEGRAM_SHOP_WEBAPP_URL=https://elixirlink.online/
```

`existing-bot.patch` is cumulative against `baseline-sha256.json`, which includes the
owner's pre-existing changes. `overlay/` contains new modules and bot tests. Never
blindly apply the cumulative patch over a previous release. Preserve `.env`, instruction
files, Telegram sessions and data. Check patches with `patch --dry-run -p1`.

Build and test a candidate against an isolated PostgreSQL database named `companion_test`.
Back up the current image/source, run the additive migration, replace only `backend-api`,
then deploy the bot and restart `elixiraibot.service`. Rollback restores image/source
and retains all profile/journal tables. No credential changes are required.

## Verification of the four-section release

- 19 backend tests passed, including real isolated PostgreSQL: owner isolation,
  draft/confirmation totals, corrected drafts, retry deduplication, weight history,
  timezone scheduling, opt-in reminders and stale notification expiry.
- 15 bot tests passed: original prompt/tool request preserved, separate histories,
  navigation, short answers, keyboard actions, identity binding, and plan callbacks
  using the existing AI handler with its phone/subscription/usage checks.
- A real model returned a meal estimate and a draft-bound Save button. The test used
  synthetic in-memory data, preserved the ordinary conversation and cleaned up provider
  resources. No test messages were sent to Telegram customers.
- Live readiness, signed dashboard/catalog calls and unsigned 401 rejection passed.
- API rollback image: `elixir-mentor-menu-rollback:20260925`.
- App source backup: `/home/paylakurusyan/deploy-backups/telegram-menu-app-20260926T002951Z`.
- Source backups on bot: `/home/paylakurusyan/deploy-backups/telegram-menu-bot-20260926T003105Z`.
- Both API and bot were checked after deployment. Physical Telegram UI tapping was
  not exercised. Temporary PostgreSQL test container/network were removed.
