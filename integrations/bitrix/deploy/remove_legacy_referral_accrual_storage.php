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

if (!\Bitrix\Main\Loader::includeModule('elixir.promo')) {
    throw new RuntimeException('elixir.promo is unavailable');
}

$result = (new \Elixir\Promo\Service\ReferralAccrualService())
    ->removeLegacyAccrualStorage();
echo json_encode(
    ['ok' => true, 'result' => $result],
    JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
) . PHP_EOL;
