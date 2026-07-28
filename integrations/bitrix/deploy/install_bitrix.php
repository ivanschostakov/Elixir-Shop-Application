<?php

declare(strict_types=1);

$documentRoot = rtrim((string)getenv('ELIXIR_BITRIX_DOCUMENT_ROOT'), '/');
if ($documentRoot === '' || !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')) {
    fwrite(STDERR, "Invalid Bitrix document root\n");
    exit(2);
}

$requiredSecrets = [
    'ELIXIR_PROMO_TOKEN',
    'ELIXIR_REVIEW_SECRET',
    'ELIXIR_APP_TOKEN',
    'ELIXIR_GIVEAWAY_TOKEN',
];
foreach ($requiredSecrets as $name) {
    if (strlen(trim((string)getenv($name))) < 32) {
        fwrite(STDERR, "Missing or weak secret: {$name}\n");
        exit(2);
    }
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
$_SERVER['SERVER_NAME'] = 'elixirpeptide.com';
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);

require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Config\Option;
use Bitrix\Main\ModuleManager;

function installOrRefreshModule(string $documentRoot, string $moduleId, string $className): void
{
    $installer = $documentRoot . '/local/modules/' . $moduleId . '/install/index.php';
    if (!is_file($installer)) {
        throw new RuntimeException('Missing module installer: ' . $moduleId);
    }
    require_once $installer;
    $module = new $className();
    if (ModuleManager::isModuleInstalled($moduleId)) {
        if (method_exists($module, 'InstallDB')) {
            $module->InstallDB();
        }
        if (method_exists($module, 'InstallAgents')) {
            $module->InstallAgents();
        }
        $module->InstallFiles();
        echo 'MODULE_REFRESHED=' . $moduleId . PHP_EOL;
        return;
    }
    $module->DoInstall();
    echo 'MODULE_INSTALLED=' . $moduleId . PHP_EOL;
}

function writePhpConfig(string $path, array $config): void
{
    $directory = dirname($path);
    $owner = fileowner($directory);
    $group = filegroup($directory);
    $temporaryPath = $path . '.elixir-new';
    $contents = "<?php\n\nreturn " . var_export($config, true) . ";\n";
    if (file_put_contents($temporaryPath, $contents, LOCK_EX) === false) {
        throw new RuntimeException('Unable to write config: ' . $path);
    }
    chmod($temporaryPath, 0640);
    if (!rename($temporaryPath, $path)) {
        @unlink($temporaryPath);
        throw new RuntimeException('Unable to activate config: ' . $path);
    }
    if ($owner !== false) {
        chown($path, $owner);
    }
    if ($group !== false) {
        chgrp($path, $group);
    }
}

installOrRefreshModule($documentRoot, 'elixir.promo', 'elixir_promo');
installOrRefreshModule($documentRoot, 'elixir.reviewsync', 'elixir_reviewsync');

$appIp = trim((string)getenv('ELIXIR_APP_IP'));
$giveawayIp = trim((string)getenv('ELIXIR_GIVEAWAY_IP'));
$privateRoot = rtrim((string)getenv('ELIXIR_PRIVATE_ROOT'), '/');
if ($privateRoot === '') {
    $privateRoot = dirname($documentRoot) . '/private';
}
if (!is_dir($privateRoot) && !mkdir($privateRoot, 0750, true) && !is_dir($privateRoot)) {
    throw new RuntimeException('Unable to create private runtime directory');
}

$promoOptions = [
    'enabled' => 'Y',
    'auto_create_enabled' => 'Y',
    'api_token' => trim((string)getenv('ELIXIR_PROMO_TOKEN')),
    'allowed_ips' => $appIp,
    'discount_id' => '24',
    'catalog_iblock_id' => '2',
    'offers_iblock_id' => '3',
    'site_id' => 's1',
    'person_type_id' => '1',
    'currency' => 'RUB',
    'rate_limit' => '300',
    'rate_limit_window_seconds' => '60',
    'max_items' => '100',
    'private_dir' => $privateRoot . '/elixir-promo',
];
foreach ($promoOptions as $name => $value) {
    Option::set('elixir.promo', $name, $value);
}

$reviewOptions = [
    'shared_secret' => trim((string)getenv('ELIXIR_REVIEW_SECRET')),
    'allowed_ips' => $appIp,
    'rate_limit' => '120',
    'rate_limit_window_seconds' => '60',
    'private_dir' => $privateRoot . '/elixir-reviewsync',
    'app_media_base_url' => 'https://api-elixirshop.devsivanschostakov.org/media/reviews',
    'site_public_base_url' => 'https://elixirpeptide.com',
];
foreach ($reviewOptions as $name => $value) {
    Option::set('elixir.reviewsync', $name, $value);
}

$apiDirectory = $documentRoot . '/local/api';
if (!is_dir($apiDirectory) && !mkdir($apiDirectory, 0750, true) && !is_dir($apiDirectory)) {
    throw new RuntimeException('Unable to create local API directory');
}

writePhpConfig($apiDirectory . '/app_integration.config.php', [
    'enabled' => true,
    'token' => trim((string)getenv('ELIXIR_APP_TOKEN')),
    'allowed_ips' => [$appIp],
    'max_body_bytes' => 16384,
    'caller_rate_limit' => 120,
    'caller_rate_window_seconds' => 60,
    'login_rate_limit' => 10,
    'login_rate_window_seconds' => 900,
    'rate_limit_dir' => $privateRoot . '/app-integration-rate-limit',
    'custom_field_allowlist' => [
        'UF_PROMO',
        'UF_PARENT_ID',
        'UF_PERCENT',
        'UF_ORDER_SUMM',
        'UF_SUM_PAID_ORDERS_MONTH',
    ],
]);

writePhpConfig($apiDirectory . '/giveaways.config.php', [
    'enabled' => true,
    'token' => trim((string)getenv('ELIXIR_GIVEAWAY_TOKEN')),
    'allowed_ips' => [$giveawayIp],
    'rate_limit' => 120,
    'rate_limit_window_seconds' => 60,
    'rate_limit_dir' => $privateRoot . '/giveaways-api-rate-limit',
]);

echo "CONFIGURED=promo,reviews,app,giveaway\n";
