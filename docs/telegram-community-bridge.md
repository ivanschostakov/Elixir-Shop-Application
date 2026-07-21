# Telegram community bridge rollout

The community bridge is disabled by default. Deploy the API, Telegram polling worker, shared `backend/private_media` volume, and migration before making it visible in the app. This directory must not be exposed by the web server; files are served only through short-lived signed API links.

## Bot and group setup

1. Add the existing bot to the forum supergroup as an administrator.
2. Disable BotFather privacy mode so the bot receives group messages.
3. Allow the bot to delete messages; it removes the one-time `/register` commands.
4. Set the community environment values:
   - `TELEGRAM_COMMUNITY_CHAT_ID` to the forum supergroup ID (normally beginning with `-100`).
   - `TELEGRAM_COMMUNITY_JOIN_URL` to the private invite or join URL.
   - `TELEGRAM_BOT_USERNAME` without `@`.
   - `TELEGRAM_COMMUNITY_MEDIA_DIR` only when the default private-media path is not suitable.
   - `TELEGRAM_COMMUNITY_MEDIA_SIGNING_SECRET` to a separate random secret.
5. Apply `alembic upgrade head` while `TELEGRAM_COMMUNITY_ENABLED=false`.
6. Start one Telegram update transport. Production uses `src.workers.telegram_polling`, which removes any configured webhook before polling.

## Register existing topics

The preferred bootstrap uses a dedicated Telegram user session through MTProto. The account only needs to be a member of the forum; making the dedicated account an administrator is recommended for operational continuity.

1. Create Telegram API credentials at `my.telegram.org` and configure:
   - `TELEGRAM_USERBOT_API_ID`
   - `TELEGRAM_USERBOT_API_HASH`
   - optional `TELEGRAM_USERBOT_PHONE`
   - `TELEGRAM_USERBOT_SESSION_PATH=/app/backend/.secrets/telegram-userbot/community`
   - `TELEGRAM_USERBOT_TOPIC_SYNC_INTERVAL_SECONDS=60`
   - `TELEGRAM_USERBOT_HISTORY_SYNC_INTERVAL_SECONDS=60`
   - `TELEGRAM_USERBOT_FULL_HISTORY_RECONCILE_SECONDS=86400`
2. Keep `TELEGRAM_USERBOT_ENABLED=false` until the session is authorized.
3. Authorize the persistent session interactively:

```bash
docker compose run --rm worker-telegram-polling python -m src.scripts.telegram_userbot_login
```

4. Set `TELEGRAM_USERBOT_ENABLED=true` and recreate the Telegram worker. Bot API polling starts immediately while the persistent Telethon client fetches topics, backfills existing topic history, and listens for edits/deletes. It incrementally fetches missed messages every minute and performs a full history reconciliation daily so deletions are repaired even if an event was missed.

The app community requires only an authenticated app account. App users do not link Telegram and do not need Telegram group membership. App-originated messages are relayed by the bot as **Full Name** `· 💬 Приложение`; replies use **Full Name** `· ↩️ Приложение` and Telegram's native reply target. Telegram usernames and Telegram identifiers stay internal.

For a manual history reconciliation:

```bash
docker compose run --rm worker-telegram-polling python -m src.scripts.telegram_history_sync
```

`/register` remains an administrator-only fallback. In an existing topic, send:

```text
/register Exact topic name
```

The bridge records that message's thread ID and deletes the command. Bot API lifecycle messages still update newly created, renamed, closed, and reopened topics immediately; MTProto fills the complete initial list and detects deletions.

## Enable and verify

1. Keep `TELEGRAM_COMMUNITY_ENABLED=false` while checking the migration and worker logs.
2. Set `TELEGRAM_COMMUNITY_ENABLED=true` on both the API and polling worker, then restart them.
3. Verify an authenticated app user with no linked Telegram account can see the selector, topics, full author names and photos.
4. Post text, a photo, a document, and a reply from Telegram and confirm they appear in the app.
5. Post the same formats from the app and confirm each arrives once in the exact Telegram topic.
6. Add and remove reactions in the app from two accounts and confirm the counts update on the next poll.
7. Edit and delete messages from both surfaces and confirm the open app chat updates on its next poll.

Turning the flag off hides the selector and stops new community ingestion and outbound delivery without deleting mirrored data.
