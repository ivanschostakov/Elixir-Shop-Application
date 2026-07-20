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

In every existing forum topic, including General, a group administrator sends:

```text
/register Exact topic name
```

The bridge records that message's thread ID and deletes the command. Topics created after launch are discovered from Telegram's forum lifecycle messages and do not need manual registration.

## Enable and verify

1. Keep `TELEGRAM_COMMUNITY_ENABLED=false` while checking the migration and worker logs.
2. Set `TELEGRAM_COMMUNITY_ENABLED=true` on both the API and polling worker, then restart them.
3. Verify a linked group member can see the selector, topics, full author names and photos.
4. Post text, a photo, a document, and a reply from Telegram and confirm they appear in the app.
5. Post the same formats from the app and confirm each arrives once in the exact Telegram topic.
6. Verify an unlinked user sees the bot action and a linked non-member sees the invite action.

Turning the flag off hides the selector and stops new community ingestion and outbound delivery without deleting mirrored data.
