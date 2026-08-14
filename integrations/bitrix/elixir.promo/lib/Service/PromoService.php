<?php

namespace Elixir\Promo\Service;

use Bitrix\Catalog\Product\CatalogProvider;
use Bitrix\Currency\CurrencyManager;
use Bitrix\Iblock\ElementTable;
use Bitrix\Main\Application;
use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Bitrix\Sale\Basket;
use Bitrix\Sale\DiscountCouponsManager;
use Bitrix\Sale\Order;
use Bitrix\Sale\Internals\DiscountCouponTable;

final class PromoService
{
    private const MODULE_ID = 'elixir.promo';

    public function lookup(string $promo): array
    {
        $promo = $this->normalizePromo($promo);
        $row = $this->loadCoupon($promo);
        if ($row === null || !$this->isAvailable($row)) {
            throw new \DomainException('promo_not_found');
        }

        $rule = $this->analyzeRule((string)$row['ACTIONS'], (string)$row['CONDITIONS']);

        return [
            'promo' => (string)$row['COUPON'],
            'coupon_id' => (int)$row['COUPON_ID'],
            'discount_id' => (int)$row['DISCOUNT_ID'],
            'discount_name' => (string)$row['DISCOUNT_NAME'],
            'use_count' => (int)($row['USE_COUNT'] ?? 0),
            'max_use' => (int)($row['MAX_USE'] ?? 0) > 0
                ? (int)$row['MAX_USE']
                : null,
            'discount_percent' => $rule['discount_percent'] ?? null,
            'applicability' => 'requires_bitrix_cart',
            'price_authority' => 'bitrix',
            'constraints' => [
                'has_order_conditions' => (bool)($rule['has_order_conditions'] ?? true),
                'has_basket_item_conditions' => (bool)($rule['has_basket_item_conditions'] ?? true),
            ],
        ];
    }

    public function quote(string $promo, array $items, int $userId = 0, ?string $userEmail = null): array
    {
        if (!Loader::includeModule('sale') || !Loader::includeModule('catalog') || !Loader::includeModule('iblock')) {
            throw new \RuntimeException('required_module_unavailable');
        }

        $lookup = $this->lookup($promo);
        $maxItems = max(1, min(500, (int)Option::get(self::MODULE_ID, 'max_items', '100')));
        if ($items === [] || count($items) > $maxItems) {
            throw new \InvalidArgumentException('invalid_items');
        }

        $siteId = trim(Option::get(self::MODULE_ID, 'site_id', 's1'));
        $currency = trim(Option::get(self::MODULE_ID, 'currency', ''));
        if ($currency === '') {
            $currency = (string)CurrencyManager::getBaseCurrency();
        }

        $userContext = $this->resolveUserContext($userId, $userEmail);
        $userId = $userContext['user_id'];
        $siteDiscountContext = new SiteDiscountContext();
        $discountContext = $siteDiscountContext->resolve($promo, $userId);
        $groupCacheSnapshot = $siteDiscountContext->overrideUserGroupCache(
            $userId,
            (array)$discountContext['runtime_user_groups']
        );
        $couponAccepted = false;

        try {
            DiscountCouponsManager::init(
                DiscountCouponsManager::MODE_CLIENT,
                ['userId' => max(0, $userId)]
            );
            DiscountCouponsManager::clear(true);
            if (!empty($discountContext['use_coupon'])) {
                $couponAccepted = DiscountCouponsManager::add($promo);
            }

            $basket = Basket::create($siteId);
            $providerClass = class_exists(CatalogProvider::class)
                ? CatalogProvider::class
                : 'CCatalogProductProvider';
            $resolvedItems = [];

            foreach ($items as $index => $itemData) {
                if (!is_array($itemData)) {
                    throw new \InvalidArgumentException('invalid_item');
                }
                $quantity = (float)($itemData['quantity'] ?? 0);
                if ($quantity <= 0 || $quantity > 10000) {
                    throw new \InvalidArgumentException('invalid_quantity');
                }
                $resolvedItem = $this->resolveProduct($itemData);
                $productId = (int)$resolvedItem['product_id'];
                if ($productId <= 0) {
                    throw new \DomainException('product_not_found:' . $index);
                }

                $basketItem = $basket->createItem('catalog', $productId);
                $setResult = $basketItem->setFields([
                    'QUANTITY' => $quantity,
                    'CURRENCY' => $currency,
                    'LID' => $siteId,
                    'PRODUCT_PROVIDER_CLASS' => $providerClass,
                ]);
                if (!$setResult->isSuccess()) {
                    throw new \RuntimeException('basket_item_failed:' . implode('; ', $setResult->getErrorMessages()));
                }
                $resolvedItems[(string)$basketItem->getBasketCode()] = $resolvedItem;
            }

            if (method_exists($basket, 'refreshData')) {
                $refreshResult = $basket->refreshData(['PRICE']);
                if (is_object($refreshResult) && method_exists($refreshResult, 'isSuccess') && !$refreshResult->isSuccess()) {
                    throw new \RuntimeException('basket_refresh_failed:' . implode('; ', $refreshResult->getErrorMessages()));
                }
            }

            $order = Order::create($siteId, max(0, $userId), $currency);
            $order->setPersonTypeId(max(1, (int)Option::get(self::MODULE_ID, 'person_type_id', '1')));
            $order->setBasket($basket);
            $calculationResult = $order->doFinalAction(true);
            if (!$calculationResult->isSuccess()) {
                throw new \RuntimeException('discount_calculation_failed:' . implode('; ', $calculationResult->getErrorMessages()));
            }
        } finally {
            DiscountCouponsManager::clear(true);
            $siteDiscountContext->restoreUserGroupCache($userId, $groupCacheSnapshot);
        }

        $lines = [];
        foreach ($basket as $basketItem) {
            $resolvedItem = $resolvedItems[(string)$basketItem->getBasketCode()] ?? [];
            $basePrice = (float)$basketItem->getBasePrice();
            $finalPrice = (float)$basketItem->getPrice();
            $quantity = (float)$basketItem->getQuantity();
            $lines[] = [
                'product_id' => (int)$basketItem->getProductId(),
                'variant_system_id' => $resolvedItem['variant_system_id'] ?? null,
                'product_system_id' => $resolvedItem['product_system_id'] ?? null,
                'sku' => $resolvedItem['sku'] ?? null,
                'matched_by' => $resolvedItem['matched_by'] ?? null,
                'name' => (string)$basketItem->getField('NAME'),
                'quantity' => $quantity,
                'base_unit_price' => round($basePrice, 2),
                'final_unit_price' => round($finalPrice, 2),
                'discount_amount' => round(max(0, ($basePrice - $finalPrice) * $quantity), 2),
                'base_total' => round($basePrice * $quantity, 2),
                'final_total' => round($finalPrice * $quantity, 2),
            ];
        }

        $baseTotal = round((float)$basket->getBasePrice(), 2);
        $finalTotal = round((float)$basket->getPrice(), 2);
        $discountAmount = round(max(0, $baseTotal - $finalTotal), 2);

        return [
            'promo' => $lookup['promo'],
            'coupon_id' => $lookup['coupon_id'],
            'discount_id' => $lookup['discount_id'],
            'currency' => $currency,
            'user_id' => max(0, $userId),
            'user_context' => $userContext['status'],
            'coupon_accepted' => (bool)$couponAccepted,
            'promo_mode' => (string)$discountContext['mode'],
            'is_referral_promo' => (
                (int)($discountContext['referral_owner_id'] ?? 0) > 0
                || !empty($discountContext['is_firm_promo'])
            ),
            'is_firm_promo' => !empty($discountContext['is_firm_promo']),
            'runtime_user_groups' => (array)$discountContext['runtime_user_groups'],
            'effective_discount_percent' => $discountContext['effective_discount_percent'],
            'is_applicable' => (
                in_array(
                    (string)$discountContext['mode'],
                    [SiteDiscountContext::MODE_NATIVE, SiteDiscountContext::MODE_EXTERNAL],
                    true
                )
                && $discountAmount > 0
            ),
            'base_total' => $baseTotal,
            'discount_amount' => $discountAmount,
            'final_total' => $finalTotal,
            'lines' => $lines,
            'price_authority' => 'bitrix',
        ];
    }

    public function ensureCouponForUser(int $userId, string $promo): array
    {
        if (!Loader::includeModule('sale')) {
            throw new \RuntimeException('sale_module_unavailable');
        }
        $promo = $this->normalizePromo($promo);
        $discountId = max(1, (int)Option::get(self::MODULE_ID, 'discount_id', '24'));

        $existing = DiscountCouponTable::getList([
            'select' => ['ID', 'DISCOUNT_ID'],
            'filter' => ['=COUPON' => $promo],
            'limit' => 1,
        ])->fetch();
        if (is_array($existing)) {
            return [
                'outcome' => 'exists',
                'coupon_id' => (int)$existing['ID'],
                'discount_id' => (int)$existing['DISCOUNT_ID'],
            ];
        }

        $result = DiscountCouponTable::add([
            'DISCOUNT_ID' => $discountId,
            'ACTIVE' => 'Y',
            'COUPON' => $promo,
            'TYPE' => DiscountCouponTable::TYPE_MULTI_ORDER,
            'CREATED_BY' => max(1, $userId),
            'DATE_APPLY' => null,
            'DESCRIPTION' => 'Персональный промокод пользователя Bitrix ID ' . $userId,
        ]);
        if (!$result->isSuccess()) {
            throw new \RuntimeException('coupon_create_failed:' . implode('; ', $result->getErrorMessages()));
        }

        return [
            'outcome' => 'created',
            'coupon_id' => (int)$result->getId(),
            'discount_id' => $discountId,
        ];
    }

    public function attachReferrer(
        string $promo,
        int $userId = 0,
        ?string $userEmail = null
    ): array {
        $promo = $this->normalizePromo($promo);
        $this->lookup($promo);
        $userContext = $this->resolveUserContext($userId, $userEmail);
        $resolvedUserId = (int)$userContext['user_id'];
        if ($resolvedUserId <= 0) {
            throw new \DomainException('user_not_found');
        }

        return [
            'promo' => $promo,
            'user_context' => $userContext['status'],
        ] + (new SiteDiscountContext())->attachReferrer($promo, $resolvedUserId);
    }

    public function context(
        string $promo,
        int $userId = 0,
        ?string $userEmail = null
    ): array {
        $promo = $this->normalizePromo($promo);
        $lookup = $this->lookup($promo);
        $userContext = $this->resolveUserContext($userId, $userEmail);
        $resolvedUserId = (int)$userContext['user_id'];
        if ($resolvedUserId <= 0) {
            throw new \DomainException('user_not_found');
        }

        $siteDiscountContext = new SiteDiscountContext();
        $context = $siteDiscountContext->resolve($promo, $resolvedUserId);
        $displayDiscountPercent = null;
        if ((string)$context['mode'] === SiteDiscountContext::MODE_NATIVE) {
            $displayDiscountPercent = $context['effective_discount_percent'];
        } elseif ((string)$context['mode'] === SiteDiscountContext::MODE_EXTERNAL) {
            $displayDiscountPercent = $lookup['discount_percent'];
        }

        return [
            'promo' => $promo,
            'user_context' => $userContext['status'],
            'display_discount_percent' => $displayDiscountPercent,
            'program_profile' => $siteDiscountContext->getProgramProfile($resolvedUserId),
        ] + $context;
    }

    public function profile(
        int $userId = 0,
        ?string $userEmail = null
    ): array {
        $userContext = $this->resolveUserContext($userId, $userEmail);
        $resolvedUserId = (int)$userContext['user_id'];
        if ($resolvedUserId <= 0) {
            throw new \DomainException('user_not_found');
        }

        return [
            'user_id' => $resolvedUserId,
            'user_context' => $userContext['status'],
            'program_profile' => (new SiteDiscountContext())->getProgramProfile($resolvedUserId),
        ];
    }

    public function setOpeningBalance(
        float $amount,
        string $currency = 'RUB',
        int $userId = 0,
        ?string $userEmail = null
    ): array {
        $userContext = $this->resolveUserContext($userId, $userEmail);
        $resolvedUserId = (int)$userContext['user_id'];
        if ($resolvedUserId <= 0) {
            throw new \DomainException('user_not_found');
        }
        if (!preg_match('/^[A-Z]{3}$/', strtoupper(trim($currency)))) {
            throw new \InvalidArgumentException('invalid_currency');
        }

        return [
            'user_id' => $resolvedUserId,
            'user_context' => $userContext['status'],
        ] + (new SiteDiscountContext())->setOpeningPurchaseBalance(
            $resolvedUserId,
            $amount,
            $currency
        );
    }

    public function detachReferrer(
        int $userId = 0,
        ?string $userEmail = null
    ): array {
        $userContext = $this->resolveUserContext($userId, $userEmail);
        $resolvedUserId = (int)$userContext['user_id'];
        if ($resolvedUserId <= 0) {
            throw new \DomainException('user_not_found');
        }

        return [
            'user_context' => $userContext['status'],
        ] + (new SiteDiscountContext())->detachReferrer($resolvedUserId);
    }

    private function normalizePromo(string $promo): string
    {
        $promo = trim($promo);
        $length = function_exists('mb_strlen') ? mb_strlen($promo, 'UTF-8') : strlen($promo);
        if ($promo === '' || $length > 100) {
            throw new \InvalidArgumentException('invalid_promo');
        }
        return $promo;
    }

    private function resolveUserContext(int $userId, ?string $userEmail): array
    {
        if ($userId > 0) {
            $connection = Application::getConnection();
            $row = $connection->query(
                'SELECT ID FROM b_user WHERE ID=' . $userId . " AND ACTIVE='Y' LIMIT 1"
            )->fetch();
            if (is_array($row)) {
                return ['user_id' => (int)$row['ID'], 'status' => 'matched_by_id'];
            }
        }

        $userEmail = trim((string)$userEmail);
        if ($userEmail !== '') {
            if (strlen($userEmail) > 254 || !filter_var($userEmail, FILTER_VALIDATE_EMAIL)) {
                throw new \InvalidArgumentException('invalid_user_email');
            }
            $connection = Application::getConnection();
            $emailSql = $connection->getSqlHelper()->forSql($userEmail, 254);
            $row = $connection->query(
                "SELECT ID FROM b_user WHERE EMAIL='" . $emailSql . "' AND ACTIVE='Y' ORDER BY ID ASC LIMIT 1"
            )->fetch();
            if (is_array($row)) {
                return ['user_id' => (int)$row['ID'], 'status' => 'matched_by_email'];
            }
        }

        return ['user_id' => 0, 'status' => 'anonymous'];
    }

    private function resolveProduct(array $item): array
    {
        $offerIblockId = (int)Option::get(self::MODULE_ID, 'offers_iblock_id', '3');
        $catalogIblockId = (int)Option::get(self::MODULE_ID, 'catalog_iblock_id', '2');
        $iblockIds = array_values(array_filter([$offerIblockId, $catalogIblockId]));
        $productId = isset($item['product_id']) && is_numeric($item['product_id'])
            ? (int)$item['product_id']
            : 0;
        $variantSystemId = $this->normalizedItemIdentifier($item['variant_system_id'] ?? null);
        $productSystemId = $this->normalizedItemIdentifier($item['product_system_id'] ?? null);
        $sku = $this->normalizedItemIdentifier($item['sku'] ?? null);

        if ($productId > 0 && $this->activeElementExists($productId, $iblockIds)) {
            return $this->resolvedProduct($productId, 'product_id', $variantSystemId, $productSystemId, $sku);
        }

        if ($offerIblockId > 0 && $variantSystemId !== null) {
            $matchedId = $this->findElementByXmlId($offerIblockId, $variantSystemId);
            if ($matchedId > 0) {
                return $this->resolvedProduct($matchedId, 'variant_system_id', $variantSystemId, $productSystemId, $sku);
            }
            $matchedId = $this->findElementByXmlIdSuffix($offerIblockId, '#' . $variantSystemId);
            if ($matchedId > 0) {
                return $this->resolvedProduct($matchedId, 'variant_system_id_suffix', $variantSystemId, $productSystemId, $sku);
            }
        }

        if ($offerIblockId > 0 && $sku !== null) {
            $matchedId = $this->findElementByProperty($offerIblockId, 'CML2_ARTICLE', $sku);
            if ($matchedId > 0) {
                return $this->resolvedProduct($matchedId, 'offer_sku', $variantSystemId, $productSystemId, $sku);
            }
        }

        if ($catalogIblockId > 0 && $productSystemId !== null) {
            $matchedId = $this->findElementByXmlId($catalogIblockId, $productSystemId);
            if ($matchedId > 0) {
                return $this->resolvedProduct($matchedId, 'product_system_id', $variantSystemId, $productSystemId, $sku);
            }
        }

        if ($catalogIblockId > 0 && $sku !== null) {
            $matchedId = $this->findElementByProperty($catalogIblockId, 'CML2_ARTICLE', $sku);
            if ($matchedId > 0) {
                return $this->resolvedProduct($matchedId, 'product_sku', $variantSystemId, $productSystemId, $sku);
            }
        }

        return $this->resolvedProduct(0, 'not_found', $variantSystemId, $productSystemId, $sku);
    }

    private function normalizedItemIdentifier($value): ?string
    {
        if (!is_scalar($value)) {
            return null;
        }
        $value = trim((string)$value);
        if ($value === '') {
            return null;
        }
        $length = function_exists('mb_strlen') ? mb_strlen($value, 'UTF-8') : strlen($value);
        if ($length > 255) {
            throw new \InvalidArgumentException('invalid_item_identifier');
        }
        return $value;
    }

    private function resolvedProduct(
        int $productId,
        string $matchedBy,
        ?string $variantSystemId,
        ?string $productSystemId,
        ?string $sku
    ): array {
        return [
            'product_id' => $productId,
            'matched_by' => $matchedBy,
            'variant_system_id' => $variantSystemId,
            'product_system_id' => $productSystemId,
            'sku' => $sku,
        ];
    }

    private function activeElementExists(int $elementId, array $iblockIds): bool
    {
        if ($elementId <= 0 || $iblockIds === []) {
            return false;
        }
        $row = ElementTable::getList([
            'select' => ['ID'],
            'filter' => ['=ID' => $elementId, '@IBLOCK_ID' => $iblockIds, '=ACTIVE' => 'Y'],
            'limit' => 1,
        ])->fetch();
        return is_array($row);
    }

    private function findElementByXmlId(int $iblockId, string $xmlId): int
    {
        $row = ElementTable::getList([
            'select' => ['ID'],
            'filter' => ['=IBLOCK_ID' => $iblockId, '=XML_ID' => $xmlId, '=ACTIVE' => 'Y'],
            'limit' => 1,
        ])->fetch();
        return is_array($row) ? (int)$row['ID'] : 0;
    }

    private function findElementByXmlIdSuffix(int $iblockId, string $suffix): int
    {
        $connection = Application::getConnection();
        $suffixSql = $connection->getSqlHelper()->forSql($suffix, 255);
        $row = $connection->query(
            "SELECT ID FROM b_iblock_element
             WHERE IBLOCK_ID=" . $iblockId . "
               AND ACTIVE='Y'
               AND XML_ID LIKE '%" . $suffixSql . "'
             ORDER BY ID ASC LIMIT 1"
        )->fetch();
        return is_array($row) ? (int)$row['ID'] : 0;
    }

    private function findElementByProperty(int $iblockId, string $propertyCode, string $value): int
    {
        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $propertyCodeSql = $sqlHelper->forSql($propertyCode, 50);
        $valueSql = $sqlHelper->forSql($value, 255);
        $row = $connection->query(
            "SELECT e.ID
             FROM b_iblock_element e
             INNER JOIN b_iblock_property p
                ON p.IBLOCK_ID=e.IBLOCK_ID AND p.CODE='" . $propertyCodeSql . "'
             INNER JOIN b_iblock_element_property ep
                ON ep.IBLOCK_ELEMENT_ID=e.ID AND ep.IBLOCK_PROPERTY_ID=p.ID
             WHERE e.IBLOCK_ID=" . $iblockId . "
               AND e.ACTIVE='Y'
               AND ep.VALUE='" . $valueSql . "'
             ORDER BY e.ID ASC LIMIT 1"
        )->fetch();
        return is_array($row) ? (int)$row['ID'] : 0;
    }

    private function loadCoupon(string $promo): ?array
    {
        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $promoSql = $sqlHelper->forSql($promo, 100);
        $row = $connection->query(
            "SELECT
                c.ID AS COUPON_ID, c.COUPON, c.ACTIVE AS COUPON_ACTIVE,
                c.ACTIVE_FROM AS COUPON_ACTIVE_FROM, c.ACTIVE_TO AS COUPON_ACTIVE_TO,
                c.MAX_USE, c.USE_COUNT, d.ID AS DISCOUNT_ID, d.NAME AS DISCOUNT_NAME,
                d.ACTIVE AS DISCOUNT_ACTIVE, d.ACTIVE_FROM AS DISCOUNT_ACTIVE_FROM,
                d.ACTIVE_TO AS DISCOUNT_ACTIVE_TO, d.CONDITIONS, d.ACTIONS
             FROM b_sale_discount_coupon c
             INNER JOIN b_sale_discount d ON d.ID = c.DISCOUNT_ID
             WHERE c.COUPON = '" . $promoSql . "'
             LIMIT 1"
        )->fetch();
        return is_array($row) ? $row : null;
    }

    private function isAvailable(array $row): bool
    {
        if ((string)$row['COUPON_ACTIVE'] !== 'Y' || (string)$row['DISCOUNT_ACTIVE'] !== 'Y') {
            return false;
        }
        $maxUse = (int)($row['MAX_USE'] ?? 0);
        $useCount = (int)($row['USE_COUNT'] ?? 0);
        if ($maxUse > 0 && $useCount >= $maxUse) {
            return false;
        }
        $now = time();
        return $this->datesAllow($row['COUPON_ACTIVE_FROM'], $row['COUPON_ACTIVE_TO'], $now)
            && $this->datesAllow($row['DISCOUNT_ACTIVE_FROM'], $row['DISCOUNT_ACTIVE_TO'], $now);
    }

    private function datesAllow($activeFrom, $activeTo, int $now): bool
    {
        $from = $this->timestamp($activeFrom);
        $to = $this->timestamp($activeTo);
        return ($from === null || $from <= $now) && ($to === null || $to >= $now);
    }

    private function timestamp($value): ?int
    {
        if ($value instanceof \Bitrix\Main\Type\DateTime || $value instanceof \DateTimeInterface) {
            return $value->getTimestamp();
        }
        if ($value === null || $value === '') {
            return null;
        }
        $timestamp = strtotime((string)$value);
        return $timestamp === false ? null : $timestamp;
    }

    private function analyzeRule(string $serializedActions, string $serializedConditions): ?array
    {
        $actions = @unserialize($serializedActions, ['allowed_classes' => false]);
        if (!is_array($actions)) {
            return null;
        }
        $percentValues = [];
        $this->collectPercentActions($actions, $percentValues);
        $conditions = @unserialize($serializedConditions, ['allowed_classes' => false]);
        $conditionJson = is_array($conditions)
            ? json_encode($conditions, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)
            : '';

        return [
            'discount_percent' => count($percentValues) === 1 ? reset($percentValues) : null,
            'has_order_conditions' => is_string($conditionJson) && $conditionJson !== '' && $conditionJson !== '[]',
            'has_basket_item_conditions' => $this->containsBasketCondition($actions),
        ];
    }

    private function collectPercentActions(array $node, array &$values): void
    {
        $class = strtolower((string)($node['CLASS_ID'] ?? ''));
        $data = is_array($node['DATA'] ?? null) ? $node['DATA'] : [];
        $unit = strtolower((string)($data['Unit'] ?? $data['UNIT'] ?? ''));
        $value = $data['Value'] ?? $data['VALUE'] ?? null;
        if (($unit === 'perc' || str_contains($class, 'percent')) && is_numeric($value)) {
            $percent = round((float)$value, 4);
            $values[(string)$percent] = $percent;
        }
        foreach ($node as $child) {
            if (is_array($child)) {
                $this->collectPercentActions($child, $values);
            }
        }
    }

    private function containsBasketCondition(array $node): bool
    {
        $class = strtolower((string)($node['CLASS_ID'] ?? ''));
        if (str_contains($class, 'basket') || str_contains($class, 'product') || str_contains($class, 'iblock')) {
            return true;
        }
        foreach ($node as $child) {
            if (is_array($child) && $this->containsBasketCondition($child)) {
                return true;
            }
        }
        return false;
    }
}
