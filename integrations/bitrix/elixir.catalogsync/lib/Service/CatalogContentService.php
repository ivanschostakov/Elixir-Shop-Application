<?php

declare(strict_types=1);

namespace Elixir\CatalogSync\Service;

use Bitrix\Main\Application;
use Bitrix\Main\Config\Option;

final class CatalogContentService
{
    private const MODULE_ID = 'elixir.catalogsync';
    private const DESCRIPTION_PROPERTY = 'ELIXIR_APP_DESCRIPTION';
    private const USAGE_PROPERTY = 'ELIXIR_APP_USAGE';
    private const STORAGE_PROPERTY = 'ELIXIR_APP_STORAGE';
    private const SYSTEM_ID_PROPERTY = 'ELIXIR_APP_SYSTEM_ID';
    private const SKU_PROPERTY = 'CML2_ARTICLE';
    private const FILES_PROPERTY = 'FILES';
    private const PUBLIC_USAGE_PROPERTY = 'SPOSOB_PRIMENENIYA';
    private const PUBLIC_STORAGE_PROPERTY = 'SROK_KHRANENIYA_1';
    private const LEGACY_PUBLIC_STORAGE_PROPERTY = 'SROK_KHRANENIYA';
    private const MAX_CONTENT_LENGTH = 200000;
    private array $fileCache = [];

    public function pull(): array
    {
        $iblockId = max(1, (int)Option::get(self::MODULE_ID, 'catalog_iblock_id', '2'));
        $legacyIblockId = max(
            1,
            (int)Option::get(self::MODULE_ID, 'legacy_catalog_iblock_id', '21')
        );
        $fallbackBySystemId = $legacyIblockId === $iblockId
            ? []
            : $this->fallbackContentBySystemId($legacyIblockId);
        $rows = [];
        $elementIds = [];
        $elements = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            ['IBLOCK_ID' => $iblockId],
            false,
            false,
            [
                'ID',
                'NAME',
                'XML_ID',
                'ACTIVE',
                'TIMESTAMP_X',
                'PREVIEW_TEXT',
                'DETAIL_TEXT',
            ]
        );
        while ($element = $elements->Fetch()) {
            $systemId = $this->systemId($element['XML_ID'] ?? null);
            $id = (int)$element['ID'];
            $elementIds[] = $id;
            $rows[$id] = [
                'element_id' => $id,
                'system_id' => $systemId,
                'name' => trim((string)$element['NAME']),
                'active' => (string)($element['ACTIVE'] ?? 'N') === 'Y',
                'updated_at' => $this->dateIso($element['TIMESTAMP_X'] ?? null),
                'preview_text' => $element['PREVIEW_TEXT'] ?? null,
                'detail_text' => $element['DETAIL_TEXT'] ?? null,
            ];
        }

        $properties = [];
        if ($elementIds !== []) {
            \CIBlockElement::GetPropertyValuesArray(
                $properties,
                $iblockId,
                ['ID' => $elementIds],
                ['CODE' => [
                    self::DESCRIPTION_PROPERTY,
                    self::USAGE_PROPERTY,
                    self::STORAGE_PROPERTY,
                    self::SYSTEM_ID_PROPERTY,
                    self::SKU_PROPERTY,
                    self::FILES_PROPERTY,
                    self::PUBLIC_USAGE_PROPERTY,
                    self::PUBLIC_STORAGE_PROPERTY,
                    self::LEGACY_PUBLIC_STORAGE_PROPERTY,
                ]]
            );
        }

        $resolvedRows = [];
        foreach ($rows as $elementId => $row) {
            $elementProperties = is_array($properties[$elementId] ?? null)
                ? $properties[$elementId]
                : [];
            $mappedSystemId = $this->systemId(
                $this->propertyValue($elementProperties, self::SYSTEM_ID_PROPERTY)
            );
            $row['system_id'] = $mappedSystemId ?? $row['system_id'];
            $fallback = $row['system_id'] === null
                ? []
                : ($fallbackBySystemId[$row['system_id']] ?? []);
            $row['sku'] = $this->plainText(
                $this->propertyValue($elementProperties, self::SKU_PROPERTY)
            );
            $row['description'] = $this->firstContent(
                $this->propertyValue($elementProperties, self::DESCRIPTION_PROPERTY),
                $row['detail_text'],
                $row['preview_text'],
                $fallback['description'] ?? null,
            );
            $row['usage'] = $this->firstContent(
                $this->propertyValue($elementProperties, self::USAGE_PROPERTY),
                $this->propertyValue($elementProperties, self::PUBLIC_USAGE_PROPERTY),
                $fallback['usage'] ?? null,
            );
            $row['storage'] = $this->firstContent(
                $this->propertyValue($elementProperties, self::STORAGE_PROPERTY),
                $this->propertyValue($elementProperties, self::PUBLIC_STORAGE_PROPERTY),
                $this->propertyValue($elementProperties, self::LEGACY_PUBLIC_STORAGE_PROPERTY),
                $fallback['storage'] ?? null,
            );
            $row['certificates'] = $this->certificates($elementProperties);
            unset($row['preview_text'], $row['detail_text']);
            $resolvedRows[] = $row;
        }

        $activeSystemIds = [];
        $activeSkus = [];
        foreach ($resolvedRows as $row) {
            if (!$row['active']) {
                continue;
            }
            if ($row['system_id'] !== null) {
                $activeSystemIds[$row['system_id']] = true;
            }
            $skuKey = $this->skuKey($row['sku']);
            if ($skuKey !== null) {
                $activeSkus[$skuKey] = true;
            }
        }

        $selectedRows = [];
        foreach ($resolvedRows as $row) {
            if (!$row['active']) {
                $skuKey = $this->skuKey($row['sku']);
                if (
                    $row['system_id'] === null
                    || isset($activeSystemIds[$row['system_id']])
                    || ($skuKey !== null && isset($activeSkus[$skuKey]))
                ) {
                    continue;
                }
            }
            $selectedRows[$row['element_id']] = $row;
        }

        $categories = $this->activeCategories($iblockId, $selectedRows);
        $products = [];
        foreach ($selectedRows as $row) {
            unset($row['element_id']);
            unset($row['active']);
            $products[] = $row;
        }

        return [
            'products' => $products,
            'total' => count($products),
            'categories' => $categories,
            'categories_total' => count($categories),
            'catalog_iblock_id' => $iblockId,
            'legacy_catalog_iblock_id' => $legacyIblockId,
        ];
    }

    private function activeCategories(int $iblockId, array $selectedRows): array
    {
        $categories = [];
        $categoryIds = [];
        $sections = \CIBlockSection::GetList(
            ['SORT' => 'ASC', 'LEFT_MARGIN' => 'ASC', 'ID' => 'ASC'],
            [
                'IBLOCK_ID' => $iblockId,
                'ACTIVE' => 'Y',
                'GLOBAL_ACTIVE' => 'Y',
            ],
            false,
            [
                'ID',
                'IBLOCK_SECTION_ID',
                'NAME',
                'CODE',
                'XML_ID',
                'SORT',
                'DEPTH_LEVEL',
            ]
        );
        while ($section = $sections->Fetch()) {
            $id = (int)$section['ID'];
            $categoryIds[$id] = true;
            $categories[$id] = [
                'source_id' => $id,
                'source_xml_id' => $this->plainText($section['XML_ID'] ?? null),
                'parent_source_id' => $section['IBLOCK_SECTION_ID'] === null
                    ? null
                    : (int)$section['IBLOCK_SECTION_ID'],
                'name' => trim((string)$section['NAME']),
                'code' => $this->plainText($section['CODE'] ?? null),
                'sort' => (int)$section['SORT'],
                'depth' => (int)$section['DEPTH_LEVEL'],
                'product_system_ids' => [],
            ];
        }

        if ($categories === [] || $selectedRows === []) {
            return array_values($categories);
        }

        $elementIds = array_map('intval', array_keys($selectedRows));
        $links = Application::getConnection()->query(sprintf(
            'SELECT IBLOCK_ELEMENT_ID, IBLOCK_SECTION_ID
             FROM b_iblock_section_element
             WHERE IBLOCK_ELEMENT_ID IN (%s)',
            implode(',', $elementIds)
        ));
        while ($link = $links->fetch()) {
            $elementId = (int)$link['IBLOCK_ELEMENT_ID'];
            $categoryId = (int)$link['IBLOCK_SECTION_ID'];
            if (!isset($categoryIds[$categoryId], $selectedRows[$elementId])) {
                continue;
            }
            $systemId = $selectedRows[$elementId]['system_id'] ?? null;
            if ($systemId !== null) {
                $categories[$categoryId]['product_system_ids'][$systemId] = $systemId;
            }
        }

        foreach ($categories as &$category) {
            $category['product_system_ids'] = array_values($category['product_system_ids']);
            sort($category['product_system_ids'], SORT_STRING);
        }
        unset($category);

        return array_values($categories);
    }

    private function certificates(array $properties): array
    {
        $property = $properties[self::FILES_PROPERTY] ?? null;
        if (!is_array($property)) {
            return [];
        }
        $values = $property['VALUE'] ?? ($property['~VALUE'] ?? []);
        if (!is_array($values)) {
            $values = $values === null || $values === '' ? [] : [$values];
        }
        $descriptions = $property['DESCRIPTION'] ?? [];
        if (!is_array($descriptions)) {
            $descriptions = [$descriptions];
        }

        $result = [];
        foreach (array_values($values) as $index => $value) {
            $fileId = (int)$value;
            if ($fileId <= 0) {
                continue;
            }
            if (!array_key_exists($fileId, $this->fileCache)) {
                $file = \CFile::GetFileArray($fileId);
                $this->fileCache[$fileId] = is_array($file) ? $file : null;
            }
            $file = $this->fileCache[$fileId];
            if (!is_array($file)) {
                continue;
            }
            $path = trim((string)\CFile::GetPath($fileId));
            if (!str_starts_with($path, '/upload/')) {
                continue;
            }
            $originalName = trim((string)($file['ORIGINAL_NAME'] ?? ''));
            $description = trim(is_scalar($descriptions[$index] ?? null)
                ? (string)$descriptions[$index]
                : '');
            $result[] = [
                'source_file_id' => $fileId,
                'title' => $description !== ''
                    ? $description
                    : ($originalName !== '' ? $originalName : 'Сертификат'),
                'original_name' => $originalName !== '' ? $originalName : null,
                'content_type' => $this->plainText($file['CONTENT_TYPE'] ?? null),
                'size_bytes' => max(0, (int)($file['FILE_SIZE'] ?? 0)),
                'path' => $path,
            ];
        }
        return $result;
    }

    private function fallbackContentBySystemId(int $iblockId): array
    {
        $rows = [];
        $elementIds = [];
        $elements = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            ['IBLOCK_ID' => $iblockId],
            false,
            false,
            ['ID', 'XML_ID']
        );
        while ($element = $elements->Fetch()) {
            $elementId = (int)$element['ID'];
            $elementIds[] = $elementId;
            $rows[$elementId] = $this->systemId($element['XML_ID'] ?? null);
        }

        $properties = [];
        if ($elementIds !== []) {
            \CIBlockElement::GetPropertyValuesArray(
                $properties,
                $iblockId,
                ['ID' => $elementIds],
                ['CODE' => [
                    self::DESCRIPTION_PROPERTY,
                    self::USAGE_PROPERTY,
                    self::STORAGE_PROPERTY,
                    self::SYSTEM_ID_PROPERTY,
                ]]
            );
        }

        $candidates = [];
        foreach ($rows as $elementId => $xmlSystemId) {
            $elementProperties = is_array($properties[$elementId] ?? null)
                ? $properties[$elementId]
                : [];
            $mappedSystemId = $this->systemId(
                $this->propertyValue($elementProperties, self::SYSTEM_ID_PROPERTY)
            );
            $systemId = $mappedSystemId ?? $xmlSystemId;
            if ($systemId === null) {
                continue;
            }
            $candidates[$systemId][] = [
                'description' => $this->content(
                    $this->propertyValue($elementProperties, self::DESCRIPTION_PROPERTY)
                ),
                'usage' => $this->content(
                    $this->propertyValue($elementProperties, self::USAGE_PROPERTY)
                ),
                'storage' => $this->content(
                    $this->propertyValue($elementProperties, self::STORAGE_PROPERTY)
                ),
            ];
        }

        $result = [];
        foreach ($candidates as $systemId => $matches) {
            $resolved = [];
            foreach (['description', 'usage', 'storage'] as $field) {
                $values = [];
                foreach ($matches as $match) {
                    $value = $match[$field] ?? null;
                    if ($value !== null) {
                        $values[] = $value;
                    }
                }
                $values = array_values(array_unique($values));
                if (count($values) === 1) {
                    $resolved[$field] = $values[0];
                }
            }
            if ($resolved !== []) {
                $result[$systemId] = $resolved;
            }
        }
        return $result;
    }

    private function systemId(mixed $value): ?string
    {
        $normalized = strtolower(trim(is_scalar($value) ? (string)$value : ''));
        return preg_match(
            '/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/D',
            $normalized
        ) === 1 ? $normalized : null;
    }

    private function content(mixed $value): ?string
    {
        if (is_array($value) && array_key_exists('TEXT', $value)) {
            $value = $value['TEXT'];
        }
        if (!is_scalar($value)) {
            return null;
        }
        $text = trim(str_replace("\0", '', (string)$value));
        if ($text === '') {
            return null;
        }
        return mb_substr($text, 0, self::MAX_CONTENT_LENGTH);
    }

    private function plainText(mixed $value): ?string
    {
        if (!is_scalar($value)) {
            return null;
        }
        $text = trim((string)$value);
        return $text === '' ? null : $text;
    }

    private function skuKey(mixed $value): ?string
    {
        $value = $this->plainText($value);
        return $value === null ? null : mb_strtolower($value);
    }

    private function firstContent(mixed ...$values): ?string
    {
        foreach ($values as $value) {
            $content = $this->content($value);
            if ($content !== null) {
                return $content;
            }
        }
        return null;
    }

    private function propertyValue(array $properties, string $code): mixed
    {
        $property = $properties[$code] ?? null;
        if (!is_array($property)) {
            return null;
        }
        return array_key_exists('~VALUE', $property)
            ? $property['~VALUE']
            : ($property['VALUE'] ?? null);
    }

    private function dateIso(mixed $value): ?string
    {
        if ($value instanceof \DateTimeInterface) {
            return $value->format(DATE_ATOM);
        }
        $timestamp = strtotime(trim(is_scalar($value) ? (string)$value : ''));
        return $timestamp === false ? null : date(DATE_ATOM, $timestamp);
    }
}
