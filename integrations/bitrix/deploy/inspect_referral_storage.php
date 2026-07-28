<?php

declare(strict_types=1);

$documentRoot = rtrim((string)getenv('ELIXIR_BITRIX_DOCUMENT_ROOT'), '/');
if ($documentRoot === '' || !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')) {
    fwrite(STDERR, "Invalid Bitrix document root\n");
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

$connection = Application::getConnection();
$tables = [];
foreach (['b_elixir_referral_app_purchase', 'b_elixir_referral_app_accrual'] as $tableName) {
    $exists = $connection->isTableExists($tableName);
    $count = 0;
    if ($exists) {
        $row = $connection->query("SELECT COUNT(*) AS CNT FROM {$tableName}")->fetch();
        $count = (int)($row['CNT'] ?? 0);
    }
    $tables[$tableName] = ['exists' => $exists, 'rows' => $count];
}

$agentRow = $connection->query(
    "SELECT COUNT(*) AS CNT
     FROM b_agent
     WHERE MODULE_ID='elixir.promo'
       AND NAME='\\\\Elixir\\\\Promo\\\\Service\\\\ReferralAccrualService::finalizePreviousMonthAgent();'"
)->fetch();

$properties = [];
if (Loader::includeModule('iblock')) {
    foreach (['SOURCE_KEY', 'STATUS', 'PERIOD', 'LEVEL'] as $code) {
        $property = \CIBlockProperty::GetList([], ['IBLOCK_ID' => 20, 'CODE' => $code])->Fetch();
        $properties[$code] = is_array($property);
    }
}

echo json_encode(
    [
        'module_version' => (string)\Bitrix\Main\ModuleManager::getVersion('elixir.promo'),
        'tables' => $tables,
        'legacy_agent_count' => (int)($agentRow['CNT'] ?? 0),
        'legacy_properties' => $properties,
    ],
    JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
) . PHP_EOL;
