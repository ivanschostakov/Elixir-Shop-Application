<?php

declare(strict_types=1);

if ($argc !== 6) {
    fwrite(
        STDERR,
        "Usage: php install_catalog_sync.php <document-root> <secret-file> <app-ip> <private-root> <catalog-iblock-id>\n"
    );
    exit(2);
}

$documentRoot = rtrim((string)$argv[1], '/');
$secretFile = (string)$argv[2];
$appIp = trim((string)$argv[3]);
$privateRoot = rtrim((string)$argv[4], '/');
$catalogIblockId = max(1, (int)$argv[5]);
$secret = trim((string)@file_get_contents($secretFile));

if (
    !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')
    || !is_file($documentRoot . '/local/modules/elixir.catalogsync/install/index.php')
    || strlen($secret) < 32
    || filter_var($appIp, FILTER_VALIDATE_IP) === false
    || $privateRoot === ''
) {
    fwrite(STDERR, "Invalid catalog sync deployment parameters\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
$_SERVER['SERVER_NAME'] = 'elixirpeptide.com';
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);

require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';
require_once $documentRoot . '/local/modules/elixir.catalogsync/install/index.php';

use Bitrix\Main\Config\Option;
use Bitrix\Main\ModuleManager;

Option::set('elixir.catalogsync', 'catalog_iblock_id', (string)$catalogIblockId);
$module = new elixir_catalogsync();
if (ModuleManager::isModuleInstalled('elixir.catalogsync')) {
    $module->InstallProperties();
    $module->InstallFiles();
    echo "MODULE_REFRESHED=elixir.catalogsync\n";
} else {
    $module->DoInstall();
    echo "MODULE_INSTALLED=elixir.catalogsync\n";
}

$options = [
    'enabled' => 'Y',
    'shared_secret' => $secret,
    'allowed_ips' => $appIp,
    'rate_limit' => '60',
    'rate_limit_window_seconds' => '60',
    'private_dir' => $privateRoot . '/elixir-catalogsync',
    'catalog_iblock_id' => (string)$catalogIblockId,
];
foreach ($options as $name => $value) {
    Option::set('elixir.catalogsync', $name, $value);
}

echo "CONFIGURED=elixir.catalogsync\n";
