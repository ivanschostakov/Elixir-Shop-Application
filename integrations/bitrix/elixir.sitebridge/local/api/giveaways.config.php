<?php

return array(
    // Keep disabled until the existing bot is confirmed and a dedicated token is configured.
    'enabled' => false,
    // Required. Send the same secret in X-Giveaway-Token or the legacy JSON token field.
    'token' => '',
    // Keep empty only during local development. Production must list the giveaway server address.
    'allowed_ips' => array(),
    'rate_limit' => 120,
    'rate_limit_window_seconds' => 60,
    // Required in production and must be outside the public document root.
    'rate_limit_dir' => '',
);
