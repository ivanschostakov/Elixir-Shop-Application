<?php

define('STOP_STATISTICS', true);
define('NO_KEEP_STATISTIC', true);
define('NO_AGENT_STATISTIC', true);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');

if ((string)(isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '') !== 'POST') {
    header('Allow: POST');
    giveaways_fail(405, 'method_not_allowed');
}

$maxBodyBytes = 65536;
$contentLength = isset($_SERVER['CONTENT_LENGTH']) ? (int)$_SERVER['CONTENT_LENGTH'] : 0;
if ($contentLength > $maxBodyBytes) {
    giveaways_fail(413, 'payload_too_large');
}

$raw = file_get_contents('php://input');
if (!is_string($raw) || strlen($raw) > $maxBodyBytes) {
    giveaways_fail(413, 'payload_too_large');
}
$payload = json_decode($raw, true);
if (!is_array($payload)) {
    giveaways_fail(400, 'bad_json');
}

require $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';

$giveawaysConfig = array();
$giveawaysConfigPath = __DIR__ . '/giveaways.config.php';
if (is_file($giveawaysConfigPath)) {
    $loadedGiveawaysConfig = include $giveawaysConfigPath;
    if (is_array($loadedGiveawaysConfig)) {
        $giveawaysConfig = $loadedGiveawaysConfig;
    }
}
if (empty($giveawaysConfig['enabled'])) {
    giveaways_fail(503, 'service_disabled');
}
$configuredToken = trim((string)($giveawaysConfig['token'] ?? ''));
$remoteAddress = trim((string)($_SERVER['REMOTE_ADDR'] ?? ''));
$allowedIps = $giveawaysConfig['allowed_ips'] ?? array();
if (is_array($allowedIps) && count($allowedIps) > 0 && !in_array($remoteAddress, $allowedIps, true)) {
    giveaways_fail(403, 'forbidden');
}

// Keep the legacy JSON token for the existing bot while preferring the header.
$token = isset($_SERVER['HTTP_X_GIVEAWAY_TOKEN'])
    ? trim((string)$_SERVER['HTTP_X_GIVEAWAY_TOKEN'])
    : trim((string)(isset($payload['token']) ? $payload['token'] : ''));
if ($configuredToken === '' || $token === '' || !hash_equals($configuredToken, $token)) {
    giveaways_fail(401, 'unauthorized');
}

giveaways_enforce_rate_limit(
    $remoteAddress !== '' ? $remoteAddress : 'unknown',
    $configuredToken
);

try {
    $connection = \Bitrix\Main\Application::getConnection();
    $sqlHelper = $connection->getSqlHelper();
    $command = isset($payload['cmd']) ? (string)$payload['cmd'] : '';

    if ($command === 'get_user_id') {
        $email = isset($payload['email']) ? trim((string)$payload['email']) : '';
        if ($email === '' || strlen($email) > 254 || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
            giveaways_fail(422, 'bad_email');
        }
        $emailSql = $sqlHelper->forSql($email, 254);
        $row = $connection->query("SELECT ID FROM b_user WHERE EMAIL='" . $emailSql . "' LIMIT 1")->fetch();
        if (!$row) {
            giveaways_fail(404, 'not_found');
        }
        giveaways_respond(array('ok' => true, 'user_id' => (int)$row['ID']));
    }

    if ($command === 'find_review') {
        $userId = isset($payload['user_id']) && is_numeric($payload['user_id']) ? (int)$payload['user_id'] : 0;
        $startDate = isset($payload['start_date']) ? (string)$payload['start_date'] : '';
        $minGrade = isset($payload['min_grade']) && is_numeric($payload['min_grade']) ? (int)$payload['min_grade'] : 0;
        $minLength = isset($payload['min_length']) && is_numeric($payload['min_length']) ? (int)$payload['min_length'] : 0;
        $limit = isset($payload['limit']) && is_numeric($payload['limit']) ? (int)$payload['limit'] : 5;

        $minGrade = max(0, min(5, $minGrade));
        $minLength = max(0, min(50000, $minLength));
        $limit = max(1, min(50, $limit));
        if ($userId <= 0) {
            giveaways_fail(422, 'bad_user_id');
        }
        if ($startDate === '' || !preg_match('/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/', $startDate)) {
            giveaways_fail(422, 'bad_start_date');
        }

        $dateSql = $sqlHelper->forSql($startDate, 19);
        $result = $connection->query(
            "SELECT * FROM b_sotbit_reviews_reviews
             WHERE ID_USER=" . $userId . "
               AND DATE_CREATION >= '" . $dateSql . "'
               AND RATING >= " . $minGrade . "
               AND CHAR_LENGTH(COALESCE(TEXT, '')) >= " . $minLength . "
             ORDER BY DATE_CREATION DESC LIMIT " . $limit
        );
        $rows = array();
        while ($row = $result->fetch()) {
            foreach ($row as $key => $value) {
                if ($value instanceof \Bitrix\Main\Type\DateTime || $value instanceof \DateTimeInterface) {
                    $row[$key] = $value->format('Y-m-d H:i:s');
                } elseif (is_object($value) && method_exists($value, '__toString')) {
                    $row[$key] = (string)$value;
                } elseif (is_object($value)) {
                    $row[$key] = null;
                }
            }
            $rows[] = $row;
        }
        giveaways_respond(array('ok' => true, 'count' => count($rows), 'reviews' => $rows));
    }

    giveaways_fail(422, 'bad_cmd');
} catch (\Throwable $exception) {
    if (function_exists('AddMessage2Log')) {
        AddMessage2Log('giveaways API internal error: ' . get_class($exception), 'giveaways');
    }
    giveaways_fail(500, 'internal_error');
}

function giveaways_enforce_rate_limit($key, $secret)
{
    global $giveawaysConfig;
    $limit = max(1, min(10000, (int)($giveawaysConfig['rate_limit'] ?? 120)));
    $windowSeconds = max(1, min(86400, (int)($giveawaysConfig['rate_limit_window_seconds'] ?? 60)));
    $directory = rtrim((string)($giveawaysConfig['rate_limit_dir'] ?? ''), '/');
    if ($directory === '') {
        giveaways_fail(503, 'rate_limit_unavailable');
    }
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        giveaways_fail(503, 'rate_limit_unavailable');
    }
    $path = $directory . '/' . hash_hmac('sha256', (string)$key, $secret) . '.json';
    $handle = @fopen($path, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        if (is_resource($handle)) {
            fclose($handle);
        }
        giveaways_fail(503, 'rate_limit_unavailable');
    }

    $decoded = json_decode((string)stream_get_contents($handle), true);
    $timestamps = is_array($decoded) ? $decoded : array();
    $now = time();
    $oldestAllowed = $now - $windowSeconds;
    $active = array();
    foreach ($timestamps as $timestamp) {
        $timestamp = (int)$timestamp;
        if ($timestamp > $oldestAllowed && $timestamp <= $now) {
            $active[] = $timestamp;
        }
    }
    if (count($active) >= $limit) {
        $retryAfter = max(1, $windowSeconds - ($now - min($active)));
        flock($handle, LOCK_UN);
        fclose($handle);
        header('Retry-After: ' . $retryAfter);
        giveaways_fail(429, 'rate_limited');
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

function giveaways_respond(array $payload)
{
    http_response_code(200);
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function giveaways_fail($status, $error)
{
    $messages = array(
        'service_disabled' => array('API розыгрышей выключен.', 'Giveaway API is disabled.'),
        'method_not_allowed' => array('Разрешены только POST-запросы.', 'Only POST requests are allowed.'),
        'payload_too_large' => array('Тело запроса слишком большое.', 'Request body is too large.'),
        'bad_json' => array('Тело запроса должно содержать корректный JSON.', 'Request body must contain valid JSON.'),
        'unauthorized' => array('Неверный токен API.', 'Invalid API token.'),
        'forbidden' => array('IP-адрес источника не разрешён.', 'Source IP address is not allowed.'),
        'rate_limited' => array('Слишком много запросов.', 'Too many requests.'),
        'rate_limit_unavailable' => array('Ограничение запросов недоступно.', 'Rate limiting is unavailable.'),
        'bad_email' => array('Укажите корректный email.', 'Provide a valid email address.'),
        'not_found' => array('Пользователь или отзыв не найден.', 'User or review was not found.'),
        'bad_user_id' => array('Укажите корректный ID пользователя.', 'Provide a valid user ID.'),
        'bad_start_date' => array('Укажите корректную дату начала.', 'Provide a valid start date.'),
        'bad_cmd' => array('Неизвестная команда.', 'Unsupported command.'),
        'internal_error' => array('Не удалось обработать запрос.', 'Unable to process request.'),
    );
    $translated = isset($messages[$error]) ? $messages[$error] : array('Не удалось выполнить запрос.', 'Unable to process request.');
    http_response_code((int)$status);
    echo json_encode(array(
        'ok' => false,
        'error' => (string)$error,
        'message' => $translated[0],
        'message_ru' => $translated[0],
        'message_en' => $translated[1],
    ), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}
