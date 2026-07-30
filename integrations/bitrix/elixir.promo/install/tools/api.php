<?php

define('STOP_STATISTICS', true);
define('NO_KEEP_STATISTIC', true);
define('NO_AGENT_STATISTIC', true);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');

require $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Elixir\Promo\Service\PromoService;
use Elixir\Promo\Service\ReferralAccrualService;

const ELIXIR_PROMO_MODULE_ID = 'elixir.promo';

if (!Loader::includeModule(ELIXIR_PROMO_MODULE_ID)) {
    elixirPromoFail(503, 'module_unavailable', 'Модуль промокодов недоступен.', 'Promo module is unavailable.');
}
if (Option::get(ELIXIR_PROMO_MODULE_ID, 'enabled', 'N') !== 'Y') {
    elixirPromoFail(503, 'service_disabled', 'Проверка промокодов выключена.', 'Promo validation is disabled.');
}
if ((string)($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    elixirPromoFail(405, 'method_not_allowed', 'Разрешены только POST-запросы.', 'Only POST requests are allowed.');
}

$configuredToken = trim(Option::get(ELIXIR_PROMO_MODULE_ID, 'api_token', ''));
if (strlen($configuredToken) < 32) {
    elixirPromoFail(503, 'service_not_configured', 'API промокодов не настроен.', 'Promo API is not configured.');
}
$providedToken = trim((string)($_SERVER['HTTP_X_ELIXIR_PROMO_TOKEN'] ?? ''));
if ($providedToken === '' || !hash_equals($configuredToken, $providedToken)) {
    elixirPromoFail(401, 'unauthorized', 'Неверный токен API.', 'Invalid API token.');
}

$remoteAddress = trim((string)($_SERVER['REMOTE_ADDR'] ?? ''));
$allowedIps = array_values(array_filter(array_map(
    'trim',
    explode(',', Option::get(ELIXIR_PROMO_MODULE_ID, 'allowed_ips', ''))
)));
if ($allowedIps !== [] && !in_array($remoteAddress, $allowedIps, true)) {
    elixirPromoFail(403, 'forbidden', 'IP-адрес источника не разрешён.', 'Source IP address is not allowed.');
}

elixirPromoRateLimit(
    $remoteAddress !== '' ? $remoteAddress : 'unknown',
    max(1, min(10000, (int)Option::get(ELIXIR_PROMO_MODULE_ID, 'rate_limit', '300'))),
    max(1, min(86400, (int)Option::get(ELIXIR_PROMO_MODULE_ID, 'rate_limit_window_seconds', '60'))),
    $configuredToken
);

$maxBodyBytes = 1048576;
$contentLength = (int)($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($contentLength > $maxBodyBytes) {
    elixirPromoFail(413, 'payload_too_large', 'Тело запроса слишком большое.', 'Request body is too large.');
}
$rawBody = file_get_contents('php://input');
if (!is_string($rawBody) || $rawBody === '' || strlen($rawBody) > $maxBodyBytes) {
    elixirPromoFail(400, 'invalid_body', 'Тело запроса отсутствует или некорректно.', 'Request body is missing or invalid.');
}
$payload = json_decode($rawBody, true);
if (!is_array($payload)) {
    elixirPromoFail(400, 'bad_json', 'Тело запроса должно содержать корректный JSON.', 'Request body must contain valid JSON.');
}

$action = trim((string)($payload['action'] ?? ''));
$promo = trim((string)($payload['promo'] ?? ''));

try {
    $service = new PromoService();
    if ($action === 'lookup') {
        elixirPromoRespond(['action' => 'lookup', 'data' => $service->lookup($promo)]);
    }
    if ($action === 'quote') {
        $items = is_array($payload['items'] ?? null) ? $payload['items'] : [];
        $userId = isset($payload['user_id']) && is_numeric($payload['user_id'])
            ? max(0, (int)$payload['user_id'])
            : 0;
        $userEmail = isset($payload['user_email']) && is_scalar($payload['user_email'])
            ? trim((string)$payload['user_email'])
            : null;
        elixirPromoRespond([
            'action' => 'quote',
            'data' => $service->quote($promo, $items, $userId, $userEmail),
        ]);
    }
    if ($action === 'context') {
        $userId = isset($payload['user_id']) && is_numeric($payload['user_id'])
            ? max(0, (int)$payload['user_id'])
            : 0;
        $userEmail = isset($payload['user_email']) && is_scalar($payload['user_email'])
            ? trim((string)$payload['user_email'])
            : null;
        elixirPromoRespond([
            'action' => 'context',
            'data' => $service->context($promo, $userId, $userEmail),
        ]);
    }
    if ($action === 'profile') {
        $userId = isset($payload['user_id']) && is_numeric($payload['user_id'])
            ? max(0, (int)$payload['user_id'])
            : 0;
        $userEmail = isset($payload['user_email']) && is_scalar($payload['user_email'])
            ? trim((string)$payload['user_email'])
            : null;
        elixirPromoRespond([
            'action' => 'profile',
            'data' => $service->profile($userId, $userEmail),
        ]);
    }
    if ($action === 'attach_referrer' || $action === 'detach_referrer') {
        $userId = isset($payload['user_id']) && is_numeric($payload['user_id'])
            ? max(0, (int)$payload['user_id'])
            : 0;
        $userEmail = isset($payload['user_email']) && is_scalar($payload['user_email'])
            ? trim((string)$payload['user_email'])
            : null;
        if ($action === 'attach_referrer') {
            elixirPromoRespond([
                'action' => 'attach_referrer',
                'data' => $service->attachReferrer($promo, $userId, $userEmail),
            ]);
        }
        elixirPromoRespond([
            'action' => 'detach_referrer',
            'data' => $service->detachReferrer($userId, $userEmail),
        ]);
    }
    if ($action === 'quote_referral_accrual') {
        elixirPromoRespond([
            'action' => 'quote_referral_accrual',
            'data' => (new ReferralAccrualService())->quotePaidOrder($payload),
        ]);
    }
    if ($action === 'record_paid_purchase') {
        elixirPromoRespond([
            'action' => 'record_paid_purchase',
            'data' => (new ReferralAccrualService())->recordPaidPurchase($payload),
        ]);
    }
    if ($action === 'reverse_paid_purchase') {
        elixirPromoRespond([
            'action' => 'reverse_paid_purchase',
            'data' => (new ReferralAccrualService())->reversePaidPurchase($payload),
        ]);
    }
    if ($action === 'record_paid_order') {
        elixirPromoRespond([
            'action' => 'record_paid_order',
            'data' => (new ReferralAccrualService())->recordPaidOrder($payload),
        ]);
    }
    if ($action === 'referral_eligibility') {
        elixirPromoRespond([
            'action' => 'referral_eligibility',
            'data' => (new ReferralAccrualService())->eligibility($payload),
        ]);
    }
    if ($action === 'partner_summary') {
        elixirPromoRespond([
            'action' => 'partner_summary',
            'data' => (new ReferralAccrualService())->partnerSummary($payload),
        ]);
    }
    elixirPromoFail(422, 'unsupported_action', 'Неизвестная операция.', 'Unsupported action.');
} catch (\InvalidArgumentException $exception) {
    elixirPromoFail(422, $exception->getMessage(), 'Параметры запроса некорректны.', 'Request parameters are invalid.');
} catch (\DomainException $exception) {
    $message = $exception->getMessage();
    if (str_starts_with($message, 'product_not_found')) {
        elixirPromoFail(404, 'product_not_found', 'Товар Bitrix не найден.', 'Bitrix product was not found.');
    }
    if ($message === 'user_not_found') {
        elixirPromoFail(404, 'user_not_found', 'Покупатель Bitrix не найден.', 'Bitrix customer was not found.');
    }
    if ($message === 'purchase_not_found') {
        elixirPromoFail(404, 'purchase_not_found', 'Покупка приложения не найдена.', 'App purchase was not found.');
    }
    if ($message === 'own_promo_not_allowed') {
        elixirPromoFail(409, 'own_promo_not_allowed', 'Собственный промокод нельзя применять к своим покупкам.', 'A customer cannot apply their own promo code.');
    }
    if ($message === 'referral_cycle_not_allowed') {
        elixirPromoFail(409, 'referral_cycle_not_allowed', 'Этот промокод создаёт недопустимую реферальную связь.', 'This promo code creates an invalid referral relationship.');
    }
    if ($message === 'promo_not_active') {
        elixirPromoFail(409, 'promo_not_active', 'Промокод сейчас неактивен.', 'The promo code is currently inactive.');
    }
    if ($message === 'promo_usage_limit_reached') {
        elixirPromoFail(409, 'promo_usage_limit_reached', 'Лимит применений промокода исчерпан.', 'The promo code usage limit has been reached.');
    }
    elixirPromoFail(404, 'promo_not_found', 'Промокод не найден или неактивен.', 'Promo code was not found or is inactive.');
} catch (\Throwable $exception) {
    if (function_exists('AddMessage2Log')) {
        AddMessage2Log(
            'Promo API error: ' . get_class($exception) . ': ' . $exception->getMessage(),
            ELIXIR_PROMO_MODULE_ID
        );
    }
    elixirPromoFail(500, 'internal_error', 'Не удалось обработать промокод.', 'Unable to process promo code.');
}

function elixirPromoRespond(array $payload): void
{
    http_response_code(200);
    echo json_encode(['ok' => true] + $payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function elixirPromoFail(int $status, string $error, string $messageRu, string $messageEn): void
{
    http_response_code($status);
    echo json_encode([
        'ok' => false,
        'error' => $error,
        'message' => $messageRu,
        'message_ru' => $messageRu,
        'message_en' => $messageEn,
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function elixirPromoRateLimit(string $key, int $limit, int $windowSeconds, string $secret): void
{
    $privateDir = rtrim(Option::get(
        ELIXIR_PROMO_MODULE_ID,
        'private_dir',
        dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-promo'
    ), '/');
    $directory = $privateDir . '/rate-limit';
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        elixirPromoFail(503, 'rate_limit_unavailable', 'Ограничение запросов недоступно.', 'Rate limiting is unavailable.');
    }
    @chmod($directory, 0700);

    $path = $directory . '/' . hash_hmac('sha256', $key, $secret) . '.json';
    $handle = @fopen($path, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        if (is_resource($handle)) {
            fclose($handle);
        }
        elixirPromoFail(503, 'rate_limit_unavailable', 'Ограничение запросов недоступно.', 'Rate limiting is unavailable.');
    }

    $decoded = json_decode((string)stream_get_contents($handle), true);
    $timestamps = is_array($decoded) ? $decoded : [];
    $now = time();
    $active = [];
    foreach ($timestamps as $timestamp) {
        $timestamp = (int)$timestamp;
        if ($timestamp > $now - $windowSeconds && $timestamp <= $now) {
            $active[] = $timestamp;
        }
    }
    if (count($active) >= $limit) {
        $retryAfter = max(1, $windowSeconds - ($now - min($active)));
        flock($handle, LOCK_UN);
        fclose($handle);
        header('Retry-After: ' . $retryAfter);
        elixirPromoFail(429, 'rate_limited', 'Слишком много запросов.', 'Too many requests.');
    }

    $active[] = $now;
    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($active));
    fflush($handle);
    @chmod($path, 0600);
    flock($handle, LOCK_UN);
    fclose($handle);
}
