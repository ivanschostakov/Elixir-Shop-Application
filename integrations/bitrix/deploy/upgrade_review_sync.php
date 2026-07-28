<?php

declare(strict_types=1);

use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Bitrix\Main\ModuleManager;

$documentRoot = rtrim((string)getenv('BITRIX_DOCUMENT_ROOT'), '/');
if ($documentRoot === '' || !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')) {
    throw new RuntimeException('BITRIX_DOCUMENT_ROOT is invalid');
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

if (!ModuleManager::isModuleInstalled('elixir.reviewsync')) {
    throw new RuntimeException('elixir.reviewsync is not installed');
}
if (!Loader::includeModule('sotbit.reviews')) {
    throw new RuntimeException('sotbit.reviews is not installed');
}

require_once $documentRoot . '/local/modules/elixir.reviewsync/install/index.php';
$module = new elixir_reviewsync();
$module->InstallFiles();

Option::set(
    'elixir.reviewsync',
    'app_media_base_url',
    'https://api-elixirshop.devsivanschostakov.org/media/reviews'
);
Option::set(
    'elixir.reviewsync',
    'site_public_base_url',
    'https://elixirpeptide.com'
);

echo json_encode([
    'ok' => true,
    'module' => 'elixir.reviewsync',
    'version' => $module->MODULE_VERSION,
    'endpoint' => '/bitrix/tools/elixir.reviewsync/sync.php',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL;
