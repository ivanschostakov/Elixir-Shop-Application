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
    http_response_code($status);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    elixirReviewSyncRespond(405, ['ok' => false, 'error' => 'POST required']);
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
