# Telegram mentor

The original ordinary AI assistant retains its original prompt, tools, model selection,
conversation, phone/subscription checks and usage accounting. The user enters the
mentor explicitly from the main menu or `/mentor`. Mentor history and profile context
are separate. Leaving, choosing an ordinary AI assistant, or `/start` exits mentor mode.

## Current menu and workflows

The first screen offers **Добавить еду** plus **Сегодня**, **Питание**,
**Тренировки**, **Мой курс**, **Прогресс**, **Спросить наставника**, **Профиль**,
and **Настройки**. Sections default open. Navigation edits its own Telegram card.
Typed form replies appear below the user's input as new messages. Long diaries paginate without trimming text.
AI replies, requested chart/photo attachments, and scheduled notifications remain
separate messages. Buttons on an AI answer create a navigation card instead of
overwriting the answer. Mentor responses use escaped HTML and keep URL underscores literal.

## Conversational input

Structured fields accept ordinary language rather than positional numbers, pipe
delimiters, weekday codes or technical timezones. `mentor_input.py` uses the existing
OpenAI client with a small, stateless `gpt-5-mini` Structured Outputs extraction call
(`store=False`, no tools or conversation). It normalizes weight, nutrition targets,
measurements, exercises/sets/repetitions, durations, course schedules/supplies,
reminder times and cities/timezones into the existing backend contracts. Plain
names, notes and verbatim existing dosage instructions remain plain text.

Incomplete answers retain the current step's question/answer history and produce
one clarification, without saving data or guessing missing fields. Local typed
validation and backend limits remain authoritative. The parser cannot prescribe
doses, calculate a nutrition target, convert medication units or approve its own
draft. Weight, reminders, timezone and explicit workout duration show a review
before a token-bound confirmation; other structured records keep their existing
draft/confirm flow. Old review buttons are invalidated by navigation. In-flight
extraction is discarded after navigation, mentor exit or privacy/conversation reset.

Extraction usage is recorded through the existing usage/token APIs; normalization
is a service operation and does not spend a premium answer credit. Ordinary AI
answers and media keep their existing phone, subscription, model and quota gates.
Raw answers are never added to extraction error logs. Temporary answer history is
bounded and cleared on a new step. No schema migration or mobile OTA is required.

- Today uses confirmed meals, the saved target (if any), today's weekly-program
  exercises, actual course dates, and wellbeing records. Weekly/interval course
  events are not represented as daily tasks.
- Nutrition accepts text, photos, voice, and spoken video notes through the existing
  professor/expert transport. Media remains professor-only under existing business
  rules. A server-side meal draft has confirm/edit/add/cancel buttons. History,
  search, favorites, and repeat create real persisted records; repeating food still
  requires confirmation. Remaining values are floored at zero and only use confirmed
  explicit user/specialist targets. The target calculator reuses the application
  nutrition rules, requires adult eligibility confirmation and a complete profile,
  and creates a draft which must be confirmed. It never silently replaces a target.
  Product lookup offers an approximate food estimate or search in the saved diary;
  it does not pretend to be a verified external food database.
- Workouts support a saved weekly exercise program, a resumable active session,
  idempotent per-set weight/repetition writes, duration, and total volume. A session
  freezes its program snapshot. Set entry defaults to the next unfinished planned
  exercise; an explicit exercise name overrides it. Finishing uses elapsed time or
  an explicit duration. Programs can be built step by step (weekday, exercise,
  sets, repetitions) or proposed by the AI as an unconfirmed draft. With no program,
  starting offers program creation or a free session; leaving cancels only empty
  active sessions, never recorded sets.
- Course items record existing user/specialist schemes only, with verbatim dose
  text, inclusive start/end dates, weekdays OR an interval anchored to the start
  date, multiple times, and an explicit timezone. Multiple items/products coexist;
  add them individually. Calendar, done/skipped marks, adherence, and supply estimates
  use those saved schedules. Supply needs stock and per-intake consumption in the
  same explicit unit; there is no dosage inference or unit conversion. Stopping a
  schedule preserves history and is not advice to discontinue treatment. A separate
  notification time can be set per course without changing its dose or intake times.
  Schedule revisions invalidate queued reminders; already sent events are not resent.
- Progress includes weight history, confirmed circumference measurements, private
  Telegram photo references, and accurate 7/30-day text reports for meals, workouts
  and courses. Reports include the recorded seven-day mean weight, average wellbeing,
  optional separately recorded energy, and sample counts. Missing days are not zero
  samples. Photo
  Reports also include calories averaged over recorded days, protein relative to
  the targets valid on those days, planned workout days, and progress toward the
  current weight goal from the first recorded measurement. Weight graphs are PNGs.
  IDs and transport receipts are removed from model context. No public photo URL
  is generated; viewing an owned photo uses protected Telegram content.
- Profile supports loss, gain, maintain, and custom goals with a goal detail. Missing
  Telegram keys may be filled from the app only through an already explicitly linked
  `User.telegram_user_id`. Telegram values, including explicit null deletions, win.
  Inheritance requires an enabled app companion and current consent, excludes future
  weight entries, and maps app `custom_goal` to Telegram `goal_detail`. Disabled app
  accounts are rejected even when a Telegram profile already exists.
  Conflicting weights are not silently synchronized by timestamp. Phone/name/account
  auto-linking is never performed. Updating profile context retains the loaded diary.
- Ask mentor offers quick prompts and structured adjustment-reason buttons. These
  use the existing model, phone, quota and accounting checks. Generic model tools
  cannot create or confirm a medication schedule or alter a dose.
- Settings offers opt-in morning weight, evening, weekly, inactivity and actual
  course-schedule reminders, timezone controls, and disable-all. Notifications omit
  health details by default. Detailed evening/weekly reports require a separate
  explicit opt-in; weekly reports include a weight chart when measurements exist.
  A specialist link uses the configured HTTPS destination; otherwise the existing
  support contact is offered without claiming it is a doctor.
  Privacy includes explicit, token-confirmed deletion of Telegram profile/journal
  and reminder records. App data, orders, Telegram messages and provider retention
  are outside that deletion's scope. Null tombstones prevent app health facts from
  being re-imported. In-flight AI drafts carry a profile version; resetting the
  conversation invalidates local in-flight replies as well.

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
  latest meal draft, timezone/reminder settings, and `workspace` read models.
- `/journal/draft`: creates an estimated meal draft; corrections replace a prior
  owned draft. Request retries are idempotent. Model tools cannot confirm a meal.
- `/journal/action`: owned `confirm` / `cancel`, invoked by the actual user button.
  Only confirmed meals count toward daily totals. Old replaced drafts cannot be saved.
- `/workspace/draft`, `/workspace/action`: strict typed draft/confirm/cancel for
  targets, programs, course items, measurements and wellbeing; course stop is explicit.
- `/workspace/workout/start`, `/set`, `/finish`: durable active sessions and per-set
  retries. (All three share the `/workspace/workout` prefix.)
- `/workspace/course/action`: owned done/skipped marks, never before the event time.
- `/workspace/course/reminder`: owned reminder-time override, no dosage changes.
- `/workspace/nutrition/preview`: guarded shared-rule calculation, no persistence.
- `/workspace/nutrition/eligibility`: explicit, revocable 30-day eligibility confirmation.
- `/workspace/workout/discard-empty`: cancels only owned empty active sessions.
- `/workspace/privacy/erase`: explicitly confirmed Telegram-only data removal.
- `/workspace/meals`, `/meals/favorite`, `/meals/repeat`: paginated confirmed meal
  library, literal name search, favorite state and repeat-to-draft.
- `/workspace/touch`: only the interaction timestamp, not message content.
- `/workspace/report`: 7/30-day bounded totals and recorded averages, without a
  last-ten-measurements shortcut or invented values for missing days.
- `/reminder/options`: full opt-in settings; `/reminder/settings` is the compatible
  legacy evening-time endpoint. Off is the default.
- `/reminder/due`: creates durable journal outbox records and returns expiring leases
  with `delivery_id`, `token`, `telegram_user_id`, `kind`, and privacy-safe `text`.
- `/reminder/check`: verifies a lease immediately before sending, including disabled
  or changed settings, stopped/completed course events and delivery grace.
- `/reminder/ack`: `sent`, `retry` or `blocked`. Only successful delivery ACK marks
  sent; failures retry with bounded backoff, and abandoned leases expire after five
  minutes. The bot keeps a local receipt across ACK failures/restarts so it can ACK
  again without knowingly resending. A crash between Telegram accepting the message
  and writing that local receipt can still duplicate delivery: this is at-least-once,
  not exactly-once delivery. Blocked bots disable all reminders for that identity.
- `/catalog`: read-only search/details and public prices/availability.

Course reminders expire after 30 minutes, morning/evening after 12 hours, weekly
after 24 hours, and inactivity after 12 hours. Expiry is recorded as `status=expired`
with a reason, not marked delivered. Missed doses are not sent as an injection backlog
or reinterpreted as catch-up instructions. Inactivity sends once per idle episode;
new mentor messages or confirmed records establish a new activity boundary.

New weight updates automatically append idempotent timestamped measurements. Old profile
values are still displayed, but an unrecorded historical trend is never invented.
Daily meal boundaries follow the configured timezone (Europe/Moscow until changed).
Nutrition values are estimates, not clinical measurements; plans do not invent medical
prescriptions. A user may correct the profile in natural language.

Migrations: `c4e6a8b0d2f4` creates `telegram_ai_profiles`; `d5f7a9c1e3b5` adds
`telegram_ai_journal` and `telegram_ai_reminder_settings`. Data lives on the application
server. The bot's private SQLite file `data/telegram_mentor_modes.sqlite3` (0600)
stores selected mode, mentor conversation IDs, the current navigation question and
temporary delivery receipts containing only numeric IDs. This release needs **no new
database migration**: new kinds and typed data reuse the existing Telegram journal.
New kinds: `target`, `program`, `workout`, `course`, `course_event`, `measurement`,
`wellbeing`, `activity`, `reminder_rule`, `reminder`. Reminder settings are the unique
`reminder-options` journal row; legacy daily settings remain compatible. Shared app
companion tables and schemas are not modified by this Telegram implementation.
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
# Optional, same comma-separated gates on backend and bot; empty means all open
TELEGRAM_MENTOR_CLOSED_SECTIONS=
# Values: today,food,workouts,course,progress,ask,profile,settings
# Bot only; omit until a real specialist destination is supplied
TELEGRAM_MENTOR_SPECIALIST_URL=
```

`existing-bot.patch` is cumulative against `baseline-sha256.json`, which includes the
owner's pre-existing changes. `overlay/` contains new modules and bot tests. Never
blindly apply the cumulative patch over a previous release. Preserve `.env`, instruction
files, Telegram sessions and data. Check patches with `patch --dry-run -p1`.
`mentor-delivery.patch` is the small October 8 transport delta against integrated
bot revision `da02e73`. Apply it once to `src/bot/main.py` after copying the overlay;
check `git apply --check` first. It leaves the ordinary assistant transport unchanged.
`mentor-conversation.patch` is the subsequent delta against bot revision `56344b5`.
Apply it once to `src/bot/handlers/new_user.py` with `git apply --check` first.
It connects literal text confirmation and draft tracking, routes counter-questions
through the original gated AI handler, and suppresses repeated free-mode hints
inside the mentor. It does not remove media/subscription/phone gates.

Build and test a candidate against an isolated PostgreSQL database named `companion_test`.
Back up the current image/source, run the additive migration, replace only `backend-api`,
then deploy the bot and restart `elixiraibot.service`. Rollback restores image/source
and retains all profile/journal tables. No credential changes are required.

The deployed baseline inspected on September 29 is bot commit `560d7192`. Its
`src/bot/main.py` already registers the mentor router/middleware and launches
`reminder_loop(professor_bot)` in `run_professor_bot`; no `run.py` edit is required.
Copy **all** overlay files, including `src/bot/handlers/mentor_flows.py` and
`src/bot/handlers/mentor_panel.py`.
The existing mentor router includes its form router. Do not apply the old cumulative
patch again to this already integrated baseline.

Deploy the backend and overlay as a coordinated pair: stop the old reminder worker
before switching `/reminder/due` to the ACK contract, then restart the new worker.
An old bot does not ACK the new leases and will cause repeated delivery attempts.
Rollback must coordinate both sides and retain the journal and bot data directory.

## Local validation and limitations

October 8 conversational completion (Telegram only, audit items 1-17):

- Guided steps retain validated known fields across follow-ups, provider failures
  and bounded history compaction. An answer may include several details at once.
  Counter-questions go to the ordinary mentor; pause/unknown/cancel are not facts.
- Corrections seed the owner's existing draft and alter only the specified fields.
  `POST /workspace/record` is signed, owner-scoped and respects section gates.
  Photo handles stay out of the extraction prompt and survive measurement edits.
- Literal confirmation is serialized and applies only to a unique existing preview.
  Several previews require the corresponding button; replacements remove stale
  pending previews. The model never obtains a confirmation/write tool.
- Voice/video-note answers in guided steps use existing transcription and the same
  professor, verified-phone and quota restrictions as ordinary media messages.
- Onboarding asks no mandatory questionnaire; profile numeric evidence accepts
  explicit Russian number words without relaxing source evidence or value ranges.
- Questions and previews keep the existing navigation/funnel. Meal edit instructions
  remain hidden. Reports add short factual next steps; missing logs are not treated
  as skipped meals or workouts. Workout results contain only workout information.
- No mobile UI, mobile companion implementation, subscription pricing or credentials
  change. Temporary form state still uses the bot's existing FSM storage; this is
  not a claim that an unfinished form survives a process restart.

Validation uses the bot snapshot plus `overlay/tests`, and all backend
`tests/test_telegram*.py` against a disposable local `companion_test` database.
Synthetic live-model extraction checks use `store=False` and do not send customer
messages or write their profiles/journals. Automated Telegram delivery remains mocked.

October 8 feedback update: bot regression coverage includes numeric weight without
AI, immutable AI replies, edited navigation, new typed-form responses, nutrition
preflight/shared calculator drafts, guarded stale buttons, guided exercise programs,
energy buttons, media transport, photo drafts, search/favorites, and section gates.
Isolated PostgreSQL tests cover deletion ownership, app-data preservation,
non-reimporting null tombstones, stale writes, eligibility expiry and empty-workout
cleanup. These tests mock Telegram delivery; they are not
a claim that every customer/device interaction has been exercised live.

September 29 changes have been tested with mocked transport and focused backend
validation tests; isolated PostgreSQL integration tests are supplied for the parent's
serial full run. No production/customer message or deployment was performed here.
The overlay adds no dependency. Full original bot imports require its existing
requirements, including `python-dotenv`, `matplotlib`, `Telethon`, `phonenumbers` and
`aiogram-media-group`, absent from the application-only local environment.

Explicit target entry and a confirmed preview from the shared app calculator are
implemented. AI target calculations use the same preview endpoint and create
saveable drafts. Measurements and course schedules use guided text forms. Weekly
programs also support AI drafts. Every save requires explicit user confirmation,
by button or an unambiguous text confirmation of the sole pending preview. Multiple
course products are entered individually; there is no bulk prescription importer.
Course corrections stop/recreate the item; historical adherence is preserved. The
progress list shows recent measurements/photos (31-day window, latest 30 records),
not an unlimited photo archive. Rendered charts use the loaded weight history. Course previews show the nearest
calendar window, while all generated events remain stored. Incomplete form fields
use the existing FSM until a server draft is created; a bot restart may require
re-entering an unfinished form. Confirmed data and active workouts survive restart.
Delivery is bounded by the documented grace windows and has the small ambiguous-send
duplicate window described above. Provider speech/food extraction quality and real
Telegram taps still require the parent's deployment verification.

Timur's test history/reminders have not been deleted. Identify the exact Telegram
identity and obtain his approval before any cleanup (feedback item 40). No third-party
test data is automatically erased. A legal review of health-data consent, retention
and provider deletion obligations is still required; the erasure endpoint is not a
claim of complete legal compliance. Callback timing is logged without health content;
the UI shows progress/retry, but no 15-second provider latency guarantee is made.

## Historical verification of the previous four-section release

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
