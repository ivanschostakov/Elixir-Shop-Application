<?php

return array(
    // Keep disabled until a strong token is configured.
    'enabled' => false,
    // Required. The caller sends the same value in X-App-Integration-Token.
    'token' => '',
    // Optional exact source IP allowlist. Leave empty to rely on the token.
    'allowed_ips' => array(),
    'max_body_bytes' => 16384,
    'caller_rate_limit' => 120,
    'caller_rate_window_seconds' => 60,
    'login_rate_limit' => 10,
    'login_rate_window_seconds' => 900,
    // Must be outside public_html and writable by the site's PHP-FPM user.
    'rate_limit_dir' => dirname($_SERVER['DOCUMENT_ROOT']) . '/private/app-integration-rate-limit',
    // Only explicitly approved Bitrix custom fields are returned.
    'custom_field_allowlist' => array(
        'UF_PROMO',
        'UF_PARENT_ID',
        'UF_PERCENT',
        'UF_ORDER_SUMM',
        'UF_SUM_PAID_ORDERS_MONTH',
    ),
);
