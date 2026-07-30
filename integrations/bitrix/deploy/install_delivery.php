<?php

declare(strict_types=1);

if ($argc !== 5) {
    fwrite(STDERR, "Usage: php install_delivery.php <document-root> <secret-file> <app-ip> <private-root>\n");
    exit(2);
}

$documentRoot = rtrim((string)$argv[1], '/');
$secretFile = (string)$argv[2];
$appIp = trim((string)$argv[3]);
$privateRoot = rtrim((string)$argv[4], '/');
$secret = trim((string)@file_get_contents($secretFile));

if (
    !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')
    || !is_file($documentRoot . '/local/modules/elixir.delivery/install/index.php')
    || strlen($secret) < 32
    || filter_var($appIp, FILTER_VALIDATE_IP) === false
    || $privateRoot === ''
) {
    fwrite(STDERR, "Invalid delivery deployment parameters\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
$_SERVER['SERVER_NAME'] = 'elixirpeptide.com';
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);

require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';
require_once $documentRoot . '/local/modules/elixir.delivery/install/index.php';

use Bitrix\Main\Config\Option;
use Bitrix\Main\ModuleManager;

$module = new elixir_delivery();
if (ModuleManager::isModuleInstalled('elixir.delivery')) {
    $module->InstallFiles();
    echo "MODULE_REFRESHED=elixir.delivery\n";
} else {
    $module->DoInstall();
    echo "MODULE_INSTALLED=elixir.delivery\n";
}

$options = [
    'enabled' => 'Y',
    'shared_secret' => $secret,
    'allowed_ips' => $appIp,
    'rate_limit' => '120',
    'rate_limit_window_seconds' => '60',
    'max_items' => '100',
    'private_dir' => $privateRoot . '/elixir-delivery',
    'site_id' => 's1',
    'person_type_id' => '1',
    'currency' => 'RUB',
    'pickup_service_code' => 'sdek:pickup',
    'courier_service_code' => 'sdek:courier',
];
foreach ($options as $name => $value) {
    Option::set('elixir.delivery', $name, $value);
}

echo "CONFIGURED=elixir.delivery\n";
