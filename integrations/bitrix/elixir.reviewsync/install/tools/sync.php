<?php

define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
define('BX_SECURITY_SHOW_MESSAGE', true);

require $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Elixir\ReviewSync\Service\ReviewSyncService;

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');

function elixirReviewSyncRespond(int $status, array $payload): void
{
    if (($payload['ok'] ?? null) === false && isset($payload['error'])) {
        $messages = [
            'POST required' => ['Разрешены только POST-запросы.', 'Only POST requests are allowed.'],
            'Invalid request body' => ['Тело запроса отсутствует или некорректно.', 'Request body is missing or invalid.'],
            'Invalid authentication' => ['Не удалось проверить подпись запроса.', 'Request signature could not be verified.'],
            'Source address is not allowed' => ['IP-адрес источника не разрешён.', 'Source IP address is not allowed.'],
            'Too many requests' => ['Слишком много запросов.', 'Too many requests.'],
            'Rate limiting is unavailable' => ['Ограничение запросов недоступно.', 'Rate limiting is unavailable.'],
            'Invalid JSON' => ['Тело запроса должно содержать корректный JSON.', 'Request body must contain valid JSON.'],
            'Required module is unavailable' => ['Не установлен необходимый модуль Bitrix.', 'A required Bitrix module is unavailable.'],
            'Review synchronization failed' => ['Не удалось синхронизировать отзывы.', 'Unable to synchronize reviews.'],
        ];
        $translated = $messages[(string)$payload['error']] ?? ['Не удалось выполнить запрос.', 'Unable to process request.'];
        $payload['message'] = $translated[0];
        $payload['message_ru'] = $translated[0];
        $payload['message_en'] = $translated[1];
    }
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    elixirReviewSyncRespond(405, ['ok' => false, 'error' => 'POST required']);
}

$remoteAddress = trim((string)($_SERVER['REMOTE_ADDR'] ?? ''));
$allowedIps = array_values(array_filter(array_map(
    'trim',
    explode(',', Option::get('elixir.reviewsync', 'allowed_ips', ''))
)));
if ($allowedIps !== [] && !in_array($remoteAddress, $allowedIps, true)) {
    elixirReviewSyncRespond(403, ['ok' => false, 'error' => 'Source address is not allowed']);
}

$body = file_get_contents('php://input');
if (!is_string($body) || $body === '' || strlen($body) > 2097152) {
    elixirReviewSyncRespond(400, ['ok' => false, 'error' => 'Invalid request body']);
}

$timestamp = (string)($_SERVER['HTTP_X_ELIXIR_TIMESTAMP'] ?? '');
$signature = strtolower((string)($_SERVER['HTTP_X_ELIXIR_SIGNATURE'] ?? ''));
$secret = trim((string)Option::get('elixir.reviewsync', 'shared_secret', ''));
if ($secret === '' || !ctype_digit($timestamp) || abs(time() - (int)$timestamp) > 300) {
    elixirReviewSyncRespond(401, ['ok' => false, 'error' => 'Invalid authentication']);
}
$expected = hash_hmac('sha256', $timestamp . '.' . $body, $secret);
if (!hash_equals($expected, $signature)) {
    elixirReviewSyncRespond(401, ['ok' => false, 'error' => 'Invalid authentication']);
}

elixirReviewSyncRateLimit(
    $remoteAddress !== '' ? $remoteAddress : 'unknown',
    max(1, min(10000, (int)Option::get('elixir.reviewsync', 'rate_limit', '120'))),
    max(1, min(86400, (int)Option::get('elixir.reviewsync', 'rate_limit_window_seconds', '60'))),
    $secret
);

$payload = json_decode($body, true);
if (!is_array($payload)) {
    elixirReviewSyncRespond(400, ['ok' => false, 'error' => 'Invalid JSON']);
}
if (!Loader::includeModule('elixir.reviewsync') || !Loader::includeModule('sotbit.reviews') || !Loader::includeModule('iblock')) {
    elixirReviewSyncRespond(503, ['ok' => false, 'error' => 'Required module is unavailable']);
}

try {
    $result = (new ReviewSyncService())->handle($payload);
    elixirReviewSyncRespond(200, ['ok' => true] + $result);
} catch (Throwable $exception) {
    AddMessage2Log(
        sprintf('%s: %s', get_class($exception), $exception->getMessage()),
        'elixir.reviewsync'
    );
    elixirReviewSyncRespond(422, ['ok' => false, 'error' => 'Review synchronization failed']);
}

function elixirReviewSyncRateLimit(string $key, int $limit, int $windowSeconds, string $secret): void
{
    $privateDir = rtrim(Option::get(
        'elixir.reviewsync',
        'private_dir',
        dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-reviewsync'
    ), '/');
    $directory = $privateDir . '/rate-limit';
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        elixirReviewSyncRespond(503, ['ok' => false, 'error' => 'Rate limiting is unavailable']);
    }
    @chmod($directory, 0700);

    $path = $directory . '/' . hash_hmac('sha256', $key, $secret) . '.json';
    $handle = @fopen($path, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        if (is_resource($handle)) {
            fclose($handle);
        }
        elixirReviewSyncRespond(503, ['ok' => false, 'error' => 'Rate limiting is unavailable']);
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
        elixirReviewSyncRespond(429, ['ok' => false, 'error' => 'Too many requests']);
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
