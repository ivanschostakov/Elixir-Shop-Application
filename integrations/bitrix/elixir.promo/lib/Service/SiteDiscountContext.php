<?php

namespace Elixir\Promo\Service;

use Bitrix\Main\Application;
use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Bitrix\Sale\Internals\DiscountCouponTable;
use Bitrix\Sale\Internals\DiscountTable;

final class SiteDiscountContext
{
    public const MODE_NONE = 'none';
    public const MODE_OWN = 'own';
    public const MODE_NATIVE = 'native';
    public const MODE_EXTERNAL = 'external';

    private const WEBSITE_MODULE_ID = 'elixir.amocrmbridge';
    private const OPTION_MIN_GROUP_ID = 'promo_min_discount_group_id';
    private const OPTION_LOYALTY_GROUP_IDS = 'promo_loyalty_group_ids';
    private const OPTION_FIRM_PROMO_CODES = 'promo_firm_promo_codes';

    public function resolve(string $promoCode, int $userId): array
    {
        $promoCode = trim($promoCode);
        $knownCoupon = $this->isKnownSaleCoupon($promoCode);
        $referralOwnerId = $this->findReferralOwnerId($promoCode);
        $firmPromo = $this->isFirmPromoCode($promoCode);
        $ownPromo = $userId > 0 ? $this->getUserOwnPromo($userId) : '';
        $nativePromo = $userId > 0 ? $this->getUserDefaultPromo($userId, $ownPromo) : '';

        $mode = self::MODE_NONE;
        if ($userId > 0 && $this->samePromo($promoCode, $ownPromo)) {
            $mode = self::MODE_OWN;
        } elseif ($userId > 0 && $this->samePromo($promoCode, $nativePromo)) {
            $mode = self::MODE_NATIVE;
        } elseif ($knownCoupon || $referralOwnerId > 0 || $firmPromo) {
            $mode = self::MODE_EXTERNAL;
        }

        $baseGroups = $userId > 0 && class_exists('\CUser')
            ? (array)\CUser::GetUserGroup($userId)
            : [2];
        $runtimeGroups = $this->buildRuntimeGroups($baseGroups, $mode, $knownCoupon);

        return [
            'mode' => $mode,
            'user_id' => max(0, $userId),
            'own_promo' => $ownPromo !== '' ? $ownPromo : null,
            'native_promo' => $nativePromo !== '' ? $nativePromo : null,
            'referral_owner_id' => $referralOwnerId > 0 ? $referralOwnerId : null,
            'is_firm_promo' => $firmPromo,
            'is_known_coupon' => $knownCoupon,
            'use_coupon' => $mode === self::MODE_EXTERNAL && $knownCoupon,
            'base_user_groups' => $this->normalizeGroupList($baseGroups),
            'runtime_user_groups' => $runtimeGroups,
            'effective_discount_percent' => $this->discountPercentForGroups($runtimeGroups),
        ];
    }

    public function getProgramProfile(int $userId): array
    {
        if ($userId <= 0) {
            throw new \InvalidArgumentException('invalid_user');
        }

        $connection = Application::getConnection();
        $row = $connection->query(
            "SELECT UF_PROMO, UF_PARENT_ID, UF_PERCENT, UF_ORDER_SUMM, UF_SUM_PAID_ORDERS_MONTH
             FROM b_uts_user
             WHERE VALUE_ID=" . $userId . "
             LIMIT 1"
        )->fetch();
        if (!is_array($row)) {
            throw new \DomainException('user_not_found');
        }

        $groups = class_exists('\CUser')
            ? $this->normalizeGroupList((array)\CUser::GetUserGroup($userId))
            : [];
        $ownPromo = trim((string)($row['UF_PROMO'] ?? ''));
        $firmPromoCodes = $this->getFirmPromoCodes();
        $purchaseTotal = round((float)($this->parseMoney(
            $row['UF_ORDER_SUMM'] ?? null
        )['amount'] ?? 0), 2);
        $nextThreshold = null;
        if ($purchaseTotal < 30000.0) {
            $nextThreshold = 30000.0;
        } elseif ($purchaseTotal < 200000.0) {
            $nextThreshold = min(
                200000.0,
                (floor($purchaseTotal / 10000.0) + 1.0) * 10000.0
            );
        }

        return [
            'user_id' => $userId,
            'own_promo' => $ownPromo !== '' ? $ownPromo : null,
            'referrer_user_id' => (int)($row['UF_PARENT_ID'] ?? 0) > 0
                ? (int)$row['UF_PARENT_ID']
                : null,
            'referrer_promo' => ($referrerPromo = $this->getUserDefaultPromo($userId, $ownPromo)) !== ''
                ? $referrerPromo
                : null,
            'stored_discount_percent' => is_numeric($row['UF_PERCENT'] ?? null)
                ? (float)$row['UF_PERCENT']
                : null,
            'group_discount_percent' => $this->discountPercentForGroups($groups),
            'order_sum' => $this->parseMoney($row['UF_ORDER_SUMM'] ?? null),
            'sum_paid_orders_month' => $this->parseMoney($row['UF_SUM_PAID_ORDERS_MONTH'] ?? null),
            'user_groups' => $groups,
            'personal_purchase_total' => $purchaseTotal,
            'personal_discount_next_threshold' => $nextThreshold,
            'personal_discount_remaining' => $nextThreshold !== null
                ? max(0.0, round($nextThreshold - $purchaseTotal, 2))
                : 0.0,
            'partner_unlock_threshold' => 100000.0,
            'partner_unlock_remaining' => max(
                0.0,
                round(100000.0 - $purchaseTotal, 2)
            ),
            'partner_unlocked' => $ownPromo !== '' || $purchaseTotal >= 100000.0,
            'firm_promo_codes' => $firmPromoCodes,
            'suggested_promo' => $firmPromoCodes[0] ?? null,
        ];
    }

    public function addPaidPurchase(int $userId, float $amount, string $currency = 'RUB'): array
    {
        if ($userId <= 0 || $amount <= 0 || !class_exists('\CUser')) {
            throw new \InvalidArgumentException('invalid_paid_purchase');
        }

        $profile = $this->getProgramProfile($userId);
        $previousTotal = round((float)($profile['order_sum']['amount'] ?? 0), 2);
        $newTotal = round($previousTotal + $amount, 2);
        $result = $this->applyPurchaseTotal($userId, $previousTotal, $newTotal, $currency);

        if ($newTotal >= 100000.0) {
            $this->ensureOwnPromoForEligibleUser($userId);
        }

        return $result;
    }

    public function subtractPaidPurchase(int $userId, float $amount, string $currency = 'RUB'): array
    {
        if ($userId <= 0 || $amount <= 0 || !class_exists('\CUser')) {
            throw new \InvalidArgumentException('invalid_paid_purchase');
        }

        $profile = $this->getProgramProfile($userId);
        $previousTotal = round((float)($profile['order_sum']['amount'] ?? 0), 2);
        $newTotal = max(0.0, round($previousTotal - $amount, 2));

        return $this->applyPurchaseTotal($userId, $previousTotal, $newTotal, $currency);
    }

    public function setOpeningPurchaseBalance(
        int $userId,
        float $amount,
        string $currency = 'RUB'
    ): array {
        if ($userId <= 0 || $amount < 0 || $amount > 999999999999.99) {
            throw new \InvalidArgumentException('invalid_opening_balance');
        }
        $profile = $this->getProgramProfile($userId);
        $previousTotal = round((float)($profile['order_sum']['amount'] ?? 0), 2);
        $newTotal = round($amount, 2);
        $result = $this->applyPurchaseTotal(
            $userId,
            $previousTotal,
            $newTotal,
            strtoupper(trim($currency)) ?: 'RUB'
        );
        if ($newTotal >= 100000.0) {
            $this->ensureOwnPromoForEligibleUser($userId);
        }

        return ['source' => 'admin_opening_balance'] + $result;
    }

    private function applyPurchaseTotal(
        int $userId,
        float $previousTotal,
        float $newTotal,
        string $currency
    ): array {
        $currency = strtoupper(trim($currency)) ?: 'RUB';
        $rateMap = $this->getLoyaltyGroupRateMap();
        $targetGroupId = 0;
        $targetRate = 0.0;
        foreach ($rateMap as $groupId => $rate) {
            $threshold = max(30000.0, (float)$rate * 10000.0);
            if ($newTotal >= $threshold && (float)$rate > $targetRate) {
                $targetGroupId = (int)$groupId;
                $targetRate = (float)$rate;
            }
        }

        $groups = array_values(array_diff(
            (array)\CUser::GetUserGroup($userId),
            $this->getLoyaltyGroupIds()
        ));
        if ($targetGroupId > 0) {
            $groups[] = $targetGroupId;
        }
        \CUser::SetUserGroup($userId, $this->normalizeGroupList($groups));

        $userApi = new \CUser();
        if (!$userApi->Update($userId, [
            'UF_ORDER_SUMM' => number_format($newTotal, 2, '.', '') . '|' . $currency,
            'UF_PERCENT' => $targetRate,
        ])) {
            throw new \RuntimeException('purchase_total_update_failed');
        }

        return [
            'previous_total' => $previousTotal,
            'new_total' => $newTotal,
            'currency' => $currency,
            'discount_percent' => $targetRate,
            'discount_group_id' => $targetGroupId > 0 ? $targetGroupId : null,
        ];
    }

    private function ensureOwnPromoForEligibleUser(int $userId): void
    {
        $userData = \CUser::GetByID($userId)->Fetch();
        if (!is_array($userData)) {
            throw new \DomainException('user_not_found');
        }
        if (trim((string)($userData['UF_PROMO'] ?? '')) !== '') {
            return;
        }

        $name = trim((string)($userData['NAME'] ?? ''));
        if ($name === '') {
            $name = 'User';
        }
        $transliteratedName = class_exists('\CUtil')
            ? (string)\CUtil::translit(
                $name,
                'ru',
                ['replace_space' => '_', 'replace_other' => '_']
            )
            : preg_replace('/[^a-z0-9]+/i', '_', $name);
        $transliteratedName = trim((string)$transliteratedName, '_');
        if ($transliteratedName === '') {
            $transliteratedName = 'USER';
        }
        $promo = strtoupper($transliteratedName) . '_' . $userId;

        (new PromoService())->ensureCouponForUser($userId, $promo);
        $userApi = new \CUser();
        if (!$userApi->Update($userId, ['UF_PROMO' => $promo])) {
            throw new \RuntimeException('own_promo_assignment_failed');
        }

        $email = trim((string)($userData['EMAIL'] ?? ''));
        if ($email !== '' && class_exists('\CEvent')) {
            \CEvent::Send('NEW_PROMO_CODE', 's1', [
                'EMAIL' => $email,
                'PROMO_CODE' => $promo,
            ]);
        }
    }

    public function attachReferrer(string $promoCode, int $userId): array
    {
        $promoCode = trim($promoCode);
        if ($promoCode === '' || $userId <= 0) {
            throw new \InvalidArgumentException('invalid_referrer_assignment');
        }

        $ownPromo = $this->getUserOwnPromo($userId);
        if ($this->samePromo($promoCode, $ownPromo)) {
            throw new \DomainException('own_promo_not_allowed');
        }

        if ($this->isFirmPromoCode($promoCode)) {
            $this->resetReferralProgress($userId, 0);
            return [
                'outcome' => 'firm_promo',
                'user_id' => $userId,
                'referrer_user_id' => null,
                'progress_reset' => true,
            ];
        }

        $referrerUserId = $this->findReferralOwnerId($promoCode);
        if ($referrerUserId <= 0) {
            if ($this->isKnownSaleCoupon($promoCode)) {
                return [
                    'outcome' => 'sale_coupon',
                    'user_id' => $userId,
                    'referrer_user_id' => null,
                    'progress_reset' => false,
                ];
            }
            throw new \DomainException('promo_not_found');
        }
        if ($referrerUserId === $userId || $this->wouldCreateCycle($userId, $referrerUserId)) {
            throw new \DomainException('referral_cycle_not_allowed');
        }

        $currentParentId = $this->getUserParentId($userId);
        if ($currentParentId === $referrerUserId) {
            return [
                'outcome' => 'unchanged',
                'user_id' => $userId,
                'referrer_user_id' => $referrerUserId,
                'progress_reset' => false,
            ];
        }

        $this->resetReferralProgress($userId, $referrerUserId);

        return [
            'outcome' => $currentParentId > 0 ? 'changed' : 'attached',
            'user_id' => $userId,
            'referrer_user_id' => $referrerUserId,
            'previous_referrer_user_id' => $currentParentId > 0 ? $currentParentId : null,
            'progress_reset' => true,
        ];
    }

    public function detachReferrer(int $userId): array
    {
        if ($userId <= 0) {
            throw new \InvalidArgumentException('invalid_referrer_assignment');
        }

        $currentParentId = $this->getUserParentId($userId);
        if ($currentParentId <= 0) {
            $this->resetReferralProgress($userId, 0);
            return [
                'outcome' => 'detached',
                'user_id' => $userId,
                'previous_referrer_user_id' => null,
                'progress_reset' => true,
            ];
        }

        $this->resetReferralProgress($userId, 0);

        return [
            'outcome' => 'detached',
            'user_id' => $userId,
            'previous_referrer_user_id' => $currentParentId,
            'progress_reset' => true,
        ];
    }

    public function overrideUserGroupCache(int $userId, array $runtimeGroups): ?array
    {
        if ($userId <= 0 || !class_exists('\CUser')) {
            return null;
        }

        try {
            $reflection = new \ReflectionClass('\CUser');
            if (!$reflection->hasProperty('userGroupCache')) {
                return null;
            }

            $property = $reflection->getProperty('userGroupCache');
            $property->setAccessible(true);
            $cache = (array)$property->getValue();
            $snapshot = [
                'had_value' => array_key_exists($userId, $cache),
                'value' => $cache[$userId] ?? null,
            ];
            $cache[$userId] = $this->normalizeGroupList($runtimeGroups);
            $property->setValue(null, $cache);

            return $snapshot;
        } catch (\Throwable $exception) {
            return null;
        }
    }

    public function restoreUserGroupCache(int $userId, ?array $snapshot): void
    {
        if ($userId <= 0 || $snapshot === null || !class_exists('\CUser')) {
            return;
        }

        try {
            $reflection = new \ReflectionClass('\CUser');
            if (!$reflection->hasProperty('userGroupCache')) {
                return;
            }

            $property = $reflection->getProperty('userGroupCache');
            $property->setAccessible(true);
            $cache = (array)$property->getValue();
            if (!empty($snapshot['had_value'])) {
                $cache[$userId] = $snapshot['value'];
            } else {
                unset($cache[$userId]);
            }
            $property->setValue(null, $cache);
        } catch (\Throwable $exception) {
        }
    }

    private function buildRuntimeGroups(array $baseGroups, string $mode, bool $knownCoupon): array
    {
        $groups = $this->normalizeGroupList($baseGroups);
        $loyaltyGroups = $this->getLoyaltyGroupIds();
        $minimumGroupId = $this->getMinimumDiscountGroupId();
        $runtimeGroups = $loyaltyGroups === []
            ? $groups
            : array_values(array_diff($groups, $loyaltyGroups));

        if ($mode === self::MODE_NATIVE) {
            $runtimeGroups = $groups;
            if (array_intersect($groups, $loyaltyGroups) === [] && $minimumGroupId > 0) {
                $runtimeGroups[] = $minimumGroupId;
            }
        } elseif ($mode === self::MODE_EXTERNAL && !$knownCoupon && $minimumGroupId > 0) {
            $runtimeGroups[] = $minimumGroupId;
        }

        if (!in_array(2, $runtimeGroups, true)) {
            $runtimeGroups[] = 2;
        }

        return $this->normalizeGroupList($runtimeGroups);
    }

    private function resetReferralProgress(int $userId, int $parentId): void
    {
        if (!class_exists('\CUser')) {
            throw new \RuntimeException('user_api_unavailable');
        }

        $connection = Application::getConnection();
        $connection->startTransaction();
        try {
            $groups = array_values(array_diff(
                (array)\CUser::GetUserGroup($userId),
                $this->getLoyaltyGroupIds()
            ));
            \CUser::SetUserGroup($userId, $this->normalizeGroupList($groups));

            $fields = [
                'UF_PARENT_ID' => $parentId > 0 ? $parentId : false,
                'UF_ORDER_SUMM' => '0|RUB',
                'UF_PERCENT' => 0,
            ];
            $userApi = new \CUser();
            if (!$userApi->Update($userId, $fields)) {
                throw new \RuntimeException('referrer_assignment_failed');
            }
            $connection->commitTransaction();
        } catch (\Throwable $exception) {
            $connection->rollbackTransaction();
            throw $exception;
        }
    }

    private function wouldCreateCycle(int $userId, int $candidateParentId): bool
    {
        $visited = [];
        $currentId = $candidateParentId;
        for ($depth = 0; $depth < 100 && $currentId > 0; $depth++) {
            if ($currentId === $userId || isset($visited[$currentId])) {
                return true;
            }
            $visited[$currentId] = true;
            $currentId = $this->getUserParentId($currentId);
        }

        return $currentId > 0;
    }

    private function getUserParentId(int $userId): int
    {
        if ($userId <= 0) {
            return 0;
        }

        $connection = Application::getConnection();
        $row = $connection->query(
            'SELECT UF_PARENT_ID FROM b_uts_user WHERE VALUE_ID=' . $userId . ' LIMIT 1'
        )->fetch();

        return is_array($row) ? max(0, (int)($row['UF_PARENT_ID'] ?? 0)) : 0;
    }

    private function getUserDefaultPromo(int $userId, string $ownPromo): string
    {
        $parentId = $this->getUserParentId($userId);
        if ($parentId <= 0) {
            return '';
        }

        $promo = $this->getUserOwnPromo($parentId);
        if ($this->samePromo($promo, $ownPromo)) {
            return '';
        }

        return $promo;
    }

    private function getUserOwnPromo(int $userId): string
    {
        if ($userId <= 0) {
            return '';
        }

        $connection = Application::getConnection();
        $row = $connection->query(
            'SELECT UF_PROMO FROM b_uts_user WHERE VALUE_ID=' . $userId . ' LIMIT 1'
        )->fetch();

        return is_array($row) ? trim((string)($row['UF_PROMO'] ?? '')) : '';
    }

    private function findReferralOwnerId(string $promoCode): int
    {
        $normalizedPromo = $this->normalizePromo($promoCode);
        if ($normalizedPromo === '') {
            return 0;
        }

        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $row = $connection->query(sprintf(
            "SELECT u.ID
             FROM b_user u
             INNER JOIN b_uts_user uts ON uts.VALUE_ID=u.ID
             WHERE u.ACTIVE='Y' AND LOWER(TRIM(uts.UF_PROMO))='%s'
             ORDER BY u.ID ASC
             LIMIT 1",
            $sqlHelper->forSql($normalizedPromo, 100)
        ))->fetch();

        return is_array($row) ? (int)$row['ID'] : 0;
    }

    private function isKnownSaleCoupon(string $promoCode): bool
    {
        if (!Loader::includeModule('sale')) {
            return false;
        }

        $normalizedPromo = $this->normalizePromo($promoCode);
        if ($normalizedPromo === '') {
            return false;
        }

        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $tableName = DiscountCouponTable::getTableName();
        $row = $connection->query(sprintf(
            "SELECT ID
             FROM %s
             WHERE ACTIVE='Y' AND LOWER(TRIM(COUPON))='%s'
             LIMIT 1",
            $tableName,
            $sqlHelper->forSql($normalizedPromo, 100)
        ))->fetch();

        return is_array($row);
    }

    public function getFirmPromoCodes(): array
    {
        $configured = Option::get(
            self::WEBSITE_MODULE_ID,
            self::OPTION_FIRM_PROMO_CODES,
            'Elixir'
        );
        $codes = preg_split('/[\s,;]+/', $configured) ?: [];
        $result = [];
        foreach ($codes as $code) {
            $code = trim((string)$code);
            if ($code !== '') {
                $result[strtolower($code)] = $code;
            }
        }

        return array_values($result);
    }

    private function isFirmPromoCode(string $promoCode): bool
    {
        foreach ($this->getFirmPromoCodes() as $code) {
            if ($this->samePromo($promoCode, (string)$code)) {
                return true;
            }
        }

        return false;
    }

    private function getMinimumDiscountGroupId(): int
    {
        $configured = (int)Option::get(
            self::WEBSITE_MODULE_ID,
            self::OPTION_MIN_GROUP_ID,
            '0'
        );
        if ($configured > 0) {
            return $configured;
        }

        foreach ($this->getLoyaltyGroupRateMap() as $groupId => $rate) {
            if (abs($rate - 3.0) < 0.0001) {
                return (int)$groupId;
            }
        }

        return 0;
    }

    private function getLoyaltyGroupIds(): array
    {
        $configured = Option::get(
            self::WEBSITE_MODULE_ID,
            self::OPTION_LOYALTY_GROUP_IDS,
            ''
        );
        $configuredIds = [];
        foreach (preg_split('/[\s,;]+/', $configured) ?: [] as $part) {
            $groupId = (int)$part;
            if ($groupId > 0) {
                $configuredIds[] = $groupId;
            }
        }
        if ($configuredIds !== []) {
            return $this->normalizeGroupList($configuredIds);
        }

        return $this->normalizeGroupList(array_keys($this->getLoyaltyGroupRateMap()));
    }

    private function getLoyaltyGroupRateMap(): array
    {
        static $rateMap = null;
        if (is_array($rateMap)) {
            return $rateMap;
        }

        $rateMap = [];
        if (!Loader::includeModule('sale')) {
            return $rateMap;
        }

        $rows = DiscountTable::getList([
            'filter' => [
                '=ACTIVE' => 'Y',
                '=USE_COUPONS' => 'N',
            ],
            'select' => ['CONDITIONS_LIST', 'ACTIONS_LIST'],
        ]);
        while ($row = $rows->fetch()) {
            $conditions = (array)($row['CONDITIONS_LIST'] ?? []);
            if (!$this->containsReferralCondition($conditions)) {
                continue;
            }
            $groupIds = $this->extractConditionGroupIds($conditions);
            $rate = $this->extractPercentageDiscount((array)($row['ACTIONS_LIST'] ?? []));
            if ($groupIds === [] || $rate < 3 || $rate > 20) {
                continue;
            }
            foreach ($groupIds as $groupId) {
                $rateMap[(int)$groupId] = $rate;
            }
        }
        ksort($rateMap, SORT_NUMERIC);

        return $rateMap;
    }

    private function containsReferralCondition(array $node): bool
    {
        if (
            (string)($node['CLASS_ID'] ?? '') === 'CondSaleCmnAdvPHPExp'
            && trim((string)($node['DATA']['value'] ?? '')) === 'check_loyalty_program_referal()'
        ) {
            return true;
        }
        foreach ((array)($node['CHILDREN'] ?? []) as $child) {
            if (is_array($child) && $this->containsReferralCondition($child)) {
                return true;
            }
        }

        return false;
    }

    private function extractConditionGroupIds(array $node): array
    {
        $groupIds = [];
        if ((string)($node['CLASS_ID'] ?? '') === 'BX:CondMainUserGroupId') {
            foreach ((array)($node['DATA']['value'] ?? []) as $groupId) {
                if ((int)$groupId > 0) {
                    $groupIds[] = (int)$groupId;
                }
            }
        }
        foreach ((array)($node['CHILDREN'] ?? []) as $child) {
            if (is_array($child)) {
                $groupIds = array_merge($groupIds, $this->extractConditionGroupIds($child));
            }
        }

        return $this->normalizeGroupList($groupIds);
    }

    private function extractPercentageDiscount(array $node): float
    {
        if (
            (string)($node['CLASS_ID'] ?? '') === 'ActSaleBsktGrp'
            && (string)($node['DATA']['Type'] ?? '') === 'Discount'
            && (string)($node['DATA']['Unit'] ?? '') === 'Perc'
        ) {
            return (float)($node['DATA']['Value'] ?? 0);
        }
        foreach ((array)($node['CHILDREN'] ?? []) as $child) {
            if (!is_array($child)) {
                continue;
            }
            $rate = $this->extractPercentageDiscount($child);
            if ($rate > 0) {
                return $rate;
            }
        }

        return 0.0;
    }

    private function discountPercentForGroups(array $groupIds): ?float
    {
        $rates = [];
        $rateMap = $this->getLoyaltyGroupRateMap();
        foreach ($groupIds as $groupId) {
            if (isset($rateMap[$groupId])) {
                $rates[] = (float)$rateMap[$groupId];
            }
        }

        return $rates === [] ? null : max($rates);
    }

    private function normalizeGroupList(array $groups): array
    {
        $result = [];
        foreach ($groups as $groupId) {
            $groupId = (int)$groupId;
            if ($groupId > 0) {
                $result[] = $groupId;
            }
        }
        $result = array_values(array_unique($result));
        sort($result, SORT_NUMERIC);

        return $result;
    }

    private function parseMoney($value): array
    {
        $value = trim((string)$value);
        if ($value === '') {
            return [
                'amount' => 0.0,
                'currency' => (string)Option::get('elixir.promo', 'currency', 'RUB'),
            ];
        }

        $parts = explode('|', $value, 2);

        return [
            'amount' => is_numeric($parts[0] ?? null) ? round((float)$parts[0], 2) : 0.0,
            'currency' => trim((string)($parts[1] ?? '')) !== ''
                ? trim((string)$parts[1])
                : (string)Option::get('elixir.promo', 'currency', 'RUB'),
        ];
    }

    private function samePromo(string $first, string $second): bool
    {
        $first = $this->normalizePromo($first);
        $second = $this->normalizePromo($second);

        return $first !== '' && $first === $second;
    }

    private function normalizePromo(string $promoCode): string
    {
        $promoCode = trim($promoCode);
        if ($promoCode === '') {
            return '';
        }

        return function_exists('mb_strtolower')
            ? mb_strtolower($promoCode, 'UTF-8')
            : strtolower($promoCode);
    }
}
