<?php

declare(strict_types=1);

namespace Elixir\CatalogSync\Service;

use Bitrix\Main\Config\Option;

final class CatalogContentService
{
    private const MODULE_ID = 'elixir.catalogsync';
    private const DESCRIPTION_PROPERTY = 'ELIXIR_APP_DESCRIPTION';
    private const USAGE_PROPERTY = 'ELIXIR_APP_USAGE';
    private const STORAGE_PROPERTY = 'ELIXIR_APP_STORAGE';
    private const SYSTEM_ID_PROPERTY = 'ELIXIR_APP_SYSTEM_ID';
    private const SKU_PROPERTY = 'CML2_ARTICLE';
    private const MAX_CONTENT_LENGTH = 200000;

    public function pull(): array
    {
        $iblockId = max(1, (int)Option::get(self::MODULE_ID, 'catalog_iblock_id', '21'));
        $rows = [];
        $elementIds = [];
        $elements = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            ['IBLOCK_ID' => $iblockId],
            false,
            false,
            ['ID', 'NAME', 'XML_ID', 'TIMESTAMP_X']
        );
        while ($element = $elements->Fetch()) {
            $systemId = $this->systemId($element['XML_ID'] ?? null);
            $id = (int)$element['ID'];
            $elementIds[] = $id;
            $rows[$id] = [
                'system_id' => $systemId,
                'name' => trim((string)$element['NAME']),
                'updated_at' => $this->dateIso($element['TIMESTAMP_X'] ?? null),
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
                ]]
            );
        }

        $products = [];
        foreach ($rows as $elementId => $row) {
            $elementProperties = is_array($properties[$elementId] ?? null)
                ? $properties[$elementId]
                : [];
            $mappedSystemId = $this->systemId(
                $this->propertyValue($elementProperties, self::SYSTEM_ID_PROPERTY)
            );
            $row['system_id'] = $mappedSystemId ?? $row['system_id'];
            $row['sku'] = $this->plainText(
                $this->propertyValue($elementProperties, self::SKU_PROPERTY)
            );
            $row['description'] = $this->content(
                $this->propertyValue($elementProperties, self::DESCRIPTION_PROPERTY)
            );
            $row['usage'] = $this->content(
                $this->propertyValue($elementProperties, self::USAGE_PROPERTY)
            );
            $row['storage'] = $this->content(
                $this->propertyValue($elementProperties, self::STORAGE_PROPERTY)
            );
            $products[] = $row;
        }

        return [
            'products' => $products,
            'total' => count($products),
            'catalog_iblock_id' => $iblockId,
        ];
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
