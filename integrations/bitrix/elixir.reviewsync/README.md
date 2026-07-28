# Elixir Review Sync for 1С-Битрикс

Модуль синхронизирует отзывы сайта (`sotbit.reviews`) и приложения Elixir Shop в обе стороны. Передаются рейтинг, текст, ответ магазина, лайки/дизлайки и статус `pending` / `published` / `rejected`. Товары сопоставляются только по `XML_ID` сайта и `products.system_id` приложения. Обмен подписан HMAC-SHA256; база сайта наружу не открывается.

Медиа-вложения отзывов в версию 1.0 не входят: фотографии и файлы остаются в исходной системе. Текстовые данные, ответ магазина, реакции и модерационный статус синхронизируются.

## Требования

- 1С-Битрикс с установленным `sotbit.reviews`;
- PHP 8.1 или новее;
- HTTPS на сайте;
- одинаковые UUID товара в `XML_ID` Битрикс и `products.system_id` приложения.

## Установка на сайт

1. Скопируйте каталог `elixir.reviewsync` целиком в `local/modules` сайта:

   `<DOCUMENT_ROOT>/local/modules/elixir.reviewsync`

2. В административной панели Битрикс откройте «Marketplace → Установленные решения», найдите «Elixir: двусторонняя синхронизация отзывов» и нажмите «Установить».

3. Откройте настройки установленного модуля, укажите IP backend приложения,
   закрытый каталог вне `public_html` и задайте отдельный секрет длиной не менее
   32 символов. Сгенерировать его можно командой:

   ```bash
   openssl rand -hex 32
   ```

   Если административная форма недоступна, секрет можно сохранить командой из корня сайта:

   ```bash
   php -r '$_SERVER["DOCUMENT_ROOT"]=getcwd(); require "bitrix/modules/main/include/prolog_before.php"; \Bitrix\Main\Config\Option::set("elixir.reviewsync", "shared_secret", "PASTE_SECRET_HERE");'
   ```

4. Проверьте, что endpoint отвечает `405` на GET, а POST без корректной подписи - `401`:

   `https://elixirpeptide.ru/bitrix/tools/elixir.reviewsync/sync.php`

## Настройка приложения

Добавьте в `backend/.env`:

```dotenv
WEBSITE_REVIEW_SYNC_ENDPOINT=https://elixirpeptide.ru/bitrix/tools/elixir.reviewsync/sync.php
WEBSITE_REVIEW_SYNC_SECRET=тот_же_секрет
WEBSITE_REVIEW_SYNC_INTERVAL_MINUTES=10
WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS=30
```

Примените миграции, пересоберите backend и запустите сервис `worker-website-review-sync`.

Перед первым запуском убедитесь, что:

- `XML_ID` товаров сайта действительно совпадают с `products.system_id`;
- создан отдельный shared secret, не совпадающий с другими production-секретами;
- сделан штатный backup баз сайта и приложения;
- worker пока остановлен.

Разовая синхронизация после этой проверки:

```bash
docker compose run --rm backend-api python -m src.scripts.sync_reviews_with_website
```

Затем:

```bash
docker compose up -d --build worker-website-review-sync
docker compose logs --tail=100 worker-website-review-sync
```

## Безопасность и откат

- Никогда не используйте пароль root, пароль БД или основной API-токен как shared secret.
- Endpoint принимает только POST, ограничивает тело 2 МБ и отклоняет запросы старше 5 минут.
- Endpoint поддерживает IP allowlist и серверный rate limit.
- Для остановки достаточно очистить `WEBSITE_REVIEW_SYNC_ENDPOINT`/`WEBSITE_REVIEW_SYNC_SECRET` и перезапустить worker.
- При удалении модуля endpoint удаляется, отзывы сайта не удаляются.
- Не запускайте два экземпляра worker одновременно.
