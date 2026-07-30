<?php

declare(strict_types=1);

define('STOP_STATISTICS', true);
define('NO_KEEP_STATISTIC', true);
define('NO_AGENT_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');

require $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Elixir\Delivery\Service\DeliveryQuoteService;

const ELIXIR_DELIVERY_MODULE_ID = 'elixir.delivery';

if (!Loader::includeModule(ELIXIR_DELIVERY_MODULE_ID)) {
    elixirDeliveryFail(503, 'module_unavailable', 'Модуль расчёта доставки недоступен.', 'Delivery calculation module is unavailable.');
}
if (Option::get(ELIXIR_DELIVERY_MODULE_ID, 'enabled', 'N') !== 'Y') {
    elixirDeliveryFail(503, 'service_disabled', 'Расчёт доставки для приложения выключен.', 'App delivery calculation is disabled.');
}
if ((string)($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    elixirDeliveryFail(405, 'method_not_allowed', 'Разрешены только POST-запросы.', 'Only POST requests are allowed.');
}

$remoteAddress = trim((string)($_SERVER['REMOTE_ADDR'] ?? ''));
$allowedIps = array_values(array_filter(array_map(
    'trim',
    explode(',', Option::get(ELIXIR_DELIVERY_MODULE_ID, 'allowed_ips', ''))
)));
if ($allowedIps !== [] && !in_array($remoteAddress, $allowedIps, true)) {
    elixirDeliveryFail(403, 'forbidden', 'IP-адрес источника не разрешён.', 'Source IP address is not allowed.');
}

$maxBodyBytes = 262144;
$contentLength = (int)($_SERVER['CONTENT_LENGTH'] ?? 0);
if ($contentLength > $maxBodyBytes) {
    elixirDeliveryFail(413, 'payload_too_large', 'Тело запроса слишком большое.', 'Request body is too large.');
}
$rawBody = file_get_contents('php://input');
if (!is_string($rawBody) || $rawBody === '' || strlen($rawBody) > $maxBodyBytes) {
    elixirDeliveryFail(400, 'invalid_body', 'Тело запроса отсутствует или некорректно.', 'Request body is missing or invalid.');
}

$timestamp = trim((string)($_SERVER['HTTP_X_ELIXIR_TIMESTAMP'] ?? ''));
$signature = strtolower(trim((string)($_SERVER['HTTP_X_ELIXIR_SIGNATURE'] ?? '')));
$secret = trim(Option::get(ELIXIR_DELIVERY_MODULE_ID, 'shared_secret', ''));
if (
    strlen($secret) < 32
    || !ctype_digit($timestamp)
    || abs(time() - (int)$timestamp) > 300
    || !preg_match('/^[a-f0-9]{64}$/', $signature)
) {
    elixirDeliveryFail(401, 'unauthorized', 'Не удалось проверить подпись запроса.', 'Request signature could not be verified.');
}
$expectedSignature = hash_hmac('sha256', $timestamp . '.' . $rawBody, $secret);
if (!hash_equals($expectedSignature, $signature)) {
    elixirDeliveryFail(401, 'unauthorized', 'Не удалось проверить подпись запроса.', 'Request signature could not be verified.');
}

elixirDeliveryRateLimit(
    $remoteAddress !== '' ? $remoteAddress : 'unknown',
    max(1, min(10000, (int)Option::get(ELIXIR_DELIVERY_MODULE_ID, 'rate_limit', '120'))),
    max(1, min(86400, (int)Option::get(ELIXIR_DELIVERY_MODULE_ID, 'rate_limit_window_seconds', '60'))),
    $secret
);

$payload = json_decode($rawBody, true);
if (!is_array($payload)) {
    elixirDeliveryFail(400, 'bad_json', 'Тело запроса должно содержать корректный JSON.', 'Request body must contain valid JSON.');
}
if (($payload['action'] ?? null) !== 'quote') {
    elixirDeliveryFail(422, 'unsupported_action', 'Неизвестная операция.', 'Unsupported action.');
}

try {
    $result = (new DeliveryQuoteService())->quote($payload);
    elixirDeliveryRespond(['action' => 'quote', 'data' => $result]);
} catch (\InvalidArgumentException $exception) {
    elixirDeliveryFail(422, $exception->getMessage(), 'Параметры запроса некорректны.', 'Request parameters are invalid.');
} catch (\DomainException $exception) {
    $code = explode(':', $exception->getMessage(), 2)[0];
    $messages = [
        'product_not_found' => ['Товар из корзины не найден в Bitrix.', 'A basket product was not found in Bitrix.', 404],
        'destination_not_found' => ['Город доставки не сопоставлен в Bitrix/IPOL.СДЭК.', 'Delivery city is not mapped in Bitrix/IPOL.CDEK.', 422],
        'delivery_mode_unavailable' => ['Выбранный способ доставки отключён в настройках сайта.', 'Selected delivery mode is disabled in site settings.', 422],
        'calculation_failed' => ['Bitrix не смог рассчитать доставку для выбранного адреса и корзины.', 'Bitrix could not calculate delivery for the selected address and basket.', 422],
    ];
    $translated = $messages[$code] ?? ['Расчёт доставки недоступен.', 'Delivery calculation is unavailable.', 422];
    elixirDeliveryFail($translated[2], $code, $translated[0], $translated[1]);
} catch (\Throwable $exception) {
    if (function_exists('AddMessage2Log')) {
        AddMessage2Log(
            'Delivery API error: ' . get_class($exception) . ': ' . $exception->getMessage(),
            ELIXIR_DELIVERY_MODULE_ID
        );
    }
    elixirDeliveryFail(500, 'internal_error', 'Не удалось рассчитать доставку.', 'Unable to calculate delivery.');
}

function elixirDeliveryRespond(array $payload): void
{
    http_response_code(200);
    echo json_encode(['ok' => true] + $payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function elixirDeliveryFail(int $status, string $error, string $messageRu, string $messageEn): void
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

function elixirDeliveryRateLimit(string $key, int $limit, int $windowSeconds, string $secret): void
{
    $privateDir = rtrim(Option::get(
        ELIXIR_DELIVERY_MODULE_ID,
        'private_dir',
        dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-delivery'
    ), '/');
    $directory = $privateDir . '/rate-limit';
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        elixirDeliveryFail(503, 'rate_limit_unavailable', 'Ограничение запросов недоступно.', 'Rate limiting is unavailable.');
    }
    @chmod($directory, 0700);

    $path = $directory . '/' . hash_hmac('sha256', $key, $secret) . '.json';
    $handle = @fopen($path, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        if (is_resource($handle)) {
            fclose($handle);
        }
        elixirDeliveryFail(503, 'rate_limit_unavailable', 'Ограничение запросов недоступно.', 'Rate limiting is unavailable.');
    }

    $decoded = json_decode((string)stream_get_contents($handle), true);
    $timestamps = is_array($decoded) ? $decoded : [];
    $now = time();
    $active = [];
    foreach ($timestamps as $recordedAt) {
        $recordedAt = (int)$recordedAt;
        if ($recordedAt > $now - $windowSeconds && $recordedAt <= $now) {
            $active[] = $recordedAt;
        }
    }
    if (count($active) >= $limit) {
        $retryAfter = max(1, $windowSeconds - ($now - min($active)));
        flock($handle, LOCK_UN);
        fclose($handle);
        header('Retry-After: ' . $retryAfter);
        elixirDeliveryFail(429, 'rate_limited', 'Слишком много запросов.', 'Too many requests.');
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
