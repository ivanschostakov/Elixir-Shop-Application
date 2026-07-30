<?php

declare(strict_types=1);

if ($argc !== 3) {
    fwrite(STDERR, "Usage: php seed_catalog_content.php <document-root> <seed-json>\n");
    exit(2);
}

$documentRoot = rtrim((string)$argv[1], '/');
$seedPath = (string)$argv[2];
if (
    !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')
    || !is_file($seedPath)
    || filesize($seedPath) <= 0
    || filesize($seedPath) > 52428800
) {
    fwrite(STDERR, "Invalid catalog seed parameters\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;

if (!Loader::includeModule('iblock') || !Loader::includeModule('elixir.catalogsync')) {
    throw new RuntimeException('Required Bitrix modules are unavailable');
}

$decoded = json_decode((string)file_get_contents($seedPath), true);
$rows = is_array($decoded['products'] ?? null) ? $decoded['products'] : null;
if ($rows === null || count($rows) > 500) {
    throw new RuntimeException('Catalog seed payload is invalid');
}

$iblockId = max(1, (int)Option::get('elixir.catalogsync', 'catalog_iblock_id', '21'));
$mapping = [
    'description' => 'ELIXIR_APP_DESCRIPTION',
    'usage' => 'ELIXIR_APP_USAGE',
    'storage' => 'ELIXIR_APP_STORAGE',
];
$systemIdProperty = 'ELIXIR_APP_SYSTEM_ID';
function elixirCatalogSeedNormalizeSku(mixed $value): string
{
    if (!is_scalar($value)) {
        return '';
    }
    return mb_strtolower(trim((string)$value), 'UTF-8');
}

$stats = [
    'input_products' => count($rows),
    'matched_products' => 0,
    'matched_by_system_id' => 0,
    'matched_by_sku' => 0,
    'missing_products' => 0,
    'invalid_system_ids' => 0,
    'duplicate_bitrix_system_ids' => 0,
    'ambiguous_bitrix_skus' => 0,
    'seeded_system_id' => 0,
    'kept_system_id' => 0,
    'system_id_conflicts' => 0,
    'seeded_description' => 0,
    'seeded_usage' => 0,
    'seeded_storage' => 0,
    'kept_existing_fields' => 0,
];

$elementIdsBySystemId = [];
$bitrixElementIds = [];
$elements = \CIBlockElement::GetList(
    ['ID' => 'ASC'],
    ['IBLOCK_ID' => $iblockId],
    false,
    false,
    ['ID', 'XML_ID']
);
while ($element = $elements->Fetch()) {
    $elementId = (int)$element['ID'];
    $bitrixElementIds[] = $elementId;
    $systemId = strtolower(trim((string)($element['XML_ID'] ?? '')));
    if (preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/D', $systemId) !== 1) {
        continue;
    }
    $elementIdsBySystemId[$systemId][] = $elementId;
}

$current = [];
\CIBlockElement::GetPropertyValuesArray(
    $current,
    $iblockId,
    ['ID' => $bitrixElementIds],
    ['CODE' => array_merge(array_values($mapping), [$systemIdProperty, 'CML2_ARTICLE'])]
);
$elementIdsBySku = [];
foreach ($bitrixElementIds as $elementId) {
    $sku = elixirCatalogSeedNormalizeSku($current[$elementId]['CML2_ARTICLE']['VALUE'] ?? null);
    if ($sku !== '') {
        $elementIdsBySku[$sku][] = $elementId;
    }
}

foreach ($rows as $row) {
    if (!is_array($row)) {
        $stats['invalid_system_ids']++;
        continue;
    }
    $systemId = strtolower(trim((string)($row['system_id'] ?? '')));
    if (preg_match('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/D', $systemId) !== 1) {
        $stats['invalid_system_ids']++;
        continue;
    }
    $matches = $elementIdsBySystemId[$systemId] ?? [];
    if (count($matches) > 1) {
        $stats['duplicate_bitrix_system_ids']++;
        continue;
    }
    if (count($matches) === 1) {
        $elementId = $matches[0];
        $stats['matched_by_system_id']++;
    } else {
        $sku = elixirCatalogSeedNormalizeSku($row['sku'] ?? null);
        $skuMatches = $sku === '' ? [] : ($elementIdsBySku[$sku] ?? []);
        if (count($skuMatches) > 1) {
            $stats['ambiguous_bitrix_skus']++;
            continue;
        }
        if (count($skuMatches) !== 1) {
            $stats['missing_products']++;
            continue;
        }
        $elementId = $skuMatches[0];
        $stats['matched_by_sku']++;
    }
    $updates = [];
    $existingSystemId = strtolower(trim((string)(
        $current[$elementId][$systemIdProperty]['VALUE'] ?? ''
    )));
    if ($existingSystemId !== '' && $existingSystemId !== $systemId) {
        $stats['system_id_conflicts']++;
        continue;
    }
    if ($existingSystemId === '') {
        $updates[$systemIdProperty] = $systemId;
        $stats['seeded_system_id']++;
    } else {
        $stats['kept_system_id']++;
    }
    foreach ($mapping as $sourceField => $propertyCode) {
        $incoming = $row[$sourceField] ?? null;
        if (!is_string($incoming)) {
            continue;
        }
        $incoming = trim(str_replace("\0", '', $incoming));
        if ($incoming === '' || mb_strlen($incoming) > 200000) {
            continue;
        }
        $existing = $current[$elementId][$propertyCode]['VALUE'] ?? null;
        if (is_array($existing) && array_key_exists('TEXT', $existing)) {
            $existing = $existing['TEXT'];
        }
        if (is_scalar($existing) && trim((string)$existing) !== '') {
            $stats['kept_existing_fields']++;
            continue;
        }
        $updates[$propertyCode] = [
            'VALUE' => [
                'TEXT' => $incoming,
                'TYPE' => 'HTML',
            ],
        ];
        $stats['seeded_' . $sourceField]++;
    }
    if ($updates !== []) {
        \CIBlockElement::SetPropertyValuesEx($elementId, $iblockId, $updates);
    }
    $stats['matched_products']++;
}

echo json_encode(['ok' => true, 'stats' => $stats], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) . PHP_EOL;
