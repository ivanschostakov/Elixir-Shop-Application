<?php
return array(
    // Keep disabled until a dedicated token and backend IP are configured.
    'enabled' => false,
    'token' => '',
    'allow_legacy_body_token' => false,
    // Optional exact source IP allowlist. Leave empty to rely on the token.
    'allowed_ips' => array(),
    'max_body_bytes' => 1048576,
    'catalog_iblock_id' => 2,
    'offers_iblock_id' => 3,
    'price_group_id' => 1,
    'default_orders_limit' => 5,
    'max_orders_limit' => 10,
    'default_search_limit' => 10,
    'default_content_limit' => 5,
    'max_content_limit' => 10,
    'min_ai_order_total_rub' => 9000.0,
);
