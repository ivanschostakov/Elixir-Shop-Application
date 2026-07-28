<?php

declare(strict_types=1);

if ($argc !== 3) {
    fwrite(STDERR, "Usage: php deploy_referral_upgrade.php <document-root> <release-root>\n");
    exit(2);
}

$documentRoot = rtrim((string)$argv[1], '/');
$releaseRoot = rtrim((string)$argv[2], '/');
$sourceModule = $releaseRoot . '/integrations/bitrix/elixir.promo';
if (
    !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')
    || !is_file($sourceModule . '/install/index.php')
) {
    fwrite(STDERR, "Invalid deployment paths\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
$_SERVER['SERVER_NAME'] = 'elixirpeptide.com';
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Application;
use Bitrix\Main\Loader;
use Bitrix\Main\ModuleManager;

function copyTreeAtomically(string $source, string $destination): void
{
    if (!is_dir($source)) {
        throw new RuntimeException('Missing source directory: ' . $source);
    }
    if (!is_dir($destination) && !mkdir($destination, 0755, true) && !is_dir($destination)) {
        throw new RuntimeException('Could not create directory: ' . $destination);
    }

    $targetOwner = fileowner($destination);
    $targetGroup = filegroup($destination);
    $iterator = new RecursiveIteratorIterator(
        new RecursiveDirectoryIterator($source, FilesystemIterator::SKIP_DOTS),
        RecursiveIteratorIterator::SELF_FIRST
    );
    foreach ($iterator as $item) {
        $relative = substr($item->getPathname(), strlen($source) + 1);
        $target = $destination . '/' . $relative;
        if ($item->isDir()) {
            if (!is_dir($target) && !mkdir($target, 0755, true) && !is_dir($target)) {
                throw new RuntimeException('Could not create directory: ' . $target);
            }
            continue;
        }

        $temporary = $target . '.elixir-new';
        if (!copy($item->getPathname(), $temporary)) {
            throw new RuntimeException('Could not copy file: ' . $relative);
        }
        chmod($temporary, $item->getPerms() & 0777);
        if ($targetOwner !== false) {
            chown($temporary, $targetOwner);
        }
        if ($targetGroup !== false) {
            chgrp($temporary, $targetGroup);
        }
        if (!rename($temporary, $target)) {
            @unlink($temporary);
            throw new RuntimeException('Could not activate file: ' . $relative);
        }
    }
}

if (!ModuleManager::isModuleInstalled('elixir.promo')) {
    throw new RuntimeException('elixir.promo is not installed');
}

$targetModule = $documentRoot . '/local/modules/elixir.promo';
copyTreeAtomically($sourceModule, $targetModule);

require_once $targetModule . '/install/index.php';
$module = new elixir_promo();
$module->InstallDB();
$module->InstallFiles();

if (!Loader::includeModule('elixir.promo')) {
    throw new RuntimeException('Could not load upgraded elixir.promo module');
}
foreach ([
    \Elixir\Promo\Service\PromoService::class,
    \Elixir\Promo\Service\SiteDiscountContext::class,
    \Elixir\Promo\Service\ReferralAccrualService::class,
] as $className) {
    if (!class_exists($className)) {
        throw new RuntimeException('Upgraded class is unavailable: ' . $className);
    }
}

$connection = Application::getConnection();
foreach ([
    'b_elixir_referral_app_purchase',
] as $tableName) {
    if (!$connection->isTableExists($tableName)) {
        throw new RuntimeException('Missing referral table: ' . $tableName);
    }
}

if (function_exists('opcache_reset')) {
    @opcache_reset();
}
if (function_exists('BXClearCache')) {
    BXClearCache(true);
}

echo json_encode([
    'ok' => true,
    'module' => 'elixir.promo',
    'version' => $module->MODULE_VERSION,
    'tables' => [
        'b_elixir_referral_app_purchase',
    ],
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL;
