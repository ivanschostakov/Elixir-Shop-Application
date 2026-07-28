<?php

define('STOP_STATISTICS', true);
define('NO_KEEP_STATISTIC', true);
define('NO_AGENT_STATISTIC', true);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store, max-age=0');
header('X-Content-Type-Options: nosniff');

$appIntegrationConfig = array();
$appIntegrationConfigPath = __DIR__ . '/app_integration.config.php';
if (file_exists($appIntegrationConfigPath)) {
    $loadedConfig = include $appIntegrationConfigPath;
    if (is_array($loadedConfig)) {
        $appIntegrationConfig = $loadedConfig;
    }
}

if (!app_integration_config('enabled', false)) {
    app_integration_fail(503, 'service_disabled', 'Website identity integration is disabled');
}

$configuredToken = trim((string)app_integration_config('token', ''));
if (strlen($configuredToken) < 32) {
    app_integration_fail(503, 'service_not_configured', 'Website identity integration is not configured');
}

if ((string)(isset($_SERVER['REQUEST_METHOD']) ? $_SERVER['REQUEST_METHOD'] : '') !== 'POST') {
    header('Allow: POST');
    app_integration_fail(405, 'method_not_allowed', 'Only POST requests are allowed');
}

$providedToken = isset($_SERVER['HTTP_X_APP_INTEGRATION_TOKEN'])
    ? trim((string)$_SERVER['HTTP_X_APP_INTEGRATION_TOKEN'])
    : '';
if ($providedToken === '' || !hash_equals($configuredToken, $providedToken)) {
    app_integration_fail(401, 'unauthorized', 'Invalid integration token');
}

$remoteAddress = isset($_SERVER['REMOTE_ADDR']) ? trim((string)$_SERVER['REMOTE_ADDR']) : '';
$allowedIps = app_integration_config('allowed_ips', array());
if (is_array($allowedIps) && count($allowedIps) > 0 && !in_array($remoteAddress, $allowedIps, true)) {
    app_integration_fail(403, 'forbidden', 'Source address is not allowed');
}

app_integration_enforce_rate_limit(
    'caller',
    $remoteAddress !== '' ? $remoteAddress : 'unknown',
    (int)app_integration_config('caller_rate_limit', 120),
    (int)app_integration_config('caller_rate_window_seconds', 60),
    $configuredToken
);

$maxBodyBytes = max(1024, min(65536, (int)app_integration_config('max_body_bytes', 16384)));
$contentLength = isset($_SERVER['CONTENT_LENGTH']) ? (int)$_SERVER['CONTENT_LENGTH'] : 0;
if ($contentLength > $maxBodyBytes) {
    app_integration_fail(413, 'payload_too_large', 'Request body is too large');
}

$rawPayload = file_get_contents('php://input');
if (!is_string($rawPayload) || strlen($rawPayload) > $maxBodyBytes) {
    app_integration_fail(413, 'payload_too_large', 'Request body is too large');
}

$payload = json_decode($rawPayload, true);
if (!is_array($payload)) {
    app_integration_fail(400, 'bad_json', 'Request body must be valid JSON');
}

$login = app_integration_require_string(isset($payload['login']) ? $payload['login'] : '', 'login', 200);
$password = app_integration_require_password(isset($payload['password']) ? $payload['password'] : null);

app_integration_enforce_rate_limit(
    'login',
    app_integration_lower($login),
    (int)app_integration_config('login_rate_limit', 10),
    (int)app_integration_config('login_rate_window_seconds', 900),
    $configuredToken
);

require $_SERVER['DOCUMENT_ROOT'] . '/bitrix/modules/main/include/prolog_before.php';

$GLOBALS['APP_INTEGRATION_CONN'] = \Bitrix\Main\Application::getConnection();
$GLOBALS['APP_INTEGRATION_SQLH'] = $GLOBALS['APP_INTEGRATION_CONN']->getSqlHelper();

try {
    $userId = app_integration_authenticate_user($login, $password);
    app_integration_respond(array(
        'user' => app_integration_get_user_profile($userId),
        'discounts' => app_integration_get_user_discounts($userId),
    ));
} catch (\Throwable $exception) {
    if (function_exists('AddMessage2Log')) {
        AddMessage2Log('app_integration internal error: ' . get_class($exception), 'app_integration');
    }
    app_integration_fail(500, 'internal_error', 'Unable to load website identity');
}

function app_integration_respond(array $data)
{
    http_response_code(200);
    echo json_encode(array('ok' => true, 'data' => $data), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function app_integration_fail($status, $error, $message)
{
    $messagesRu = array(
        'service_disabled' => 'Интеграция профиля сайта выключена.',
        'service_not_configured' => 'Интеграция профиля сайта не настроена.',
        'method_not_allowed' => 'Разрешены только POST-запросы.',
        'unauthorized' => 'Неверный токен интеграции или данные для входа.',
        'forbidden' => 'IP-адрес источника не разрешён.',
        'rate_limited' => 'Слишком много запросов.',
        'payload_too_large' => 'Тело запроса слишком большое.',
        'bad_json' => 'Тело запроса должно содержать корректный JSON.',
        'bad_login' => 'Укажите корректный email.',
        'bad_password' => 'Укажите корректный пароль.',
        'invalid_credentials' => 'Неверный email или пароль.',
        'user_not_found' => 'Пользователь не найден.',
        'rate_limit_unavailable' => 'Ограничение запросов недоступно.',
        'internal_error' => 'Не удалось загрузить профиль сайта.',
    );
    $messageRu = isset($messagesRu[$error]) ? $messagesRu[$error] : 'Не удалось выполнить запрос.';
    http_response_code((int)$status);
    echo json_encode(array(
        'ok' => false,
        'error' => (string)$error,
        'message' => (string)$message,
        'message_ru' => $messageRu,
        'message_en' => (string)$message,
    ), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function app_integration_config($key, $default = null)
{
    global $appIntegrationConfig;
    return array_key_exists($key, $appIntegrationConfig) ? $appIntegrationConfig[$key] : $default;
}

function app_integration_enforce_rate_limit($scope, $key, $limit, $windowSeconds, $secret)
{
    $limit = max(1, min(10000, (int)$limit));
    $windowSeconds = max(1, min(86400, (int)$windowSeconds));
    $directory = rtrim((string)app_integration_config('rate_limit_dir', ''), '/');
    if ($directory === '') {
        app_integration_fail(503, 'rate_limit_unavailable', 'Rate limiting is not configured');
    }
    if (!is_dir($directory) && !@mkdir($directory, 0700, true) && !is_dir($directory)) {
        app_integration_fail(503, 'rate_limit_unavailable', 'Rate limiting is unavailable');
    }

    $fileName = hash_hmac('sha256', (string)$scope . '|' . (string)$key, (string)$secret) . '.json';
    $handle = @fopen($directory . '/' . $fileName, 'c+');
    if ($handle === false || !flock($handle, LOCK_EX)) {
        if (is_resource($handle)) {
            fclose($handle);
        }
        app_integration_fail(503, 'rate_limit_unavailable', 'Rate limiting is unavailable');
    }

    $raw = stream_get_contents($handle);
    $decoded = is_string($raw) && $raw !== '' ? json_decode($raw, true) : array();
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
        app_integration_fail(429, 'rate_limited', 'Too many requests');
    }

    $active[] = $now;
    rewind($handle);
    ftruncate($handle, 0);
    fwrite($handle, json_encode($active));
    fflush($handle);
    @chmod($directory . '/' . $fileName, 0600);
    flock($handle, LOCK_UN);
    fclose($handle);
}

function app_integration_length($value)
{
    return function_exists('mb_strlen') ? mb_strlen((string)$value, 'UTF-8') : strlen((string)$value);
}

function app_integration_substring($value, $maxLength)
{
    $value = trim((string)$value);
    if (app_integration_length($value) <= $maxLength) {
        return $value;
    }
    return function_exists('mb_substr')
        ? mb_substr($value, 0, $maxLength, 'UTF-8')
        : substr($value, 0, $maxLength);
}

function app_integration_require_string($value, $fieldName, $maxLength)
{
    if (!is_scalar($value)) {
        app_integration_fail(422, 'bad_' . $fieldName, 'Field `' . $fieldName . '` is required');
    }
    $value = trim((string)$value);
    if ($value === '' || app_integration_length($value) > $maxLength) {
        app_integration_fail(422, 'bad_' . $fieldName, 'Field `' . $fieldName . '` is invalid');
    }
    return $value;
}

function app_integration_require_password($value)
{
    if (!is_scalar($value)) {
        app_integration_fail(422, 'bad_password', 'Field `password` is required');
    }
    $value = (string)$value;
    if ($value === '' || strlen($value) > 255) {
        app_integration_fail(422, 'bad_password', 'Field `password` is invalid');
    }
    return $value;
}

function app_integration_lower($value)
{
    return function_exists('mb_strtolower')
        ? mb_strtolower((string)$value, 'UTF-8')
        : strtolower((string)$value);
}

function app_integration_conn()
{
    return $GLOBALS['APP_INTEGRATION_CONN'];
}

function app_integration_sqlh()
{
    return $GLOBALS['APP_INTEGRATION_SQLH'];
}

function app_integration_query_row($sql)
{
    $row = app_integration_conn()->query($sql)->fetch();
    return is_array($row) ? app_integration_normalize_row($row) : null;
}

function app_integration_query_all($sql)
{
    $rows = array();
    $result = app_integration_conn()->query($sql);
    while ($row = $result->fetch()) {
        $rows[] = app_integration_normalize_row($row);
    }
    return $rows;
}

function app_integration_normalize_row(array $row)
{
    foreach ($row as $key => $value) {
        if ($value instanceof \Bitrix\Main\Type\DateTime || $value instanceof \DateTimeInterface) {
            $row[$key] = $value->format(DATE_ATOM);
        } elseif (is_object($value) && method_exists($value, '__toString')) {
            $row[$key] = (string)$value;
        }
    }
    return $row;
}

function app_integration_authenticate_user($login, $password)
{
    $authUser = new CUser();
    $authResult = $authUser->Login((string)$login, (string)$password, 'N', 'Y');
    if ($authResult !== true || !$authUser->IsAuthorized()) {
        app_integration_fail(401, 'invalid_credentials', 'Invalid login or password');
    }
    $userId = (int)$authUser->GetID();
    $authUser->Logout();
    if ($userId <= 0) {
        app_integration_fail(401, 'invalid_credentials', 'Invalid login or password');
    }
    return $userId;
}

function app_integration_get_user_profile($userId)
{
    $user = app_integration_query_row(
        "SELECT ID, LOGIN, NAME, LAST_NAME, SECOND_NAME, EMAIL, PERSONAL_PHONE, PERSONAL_MOBILE, PERSONAL_CITY, DATE_REGISTER, LAST_LOGIN
         FROM b_user WHERE ID=" . (int)$userId . " LIMIT 1"
    );
    if (!$user) {
        app_integration_fail(404, 'user_not_found', 'User not found');
    }

    $groupRows = app_integration_query_all(
        "SELECT g.ID, g.NAME FROM b_user_group ug
         INNER JOIN b_group g ON g.ID=ug.GROUP_ID
         WHERE ug.USER_ID=" . (int)$userId . " ORDER BY g.ID ASC"
    );
    $groupIds = array();
    $groupNames = array();
    foreach ($groupRows as $row) {
        $groupIds[] = (int)$row['ID'];
        $groupNames[] = app_integration_substring($row['NAME'], 255);
    }

    return array(
        'id' => (int)$userId,
        'login' => app_integration_substring($user['LOGIN'], 120),
        'name' => app_integration_substring($user['NAME'], 120),
        'last_name' => app_integration_substring($user['LAST_NAME'], 120),
        'second_name' => app_integration_substring($user['SECOND_NAME'], 120),
        'email' => app_integration_substring($user['EMAIL'], 190),
        'personal_phone' => app_integration_substring($user['PERSONAL_PHONE'], 80),
        'personal_mobile' => app_integration_substring($user['PERSONAL_MOBILE'], 80),
        'personal_city' => app_integration_substring($user['PERSONAL_CITY'], 120),
        'date_register' => isset($user['DATE_REGISTER']) ? $user['DATE_REGISTER'] : null,
        'last_login' => isset($user['LAST_LOGIN']) ? $user['LAST_LOGIN'] : null,
        'group_ids' => $groupIds,
        'group_names' => $groupNames,
        'custom_fields' => app_integration_load_custom_fields($userId),
    );
}

function app_integration_load_custom_fields($userId)
{
    $row = app_integration_query_row("SELECT * FROM b_uts_user WHERE VALUE_ID=" . (int)$userId . " LIMIT 1");
    if (!$row) {
        return array();
    }
    $allowlist = app_integration_config('custom_field_allowlist', array());
    $result = array();
    foreach ($allowlist as $fieldName) {
        $fieldName = strtoupper(trim((string)$fieldName));
        if (strpos($fieldName, 'UF_') !== 0 || !array_key_exists($fieldName, $row)) {
            continue;
        }
        $value = app_integration_substring($row[$fieldName], 2000);
        if ($value !== '') {
            $result[$fieldName] = $value;
        }
    }
    return $result;
}

function app_integration_parse_money($value)
{
    $value = app_integration_substring($value, 255);
    if ($value === '') {
        return null;
    }
    $parts = explode('|', $value, 2);
    return array(
        'raw' => $value,
        'amount' => isset($parts[0]) && is_numeric($parts[0]) ? round((float)$parts[0], 2) : null,
        'currency' => isset($parts[1]) && trim($parts[1]) !== '' ? app_integration_substring($parts[1], 16) : null,
    );
}

function app_integration_load_referral_program($userId)
{
    $row = app_integration_query_row(
        "SELECT
            current_user.UF_PROMO,
            current_user.UF_PARENT_ID,
            current_user.UF_PERCENT,
            current_user.UF_ORDER_SUMM,
            current_user.UF_SUM_PAID_ORDERS_MONTH,
            parent_user.UF_PROMO AS REFERRER_PROMO_CODE
         FROM b_uts_user current_user
         LEFT JOIN b_uts_user parent_user
            ON parent_user.VALUE_ID=current_user.UF_PARENT_ID
         WHERE current_user.VALUE_ID=" . (int)$userId . "
         LIMIT 1"
    );
    if (!$row) {
        return null;
    }
    return array(
        'promo_code' => app_integration_substring($row['UF_PROMO'], 255) ?: null,
        'parent_user_id' => is_numeric($row['UF_PARENT_ID']) ? (int)$row['UF_PARENT_ID'] : null,
        'referrer_promo_code' => app_integration_substring($row['REFERRER_PROMO_CODE'], 255) ?: null,
        'percent' => is_numeric($row['UF_PERCENT']) ? (float)$row['UF_PERCENT'] : null,
        'order_sum' => app_integration_parse_money($row['UF_ORDER_SUMM']),
        'sum_paid_orders_month' => app_integration_parse_money($row['UF_SUM_PAID_ORDERS_MONTH']),
    );
}

function app_integration_load_bonus_account($userId)
{
    if (!app_integration_conn()->isTableExists('sotbit_bonuses_account')) {
        return null;
    }
    $row = app_integration_query_row(
        "SELECT ID, USER_ID, DATE_CREATE, ACTIVE, BALANCE
         FROM sotbit_bonuses_account WHERE USER_ID=" . (int)$userId . " LIMIT 1"
    );
    if (!$row) {
        return null;
    }
    return array(
        'id' => (int)$row['ID'],
        'user_id' => (int)$row['USER_ID'],
        'date_create' => isset($row['DATE_CREATE']) ? $row['DATE_CREATE'] : null,
        'active' => (string)$row['ACTIVE'] === 'Y',
        'balance' => round((float)$row['BALANCE'], 2),
    );
}

function app_integration_load_discount_groups($userId)
{
    $rows = app_integration_query_all(
        "SELECT g.ID, g.NAME FROM b_user_group ug
         INNER JOIN b_group g ON g.ID=ug.GROUP_ID
         WHERE ug.USER_ID=" . (int)$userId . " ORDER BY g.ID ASC"
    );
    $result = array();
    foreach ($rows as $row) {
        $name = app_integration_substring($row['NAME'], 255);
        $normalized = app_integration_lower($name);
        if (strpos($normalized, 'скид') === false && strpos($normalized, 'discount') === false && strpos($normalized, 'bonus') === false && strpos($normalized, 'бонус') === false) {
            continue;
        }
        $result[] = array('id' => (int)$row['ID'], 'name' => $name);
    }
    return $result;
}

function app_integration_load_active_coupons($userId)
{
    $now = app_integration_sqlh()->forSql(date('Y-m-d H:i:s'));
    $rows = app_integration_query_all(
        "SELECT c.ID, c.COUPON, c.TYPE, c.MAX_USE, c.USE_COUNT, c.DATE_APPLY, c.DATE_CREATE, c.DESCRIPTION,
                d.ID AS DISCOUNT_ID, d.NAME AS DISCOUNT_NAME, d.SHORT_DESCRIPTION, d.DISCOUNT_VALUE, d.CURRENCY
         FROM b_sale_discount_coupon c LEFT JOIN b_sale_discount d ON d.ID=c.DISCOUNT_ID
         WHERE c.USER_ID=" . (int)$userId . " AND c.ACTIVE='Y'
           AND (c.ACTIVE_FROM IS NULL OR c.ACTIVE_FROM <= '" . $now . "')
           AND (c.ACTIVE_TO IS NULL OR c.ACTIVE_TO >= '" . $now . "')
           AND (c.MAX_USE=0 OR c.USE_COUNT<c.MAX_USE)
         ORDER BY c.DATE_CREATE DESC, c.ID DESC LIMIT 50"
    );
    $result = array();
    foreach ($rows as $row) {
        $result[] = array(
            'id' => (int)$row['ID'],
            'coupon' => app_integration_substring($row['COUPON'], 255),
            'type' => (int)$row['TYPE'],
            'max_use' => (int)$row['MAX_USE'],
            'use_count' => (int)$row['USE_COUNT'],
            'date_apply' => isset($row['DATE_APPLY']) ? $row['DATE_APPLY'] : null,
            'date_create' => isset($row['DATE_CREATE']) ? $row['DATE_CREATE'] : null,
            'description' => app_integration_substring($row['DESCRIPTION'], 2000),
            'discount' => array(
                'id' => isset($row['DISCOUNT_ID']) ? (int)$row['DISCOUNT_ID'] : null,
                'name' => app_integration_substring($row['DISCOUNT_NAME'], 255),
                'short_description' => app_integration_substring($row['SHORT_DESCRIPTION'], 2000),
                'value' => is_numeric($row['DISCOUNT_VALUE']) ? (float)$row['DISCOUNT_VALUE'] : null,
                'currency' => app_integration_substring($row['CURRENCY'], 16),
            ),
        );
    }
    return $result;
}

function app_integration_load_recent_used_coupons($userId)
{
    $rows = app_integration_query_all(
        "SELECT oc.COUPON, oc.TYPE, oc.COUPON_ID, oc.ORDER_ID, o.ACCOUNT_NUMBER, o.DATE_INSERT, o.STATUS_ID,
                od.NAME AS DISCOUNT_NAME
         FROM b_sale_order_coupons oc INNER JOIN b_sale_order o ON o.ID=oc.ORDER_ID
         LEFT JOIN b_sale_order_discount od ON od.ID=oc.ORDER_DISCOUNT_ID
         WHERE o.USER_ID=" . (int)$userId . " ORDER BY o.DATE_INSERT DESC, oc.ID DESC LIMIT 20"
    );
    $result = array();
    foreach ($rows as $row) {
        $result[] = array(
            'coupon' => app_integration_substring($row['COUPON'], 255),
            'type' => (int)$row['TYPE'],
            'coupon_id' => (int)$row['COUPON_ID'],
            'order_id' => (int)$row['ORDER_ID'],
            'account_number' => app_integration_substring($row['ACCOUNT_NUMBER'], 64),
            'date_insert' => isset($row['DATE_INSERT']) ? $row['DATE_INSERT'] : null,
            'status_id' => app_integration_substring($row['STATUS_ID'], 16),
            'discount_name' => app_integration_substring($row['DISCOUNT_NAME'], 255),
        );
    }
    return $result;
}

function app_integration_get_user_discounts($userId)
{
    return array(
        'referral_program' => app_integration_load_referral_program($userId),
        'bonus_account' => app_integration_load_bonus_account($userId),
        'discount_groups' => app_integration_load_discount_groups($userId),
        'active_coupons' => app_integration_load_active_coupons($userId),
        'recent_used_coupons' => app_integration_load_recent_used_coupons($userId),
    );
}
