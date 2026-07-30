<?php

declare(strict_types=1);

namespace Elixir\Delivery\Service;

use Bitrix\Catalog\Product\CatalogProvider;
use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Bitrix\Sale\Basket;
use Bitrix\Sale\Delivery\Services\Manager as DeliveryManager;
use Bitrix\Sale\Delivery\Services\Table as DeliveryServiceTable;
use Bitrix\Sale\Location\LocationTable;
use Bitrix\Sale\Order;

final class DeliveryQuoteService
{
    private const MODULE_ID = 'elixir.delivery';

    public function quote(array $payload): array
    {
        $this->includeRequiredModules();
        $mode = $this->normalizeMode($payload['mode'] ?? null);
        $destination = $this->normalizeDestination($payload['destination'] ?? null);
        $items = $this->normalizeItems($payload['items'] ?? null);
        $siteId = trim(Option::get(self::MODULE_ID, 'site_id', 's1'));
        $currency = strtoupper(trim(Option::get(self::MODULE_ID, 'currency', 'RUB')));
        $personTypeId = max(1, (int)Option::get(self::MODULE_ID, 'person_type_id', '1'));
        $userId = $this->resolveUserId($payload);

        $location = $this->resolveLocation((int)$destination['cdek_city_code']);
        $service = $this->resolveDeliveryService($mode);
        $basket = $this->buildBasket($siteId, $currency, $items);
        $order = Order::create($siteId, $userId, $currency);
        $order->setPersonTypeId($personTypeId);
        $setBasketResult = $order->setBasket($basket);
        if (!$setBasketResult->isSuccess()) {
            throw new \RuntimeException('basket_setup_failed:' . implode('; ', $setBasketResult->getErrorMessages()));
        }
        $this->setOrderProperties($order, $location['code'], $destination);

        $shipment = $order->getShipmentCollection()->createItem($service);
        $shipmentItems = $shipment->getShipmentItemCollection();
        foreach ($basket as $basketItem) {
            $shipmentItem = $shipmentItems->createItem($basketItem);
            $shipmentItem->setQuantity($basketItem->getQuantity());
        }

        $this->resetIpolRuntime();
        $order->doFinalAction(true);
        $calculation = $shipment->calculateDelivery();
        if (!$calculation->isSuccess()) {
            throw new \DomainException(
                'calculation_failed:' . implode('; ', $calculation->getErrorMessages())
            );
        }

        $period = $this->normalizePeriod(
            $calculation->getPeriodFrom(),
            $calculation->getPeriodTo(),
            (string)$calculation->getPeriodDescription()
        );
        $profile = $mode === 'door' ? 'courier' : 'pickup';
        $tariff = class_exists('sdekShipmentCollection')
            ? \sdekShipmentCollection::getProfileTarif($profile)
            : ($_SESSION['IPOLSDEK_CHOSEN'][$profile] ?? null);
        $weight = max(0, (int)(\CDeliverySDEK::$orderWeight ?: $basket->getWeight()));
        if ($weight === 0 && class_exists(\Ipolh\SDEK\option::class)) {
            $weight = max(0, (int)\Ipolh\SDEK\option::get('weightD'));
        }

        return [
            'delivery_sum' => round((float)$calculation->getPrice(), 2),
            'period_min' => $period['min'],
            'period_max' => $period['max'],
            'period_description' => $period['description'],
            'weight_calc' => $weight,
            'currency' => $currency,
            'service' => [
                'id' => (int)$service->getId(),
                'code' => (string)$service->getCode(),
                'name' => (string)$service->getName(),
                'mode' => $mode,
            ],
            'tariff_code' => is_numeric($tariff) ? (int)$tariff : null,
            'destination' => [
                'cdek_city_code' => (int)$destination['cdek_city_code'],
                'bitrix_location_code' => $location['code'],
                'city' => $destination['city'],
            ],
            'items_count' => count($items),
            'quantity_total' => array_sum(array_column($items, 'quantity')),
            'calculated_by' => 'bitrix_ipol_sdek',
        ];
    }

    private function includeRequiredModules(): void
    {
        foreach (['sale', 'catalog', 'iblock', 'ipol.sdek'] as $moduleId) {
            if (!Loader::includeModule($moduleId)) {
                throw new \RuntimeException('module_unavailable:' . $moduleId);
            }
        }
    }

    private function normalizeMode(mixed $rawMode): string
    {
        $mode = strtolower(trim(is_scalar($rawMode) ? (string)$rawMode : ''));
        if ($mode === 'office') {
            return 'pickup';
        }
        if (!in_array($mode, ['pickup', 'door'], true)) {
            throw new \InvalidArgumentException('invalid_mode');
        }
        return $mode;
    }

    private function normalizeDestination(mixed $rawDestination): array
    {
        if (!is_array($rawDestination)) {
            throw new \InvalidArgumentException('invalid_destination');
        }
        $cityCode = filter_var(
            $rawDestination['cdek_city_code'] ?? null,
            FILTER_VALIDATE_INT,
            ['options' => ['min_range' => 1]]
        );
        if ($cityCode === false) {
            throw new \InvalidArgumentException('invalid_destination');
        }
        return [
            'cdek_city_code' => (int)$cityCode,
            'country_code' => $this->boundedString($rawDestination['country_code'] ?? '', 2),
            'postal_code' => $this->boundedString($rawDestination['postal_code'] ?? '', 20),
            'city' => $this->boundedString($rawDestination['city'] ?? '', 255),
            'address' => $this->boundedString($rawDestination['address'] ?? '', 1000),
            'latitude' => $this->nullableFloat($rawDestination['latitude'] ?? null, -90, 90),
            'longitude' => $this->nullableFloat($rawDestination['longitude'] ?? null, -180, 180),
        ];
    }

    private function normalizeItems(mixed $rawItems): array
    {
        if (!is_array($rawItems) || $rawItems === []) {
            throw new \InvalidArgumentException('empty_basket');
        }
        $maxItems = max(1, min(500, (int)Option::get(self::MODULE_ID, 'max_items', '100')));
        if (count($rawItems) > $maxItems) {
            throw new \InvalidArgumentException('too_many_items');
        }
        $items = [];
        foreach ($rawItems as $rawItem) {
            if (!is_array($rawItem)) {
                throw new \InvalidArgumentException('invalid_item');
            }
            $variantSystemId = $this->boundedString($rawItem['variant_system_id'] ?? '', 100);
            $productSystemId = $this->boundedString($rawItem['product_system_id'] ?? '', 100);
            $quantity = filter_var(
                $rawItem['quantity'] ?? null,
                FILTER_VALIDATE_INT,
                ['options' => ['min_range' => 1, 'max_range' => 1000]]
            );
            if (($variantSystemId === '' && $productSystemId === '') || $quantity === false) {
                throw new \InvalidArgumentException('invalid_item');
            }
            $items[] = [
                'variant_system_id' => $variantSystemId,
                'product_system_id' => $productSystemId,
                'quantity' => (int)$quantity,
            ];
        }
        return $items;
    }

    private function buildBasket(string $siteId, string $currency, array $items): Basket
    {
        $basket = Basket::create($siteId);
        foreach ($items as $item) {
            $element = $this->findCatalogElement(
                $item['variant_system_id'],
                $item['product_system_id']
            );
            $basketItem = $basket->createItem('catalog', (int)$element['ID']);
            $setResult = $basketItem->setFields([
                'QUANTITY' => (float)$item['quantity'],
                'CURRENCY' => $currency,
                'LID' => $siteId,
                'PRODUCT_PROVIDER_CLASS' => CatalogProvider::class,
            ]);
            if (!$setResult->isSuccess()) {
                throw new \RuntimeException(
                    'basket_item_failed:' . implode('; ', $setResult->getErrorMessages())
                );
            }
        }
        $refreshResult = $basket->refresh();
        if (!$refreshResult->isSuccess()) {
            throw new \RuntimeException(
                'basket_refresh_failed:' . implode('; ', $refreshResult->getErrorMessages())
            );
        }
        return $basket;
    }

    private function findCatalogElement(string $variantSystemId, string $productSystemId): array
    {
        foreach (array_values(array_unique(array_filter([$variantSystemId, $productSystemId]))) as $xmlId) {
            $element = \CIBlockElement::GetList(
                [],
                ['=XML_ID' => $xmlId, '=ACTIVE' => 'Y'],
                false,
                ['nTopCount' => 1],
                ['ID', 'IBLOCK_ID', 'XML_ID', 'NAME']
            )->Fetch();
            if (is_array($element)) {
                return $element;
            }
        }
        throw new \DomainException('product_not_found:' . ($variantSystemId ?: $productSystemId));
    }

    private function resolveLocation(int $cdekCityCode): array
    {
        $cdekCity = \sqlSdekCity::getBySId($cdekCityCode);
        if (!is_array($cdekCity) || empty($cdekCity['BITRIX_ID'])) {
            throw new \DomainException('destination_not_found');
        }
        $location = LocationTable::getById((int)$cdekCity['BITRIX_ID'])->fetch();
        if (!is_array($location) || empty($location['CODE'])) {
            throw new \DomainException('destination_not_found');
        }
        return ['code' => (string)$location['CODE']];
    }

    private function resolveDeliveryService(string $mode): object
    {
        $option = $mode === 'door' ? 'courier_service_code' : 'pickup_service_code';
        $default = $mode === 'door' ? 'sdek:courier' : 'sdek:pickup';
        $code = trim(Option::get(self::MODULE_ID, $option, $default));
        $row = DeliveryServiceTable::getList([
            'filter' => ['=CODE' => $code, '=ACTIVE' => 'Y'],
            'order' => ['ID' => 'DESC'],
            'limit' => 1,
            'select' => ['ID', 'PARENT_ID', 'ACTIVE'],
        ])->fetch();
        if (!is_array($row)) {
            throw new \DomainException('delivery_mode_unavailable:' . $mode);
        }
        if ((int)($row['PARENT_ID'] ?? 0) > 0) {
            $parent = DeliveryServiceTable::getById((int)$row['PARENT_ID'])->fetch();
            if (!is_array($parent) || $parent['ACTIVE'] !== 'Y') {
                throw new \DomainException('delivery_mode_unavailable:' . $mode);
            }
        }
        $service = DeliveryManager::getObjectById((int)$row['ID']);
        if ($service === null) {
            throw new \DomainException('delivery_mode_unavailable:' . $mode);
        }
        return $service;
    }

    private function setOrderProperties(Order $order, string $locationCode, array $destination): void
    {
        $values = [
            'LOCATION' => $locationCode,
            'ZIP' => $destination['postal_code'],
            'CITY' => $destination['city'],
            'ADDRESS' => $destination['address'],
        ];
        foreach ($order->getPropertyCollection() as $property) {
            $code = (string)$property->getField('CODE');
            if (array_key_exists($code, $values)) {
                $property->setValue($values[$code]);
            }
        }
    }

    private function resolveUserId(array $payload): int
    {
        if (isset($payload['bitrix_user_id']) && is_numeric($payload['bitrix_user_id'])) {
            return max(0, (int)$payload['bitrix_user_id']);
        }
        $email = $this->boundedString($payload['user_email'] ?? '', 255);
        if ($email === '' || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
            return 0;
        }
        $by = 'id';
        $orderDirection = 'asc';
        $user = \CUser::GetList(
            $by,
            $orderDirection,
            ['=EMAIL' => $email, 'ACTIVE' => 'Y'],
            ['FIELDS' => ['ID']]
        )->Fetch();
        return is_array($user) ? max(0, (int)$user['ID']) : 0;
    }

    private function resetIpolRuntime(): void
    {
        \CDeliverySDEK::$profiles = false;
        \CDeliverySDEK::$price = false;
        \CDeliverySDEK::$orderWeight = false;
        \CDeliverySDEK::$orderPrice = false;
        \CDeliverySDEK::$bitrixCity = false;
        \CDeliverySDEK::$sdekCity = false;
        \CDeliverySDEK::$sdekCityCntr = false;
        \CDeliverySDEK::$sdekSender = false;
        \CDeliverySDEK::$goods = false;
        \CDeliverySDEK::$preSet = false;
        \CDeliverySDEK::$lastCnt = false;
        if (!isset($_SESSION) || !is_array($_SESSION)) {
            $_SESSION = [];
        }
        $_SESSION['IPOLSDEK_CHOSEN'] = [];
    }

    private function normalizePeriod(mixed $from, mixed $to, string $description): array
    {
        $min = is_numeric($from) ? max(0, (int)$from) : 0;
        $max = is_numeric($to) ? max(0, (int)$to) : 0;
        if ($min === 0 && preg_match_all('/\d+/', $description, $matches) && $matches[0] !== []) {
            $min = (int)$matches[0][0];
            $max = (int)($matches[0][1] ?? $matches[0][0]);
        }
        if ($max < $min) {
            $max = $min;
        }
        return ['min' => $min, 'max' => $max, 'description' => trim($description)];
    }

    private function boundedString(mixed $value, int $maxLength): string
    {
        if (!is_scalar($value)) {
            return '';
        }
        $normalized = trim((string)$value);
        if (mb_strlen($normalized) > $maxLength) {
            throw new \InvalidArgumentException('value_too_long');
        }
        return $normalized;
    }

    private function nullableFloat(mixed $value, float $minimum, float $maximum): ?float
    {
        if ($value === null || $value === '') {
            return null;
        }
        if (!is_numeric($value)) {
            throw new \InvalidArgumentException('invalid_destination');
        }
        $number = (float)$value;
        if (!is_finite($number) || $number < $minimum || $number > $maximum) {
            throw new \InvalidArgumentException('invalid_destination');
        }
        return $number;
    }
}
