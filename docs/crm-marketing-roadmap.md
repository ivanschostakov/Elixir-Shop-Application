# CRM + marketing roadmap for Elixir Shop

Дата пересмотра: 2026-07-23

## Оценка исходного плана

Направление выбрано правильно: Elixir Shop не должен копировать Bitrix24 или amoCRM целиком. Продукту нужны только те CRM-механики, которые усиливают собственную коммерцию: единый профиль клиента, работа с интересом до заказа, коммуникации, событийная автоматизация, journeys и аналитика воронки.

Сильные стороны исходного плана:

- Customer Intelligence поставлен раньше автоматизаций и journeys.
- Лиды отделены от заказов.
- Поддержка и продажи объединяются через inbox.
- Автоматизация описана через событие, условие и действие.
- Для journeys сразу учтены stop conditions, quiet hours и frequency cap.
- Аналитика смотрит не только на выручку, но и на потери воронки.

Что требовало усиления:

- Пять таблиц сами по себе не создают надежный tracking layer. Нужны версия контракта, whitelist событий, ограничения размера, идемпотентность и наблюдаемость.
- Нельзя смешивать сырой event log и быстрые CRM-запросы. Для сегментов нужен агрегированный marketing profile.
- До рассылок нужны consent, suppression, retention и quiet-hours policy.
- Автоматизации должны выполняться через идемпотентные execution records/outbox, а не напрямую из HTTP-запроса.
- Inbox требует канонической модели conversation/message и адаптеров каналов, иначе Telegram, AI chat и отзывы останутся отдельными системами.
- Lead и conversation — разные сущности: обращение может не быть коммерческой возможностью, а лид может существовать без переписки.
- Attribution необходимо хранить как минимум в first-touch и last-touch вариантах; campaign revenue без этого будет вводить в заблуждение.
- «Next best action» нельзя делать отдельной AI-фичей до появления качественных событий, исходов и причин потерь.

## Принципы архитектуры

1. Один канонический event contract для app, API, workers, webhooks и admin.
2. Сырые события неизменяемы; исправления выполняются новым событием или rebuild агрегата.
3. Повторная доставка события безопасна благодаря `event_id`.
4. CRM-экраны и сегменты читают агрегаты, а не сканируют весь event log.
5. Каждая автоматическая операция имеет execution record и idempotency key.
6. Каналы коммуникации подключаются адаптерами к общей модели inbox.
7. Consent, suppression, quiet hours и frequency cap проверяются в одном policy layer.
8. amoCRM и МойСклад остаются интеграциями, а не источником внутренней CRM-модели.
9. Mobile API изменяется только расширением; существующие контракты не ломаются.
10. Каждый этап заканчивается рабочим вертикальным срезом, метриками и тестами.

## Этап 11 — Customer Intelligence v1

Статус: реализован базовый вертикальный срез.

### Модель данных

- `user_devices` — installation, platform, app/build/OS, model, locale, timezone, push permission, install source, first/last seen, sessions.
- `user_events` — UUID события, пользователь, устройство, сессия, source, entity, occurred/received time, properties и attribution.
- `customer_marketing_profiles` — быстрый агрегат lifecycle, lead/engagement scores и счетчиков поведения.
- `customer_consents` — актуальное состояние согласия по purpose/channel.
- `customer_attribution` — first-touch, last-touch и install source.

### Контракт ingestion

- Authenticated batch endpoint: `POST /api/v1/users/me/customer-intelligence/sync`.
- Не больше 50 событий в batch.
- Whitelist имен событий.
- UUID idempotency.
- События не старше 90 дней и не более чем на 10 минут из будущего.
- Ограничения: properties 8 KB, device metadata 4 KB.
- App Integrity применяется так же, как к другим чувствительным mobile actions.

### События v1

- `app_opened`
- `product_viewed`
- `category_viewed`
- `search_submitted`
- `banner_clicked`
- `push_opened`
- `push_clicked`
- `cart_item_added`
- `cart_item_removed`
- `checkout_started`
- `checkout_failed`
- `order_created`
- `order_paid`
- `ai_chat_message_sent`
- `ai_recommendation_shown`
- `ai_action_clicked`
- `ai_action_completed`

### Потребители

- Customer 360°: lifecycle, scores, устройства, согласия, attribution и последние события.
- Сегменты: platform, app version, push permission, install source, lifecycle, lead score, event count/name.
- Analytics: platform, app version, push permission и event breakdown.
- Mobile: device/session sync при авторизации и возвращении приложения в active state.
- Backend: server-side commerce events для просмотров, поиска, корзины, checkout, заказа и оплаты.

### Data governance

- Сырые события хранятся 365 дней по умолчанию.
- Retention настраивается через `CUSTOMER_EVENT_RETENTION_DAYS`.
- Очистка выполняется worker-ом пакетами; агрегированный профиль сохраняется.
- Consent не считается предоставленным по умолчанию.

### Перед production rollout

- Применить migration `b4c5d6e7f8a9`.
- Проверить App Integrity для нового action в production.
- Согласовать текст и версию consent policy в приложении.
- Зафиксировать naming convention и владельца event schema.
- Добавить мониторинг ingestion error rate, event lag и доли клиентов без device profile.
- Сделать backfill `order_created/order_paid` и базового marketing profile из существующих заказов.
- При объеме в десятки миллионов событий перейти к месячному partitioning `user_events`.
- Добавить anonymous installation identity и безопасное identity stitching после входа. Это отдельный hardening-step, а не условие authenticated v1.

## Этап 12 — App Support, AI Chat visibility и Leads

Статус: реализован рабочий вертикальный срез.

Зависит от Customer Intelligence v1. Омниканальность на этом этапе не нужна: CRM работает с собственным support-чатом приложения, а Telegram/community остается отдельной пользовательской функцией и не импортируется в CRM.

### 12.1 Третий раздел чата — «Поддержка»

В существующем экране чата появляются три режима:

1. AI.
2. Сообщество.
3. Поддержка.

«Поддержка» — прямой диалог пользователя с командой через CRM. Пользователь видит историю, статус доставки/прочтения и имя сотрудника, который ответил. После закрытия обращения история сохраняется, а пользователь может открыть новый вопрос.

MVP поддерживает текст и изображения. Ответ администратора вызывает push с deep link обратно в support-раздел. Community/Telegram data не копируется в этот контур.

### 12.2 Support Inbox в CRM

Канонические сущности:

- `crm_conversations`
- `crm_messages`
- `crm_message_attachments`
- `crm_assignment_history`
- `crm_conversation_links`

Conversation содержит customer, status, priority, owner, SLA timestamps, last message и unread count. Message содержит direction, author type, `admin_user_id`, delivery/read timestamps и client-generated idempotency key.

CRM показывает:

- очереди `new`, `open`, `waiting_customer`, `waiting_team`, `resolved`, `spam`;
- непрочитанные обращения и просроченный SLA;
- карточку клиента и последние заказы рядом с перепиской;
- имя ответившего сотрудника и полную историю назначений;
- internal notes, невидимые клиенту;
- действия «назначить», «создать задачу», «создать лид», «связать заказ», «закрыть».

Каждое сообщение, назначение, изменение статуса и internal note попадает в audit. Права `support.read`, `support.reply`, `support.assign` разделяются.

Реализовано: очередь с polling, unread/read state, текстовые ответы, приватные изображения клиента, internal notes, приоритеты, назначение, связь с заказом, SLA/alerts, push `support_reply` и переход обратно в третий раздел чата.

### 12.3 AI Chat в CRM

AI Chat — отдельный read-only раздел аналитики поведения, а не канал Support Inbox. Он читает существующие `chats`, `ai_messages`, usage и interactive payload без копирования переписки.

В списке видны customer, last activity, message count, использованная модель, token usage и последнее намерение. В деталях:

- полная последовательность user/AI messages и attachments;
- рекомендованные товары и варианты;
- показанные AI actions;
- клики `open_product`, `add_to_basket`, `open_checkout`, `ask_ai`;
- успешность action, созданный basket item и последующий order;
- ошибки, reset reason и ссылка на Customer 360°.

Для полноценной воронки добавляются события `ai_chat_message_sent`, `ai_recommendation_shown`, `ai_action_clicked` и `ai_action_completed`. Доступ ограничивается отдельным permission и журналируется из-за чувствительности переписки.

Реализовано: read-only список и история сообщений, usage/model, приватная выгрузка вложений, interactive cards и отдельная хронология фактических событий пользователя. Секретные `action_token` удаляются из admin-ответа рекурсивно.

### 12.4 Leads

Канонические сущности:

- `crm_leads`
- `crm_lead_stage_history`
- `crm_lead_notes`
- связи с customer, conversation, product/category, task и order.

Lead содержит commercial intent: source, customer/contact, product/category interest, stage, priority, score, owner, next action, lost reason и converted order.

Lead можно создать:

- вручную из support conversation;
- из Customer 360°;
- позже автоматически по событиям Customer Intelligence или AI actions.

Lead stages: `new`, `contacted`, `interested`, `waiting`, `converted`, `lost`. Conversation остается коммуникацией, а Lead — потенциальной продажей; одно не создается автоматически из другого без явного правила.

Реализовано: отдельный pipeline, фильтры active/all/mine, score/priority/owner/next action, создание из Support и AI Chat, заметки, неизменяемая история стадий, обязательные lost reason и converted order, optimistic concurrency и audit.

### Acceptance criteria

- Сообщение из приложения появляется в Support Inbox один раз.
- Ответ администратора появляется в приложении с именем сотрудника и вызывает push.
- В CRM видны delivery/read state, first response SLA, resolution SLA и audit.
- Из conversation можно создать lead/task без повторного ввода клиента и контекста.
- AI Chat показывает сообщения и interactive actions, но не позволяет администратору незаметно вмешиваться в AI-диалог.
- Lead конвертируется в ссылку на существующий или новый order без копирования заказа.
- Для `lost` обязательна причина; история стадий неизменяема.

### Перед production rollout

- Применить migration `c5d6e7f8a9b0`.
- Убедиться, что `backend/private_media/support` примонтирован как постоянный приватный volume и доступен backend API.
- Проверить роли support/sales и отдельно выдать `ai_chats.read` только сотрудникам с бизнес-необходимостью.
- Запустить `worker-admin-automation`: он сканирует response/resolution SLA обращений.
- Проверить push deep link `mode=support&conversationId=...` на production Android/iOS builds.
- Зафиксировать retention и процедуру удаления AI/support переписки по запросу пользователя.
- Включить мониторинг очереди без ответов, first-response SLA, resolution SLA и lead-to-order conversion.

## Этап 13 — Event automation engine

Этот слой нужно завершить до marketing journeys.

### Модель

- `automation_rules`
- `automation_rule_versions`
- `automation_executions`
- `automation_action_executions`
- event outbox / queue

### Триггеры v1

- customer event;
- profile field changed;
- lead stage changed;
- conversation created/status changed;
- order status/payment changed;
- schedule/timer.

### Actions v1

- create task;
- assign owner;
- create/update lead;
- send push through policy layer;
- add/remove static segment membership;
- change lifecycle stage;
- create admin alert.

### Безопасность исполнения

- Draft/published versions.
- Preview на исторических данных без выполнения actions.
- Idempotency key: rule version + trigger event + action.
- Per-rule rate limit и kill switch.
- Retry с backoff и dead-letter state.
- Полный execution log с причиной match/no-match.

### Acceptance criteria

- Повторная доставка trigger не создает вторую задачу/лид/push.
- Оператор видит, почему rule matched и что выполнил.
- Rule можно отключить без потери уже созданной execution history.
- Ошибка одного action не теряет остальные executions.

## Этап 14 — Marketing journeys

Journeys строятся поверх event automation и общего messaging policy.

### Общие policy до первого journey

- frequency cap на customer/channel;
- quiet hours с timezone клиента и fallback timezone;
- suppression list;
- consent check;
- global and campaign unsubscribe;
- conflict resolution между journeys;
- stop conditions;
- holdout/control group;
- delivery/open/click/conversion attribution window.

### Journeys v1

1. Welcome.
2. Abandoned cart.
3. Post-purchase/review request.
4. Winback.

### Модель

- `marketing_journeys`
- `marketing_journey_versions`
- `marketing_journey_steps`
- `marketing_enrollments`
- `marketing_step_executions`
- `marketing_suppressions`
- `customer_message_frequency`

### Acceptance criteria

- Один customer не имеет двух активных enrollments одной journey/version.
- Покупка останавливает abandoned-cart journey до следующего шага.
- Все отправки проходят consent/frequency/quiet-hours policy.
- Для каждого шага видны entered, sent, skipped, failed, converted.
- Изменение опубликованной journey создает новую version.

## Этап 15 — Sales performance and attribution analytics

### Метрики

- lead stage conversion;
- lead-to-order conversion;
- time in stage;
- stuck leads/orders;
- conversation first response/resolution SLA;
- workload by owner;
- conversion and revenue by owner;
- lost reasons;
- first-touch and last-touch revenue;
- campaign/journey assisted conversion;
- pipeline forecast.

### Требования к корректности

- Все stage transitions берутся из history, а не из текущего значения.
- Revenue считается только по зафиксированной бизнес-дефиниции оплаченного заказа.
- У attribution есть явное окно и модель: first-touch, last-touch или assisted.
- Forecast отделен от фактической выручки.
- Dashboard показывает freshness timestamp и неполноту данных.

## Этап 16 — Next best action

Начинать только после накопления исходов lead/journey/manager actions.

Первая версия должна быть rules-based и объяснимой:

- «ответить на conversation с истекающим SLA»;
- «связаться с high-intent customer без заказа»;
- «повторная покупка ожидается по историческому интервалу»;
- «VIP customer оставил негативный отзыв».

ML/AI ranking добавляется позже и не выполняет действие автоматически. Оператор видит причину рекомендации и подтверждает действие.

## Рекомендуемый порядок поставки

1. Customer Intelligence production hardening и backfill.
2. Третий раздел «Поддержка» в приложении + Support Inbox в CRM.
3. Read-only AI Chat в CRM + события AI actions.
4. Lead core + conversion/lost reasons.
5. Event outbox и automation execution engine.
6. Messaging policy.
7. Abandoned cart journey как первый end-to-end сценарий.
8. Остальные journeys.
9. Sales performance dashboards.
10. Explainable next best action.

## Продуктовые метрики программы

- доля authenticated active users с device profile;
- доля ключевых действий, представленных валидным событием;
- ingestion duplicate/error/late-event rates;
- lead-to-order conversion;
- median first response and resolution time;
- abandoned-cart recovery rate;
- incremental conversion journeys против holdout;
- unsubscribe/suppression and notification complaint rates;
- automation failure/dead-letter rate;
- доля recommendations next best action, принятых менеджерами.

## Что намеренно не входит

- копирование Bitrix24/amoCRM целиком;
- импорт Telegram/community переписки в CRM;
- телефония и документы без подтвержденного use case;
- двусторонняя синхронизация внутренней CRM-модели с amoCRM;
- произвольный SQL/код в rule builder;
- автоматические AI-ответы и действия без audit, policy и human-control;
- vanity analytics без определенной бизнес-метрики и источника истины.
