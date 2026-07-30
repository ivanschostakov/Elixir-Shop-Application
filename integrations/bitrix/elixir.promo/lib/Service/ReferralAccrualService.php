<?php

namespace Elixir\Promo\Service;

use Bitrix\Main\Application;
use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;

final class ReferralAccrualService
{
    private const MODULE_ID = 'elixir.promo';
    private const PURCHASE_TABLE = 'b_elixir_referral_app_purchase';

    public function quotePaidOrder(array $payload): array
    {
        if (!Loader::includeModule('main') || !Loader::includeModule('iblock')) {
            throw new \RuntimeException('required_module_unavailable');
        }

        $order = $this->normalizePaidOrder($payload);
        $buyer = $this->resolveUserByEmail($order['user_email']);
        (new PromoService())->lookup($order['promo']);

        $siteContext = new SiteDiscountContext();
        $discountContext = $siteContext->resolve($order['promo'], (int)$buyer['user_id']);
        $buyerDiscount = $this->userDiscountPercent($siteContext, (int)$buyer['user_id'], true);
        $referrerUserId = $this->referrerForAppliedPromo($discountContext, (int)$buyer['user_id']);
        $accruals = [];

        if ($referrerUserId > 0) {
            $referrerDiscount = $this->userDiscountPercent($siteContext, $referrerUserId, true);
            $accruals[] = $this->buildAccrual(
                $siteContext,
                $referrerUserId,
                (int)$buyer['user_id'],
                1,
                max(3.0, $referrerDiscount - $buyerDiscount),
                $referrerDiscount,
                $buyerDiscount,
                (float)$order['amount'],
                (string)$order['period']
            );

            $referrerProfile = $siteContext->getProgramProfile($referrerUserId);
            $superReferrerUserId = (int)($referrerProfile['referrer_user_id'] ?? 0);
            if ($superReferrerUserId > 0 && $superReferrerUserId !== (int)$buyer['user_id']) {
                $accruals[] = $this->buildAccrual(
                    $siteContext,
                    $superReferrerUserId,
                    (int)$buyer['user_id'],
                    2,
                    3.0,
                    $this->userDiscountPercent($siteContext, $superReferrerUserId, true),
                    $buyerDiscount,
                    (float)$order['amount'],
                    (string)$order['period']
                );
            }
        }

        return [
            'storage' => 'app',
            'bitrix_writes' => false,
            'promo' => $order['promo'],
            'promo_mode' => (string)$discountContext['mode'],
            'buyer' => $buyer,
            'buyer_discount_percent' => $buyerDiscount,
            'referrer_user_id' => $referrerUserId > 0 ? $referrerUserId : null,
            'amount' => $order['amount'],
            'currency' => $order['currency'],
            'paid_at' => $order['paid_at']->format(DATE_ATOM),
            'period' => $order['period'],
            'accruals' => $accruals,
        ];
    }

    public function recordPaidPurchase(array $payload): array
    {
        if (
            !Loader::includeModule('main')
            || !Loader::includeModule('iblock')
            || !Loader::includeModule('sale')
        ) {
            throw new \RuntimeException('required_module_unavailable');
        }

        $order = $this->normalizePaidOrder($payload);
        $buyer = $this->resolveUserByEmail($order['user_email']);
        $promoService = new PromoService();
        $promoLookup = $promoService->lookup($order['promo']);

        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $externalOrderSql = $sqlHelper->forSql($order['external_order_id'], 100);
        $existing = $connection->query(
            "SELECT ID FROM " . self::PURCHASE_TABLE . "
             WHERE SOURCE='app' AND EXTERNAL_ORDER_ID='" . $externalOrderSql . "'
             LIMIT 1"
        )->fetch();
        if (is_array($existing)) {
            return $this->purchaseResult((int)$existing['ID'], 'already_recorded');
        }

        $siteContext = new SiteDiscountContext();
        $assignment = $siteContext->attachReferrer($order['promo'], (int)$buyer['user_id']);
        $assignmentOutcome = (string)($assignment['outcome'] ?? '');
        $referrerUserId = in_array($assignmentOutcome, ['attached', 'changed', 'unchanged'], true)
            ? (int)($assignment['referrer_user_id'] ?? 0)
            : 0;

        $couponUsage = null;
        $connection->startTransaction();
        try {
            $promoSql = $sqlHelper->forSql($order['promo'], 100);
            $currencySql = $sqlHelper->forSql($order['currency'], 3);
            $periodSql = $sqlHelper->forSql($order['period'], 7);
            $paidAtSql = $sqlHelper->forSql($order['paid_at']->format('Y-m-d H:i:s'), 19);
            $connection->queryExecute(
                "INSERT IGNORE INTO " . self::PURCHASE_TABLE . "
                    (SOURCE, EXTERNAL_ORDER_ID, USER_ID, REFERRER_USER_ID, PROMO, AMOUNT, CURRENCY, PAID_AT, PERIOD, CREATED_AT)
                 VALUES
                    ('app', '" . $externalOrderSql . "', " . (int)$buyer['user_id'] . ", "
                    . ($referrerUserId > 0 ? $referrerUserId : 'NULL') . ", '" . $promoSql . "', "
                    . number_format((float)$order['amount'], 2, '.', '') . ", '" . $currencySql . "', '"
                    . $paidAtSql . "', '" . $periodSql . "', NOW())"
            );
            $purchaseId = (int)$connection->getInsertedId();
            if ($purchaseId <= 0) {
                $raceWinner = $connection->query(
                    "SELECT ID FROM " . self::PURCHASE_TABLE . "
                     WHERE SOURCE='app' AND EXTERNAL_ORDER_ID='" . $externalOrderSql . "'
                     LIMIT 1"
                )->fetch();
                if (!is_array($raceWinner)) {
                    throw new \RuntimeException('purchase_record_failed');
                }
                $connection->commitTransaction();
                return $this->purchaseResult((int)$raceWinner['ID'], 'already_recorded');
            }

            $couponUsage = $this->incrementCouponUseCount(
                (int)($promoLookup['coupon_id'] ?? 0)
            );
            $purchaseProgress = $siteContext->addPaidPurchase(
                (int)$buyer['user_id'],
                (float)$order['amount'],
                $order['currency']
            );
            $connection->commitTransaction();
        } catch (\Throwable $exception) {
            $connection->rollbackTransaction();
            throw $exception;
        }

        return $this->purchaseResult($purchaseId, 'recorded') + [
            'assignment' => $assignment,
            'coupon_usage' => $couponUsage,
            'purchase_progress' => $purchaseProgress,
        ];
    }

    public function recordPaidOrder(array $payload): array
    {
        $calculation = $this->quotePaidOrder($payload);
        $purchase = $this->recordPaidPurchase($payload);

        return $purchase + [
            'storage' => 'app',
            'bitrix_accrual_writes' => false,
            'accruals' => $calculation['accruals'],
            'calculation' => $calculation,
        ];
    }

    public function eligibility(array $payload): array
    {
        $period = trim((string)($payload['period'] ?? ''));
        if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $period)) {
            throw new \InvalidArgumentException('invalid_period');
        }

        $userId = isset($payload['user_id']) && is_numeric($payload['user_id'])
            ? max(0, (int)$payload['user_id'])
            : 0;
        if ($userId <= 0) {
            $userEmail = trim((string)($payload['user_email'] ?? ''));
            $userId = (int)$this->resolveUserByEmail($userEmail)['user_id'];
        }

        return $this->eligibilityForPeriod(new SiteDiscountContext(), $userId, $period);
    }

    public function removeLegacyAccrualStorage(): array
    {
        if (class_exists('\CAgent')) {
            \CAgent::RemoveAgent(
                '\\Elixir\\Promo\\Service\\ReferralAccrualService::finalizePreviousMonthAgent();',
                self::MODULE_ID
            );
        }

        $removedProperties = [];
        if (Loader::includeModule('iblock')) {
            foreach (['SOURCE_KEY', 'STATUS', 'PERIOD', 'LEVEL'] as $code) {
                $property = \CIBlockProperty::GetList(
                    [],
                    ['IBLOCK_ID' => 20, 'CODE' => $code]
                )->Fetch();
                if (is_array($property) && \CIBlockProperty::Delete((int)$property['ID'])) {
                    $removedProperties[] = $code;
                }
            }
        }

        $connection = Application::getConnection();
        if ($connection->isTableExists('b_elixir_referral_app_accrual')) {
            $connection->queryExecute('DROP TABLE b_elixir_referral_app_accrual');
        }

        return [
            'agent_removed' => true,
            'accrual_table_removed' => !$connection->isTableExists('b_elixir_referral_app_accrual'),
            'properties_removed' => $removedProperties,
            'purchase_tracking_retained' => $connection->isTableExists(self::PURCHASE_TABLE),
        ];
    }

    private function normalizePaidOrder(array $payload): array
    {
        $externalOrderId = trim((string)($payload['external_order_id'] ?? ''));
        $userEmail = trim((string)($payload['user_email'] ?? ''));
        $promo = trim((string)($payload['promo'] ?? ''));
        $currency = strtoupper(trim((string)($payload['currency'] ?? 'RUB')));
        $amount = round((float)($payload['amount'] ?? 0), 2);
        $paidAt = $this->parsePaidAt($payload['paid_at'] ?? null);
        if (
            $externalOrderId === ''
            || strlen($externalOrderId) > 100
            || !filter_var($userEmail, FILTER_VALIDATE_EMAIL)
            || $promo === ''
            || strlen($promo) > 100
            || $amount <= 0
            || $amount > 999999999999.99
            || !preg_match('/^[A-Z]{3}$/', $currency)
        ) {
            throw new \InvalidArgumentException('invalid_paid_order');
        }

        return [
            'external_order_id' => $externalOrderId,
            'user_email' => $userEmail,
            'promo' => $promo,
            'amount' => $amount,
            'currency' => $currency,
            'paid_at' => $paidAt,
            'period' => $paidAt->format('Y-m'),
        ];
    }

    private function referrerForAppliedPromo(array $discountContext, int $buyerUserId): int
    {
        if (
            !in_array(
                (string)($discountContext['mode'] ?? ''),
                [SiteDiscountContext::MODE_NATIVE, SiteDiscountContext::MODE_EXTERNAL],
                true
            )
            || !empty($discountContext['is_firm_promo'])
        ) {
            return 0;
        }

        $referrerUserId = (int)($discountContext['referral_owner_id'] ?? 0);
        return $referrerUserId > 0 && $referrerUserId !== $buyerUserId
            ? $referrerUserId
            : 0;
    }

    private function buildAccrual(
        SiteDiscountContext $siteContext,
        int $beneficiaryUserId,
        int $referralUserId,
        int $level,
        float $percent,
        float $referrerDiscount,
        float $referralDiscount,
        float $purchaseAmount,
        string $period
    ): array {
        $beneficiary = $this->userSnapshot($beneficiaryUserId);

        return [
            'beneficiary' => $beneficiary,
            'referral_user_id' => $referralUserId,
            'level' => $level,
            'percent' => round($percent, 2),
            'referrer_discount_percent' => round($referrerDiscount, 2),
            'referral_discount_percent' => round($referralDiscount, 2),
            'amount' => round($purchaseAmount * $percent / 100, 2),
            'period' => $period,
            'eligibility' => $this->eligibilityForPeriod(
                $siteContext,
                $beneficiaryUserId,
                $period
            ),
        ];
    }

    private function eligibilityForPeriod(
        SiteDiscountContext $siteContext,
        int $userId,
        string $period
    ): array {
        $periodStart = new \DateTimeImmutable($period . '-01 00:00:00');
        $periodEnd = $periodStart->modify('+1 month');
        $isClosed = $periodEnd <= new \DateTimeImmutable('first day of this month 00:00:00');
        $lifetimeTotal = $this->lifetimeProgramTotal($siteContext, $userId);
        $monthlyOwnPurchases = $this->monthlyOwnPurchases($userId, $periodStart, $periodEnd);
        $eligible = $lifetimeTotal >= 100000.0 && $monthlyOwnPurchases >= 10000.0;
        $reason = null;
        if ($isClosed && !$eligible) {
            $reason = $lifetimeTotal < 100000.0
                ? 'lifetime_purchase_minimum_not_met'
                : 'monthly_purchase_minimum_not_met';
        }

        return [
            'user_id' => $userId,
            'period' => $period,
            'period_closed' => $isClosed,
            'status' => !$isClosed ? 'pending' : ($eligible ? 'approved' : 'rejected'),
            'eligible' => $isClosed ? $eligible : null,
            'reason' => $reason,
            'lifetime_purchase_total' => $lifetimeTotal,
            'monthly_own_purchase_total' => $monthlyOwnPurchases,
            'lifetime_minimum' => 100000.0,
            'monthly_minimum' => 10000.0,
            'currency' => (string)Option::get(self::MODULE_ID, 'currency', 'RUB'),
        ];
    }

    private function resolveUserByEmail(string $email): array
    {
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            throw new \InvalidArgumentException('invalid_user_email');
        }

        $connection = Application::getConnection();
        $emailSql = $connection->getSqlHelper()->forSql($email, 254);
        $row = $connection->query(
            "SELECT ID, EMAIL, NAME, LAST_NAME
             FROM b_user
             WHERE ACTIVE='Y' AND EMAIL='" . $emailSql . "'
             ORDER BY ID ASC
             LIMIT 1"
        )->fetch();
        if (!is_array($row)) {
            throw new \DomainException('user_not_found');
        }

        return [
            'user_id' => (int)$row['ID'],
            'email' => (string)$row['EMAIL'],
            'name' => trim((string)$row['NAME'] . ' ' . (string)$row['LAST_NAME']),
        ];
    }

    private function userSnapshot(int $userId): array
    {
        $row = Application::getConnection()->query(
            "SELECT ID, EMAIL, NAME, LAST_NAME
             FROM b_user
             WHERE ID=" . $userId . " AND ACTIVE='Y'
             LIMIT 1"
        )->fetch();
        if (!is_array($row)) {
            throw new \DomainException('user_not_found');
        }

        return [
            'user_id' => (int)$row['ID'],
            'email' => trim((string)$row['EMAIL']) ?: null,
            'name' => trim((string)$row['NAME'] . ' ' . (string)$row['LAST_NAME']),
        ];
    }

    private function userDiscountPercent(
        SiteDiscountContext $siteContext,
        int $userId,
        bool $minimumForParticipant
    ): float {
        $profile = $siteContext->getProgramProfile($userId);
        $discount = max(
            (float)($profile['group_discount_percent'] ?? 0),
            (float)($profile['stored_discount_percent'] ?? 0)
        );

        return $minimumForParticipant ? max(3.0, $discount) : max(0.0, $discount);
    }

    private function lifetimeProgramTotal(SiteDiscountContext $siteContext, int $userId): float
    {
        $profile = $siteContext->getProgramProfile($userId);

        return round((float)($profile['order_sum']['amount'] ?? 0), 2);
    }

    private function monthlyOwnPurchases(
        int $userId,
        \DateTimeImmutable $periodStart,
        \DateTimeImmutable $periodEnd
    ): float {
        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $fromSql = $sqlHelper->forSql($periodStart->format('Y-m-d H:i:s'), 19);
        $toSql = $sqlHelper->forSql($periodEnd->format('Y-m-d H:i:s'), 19);

        $websiteRow = $connection->query(
            "SELECT COALESCE(SUM(PRICE), 0) AS TOTAL
             FROM b_sale_order
             WHERE USER_ID=" . $userId . "
               AND PAYED='Y'
               AND CANCELED='N'
               AND DATE_PAYED>='" . $fromSql . "'
               AND DATE_PAYED<'" . $toSql . "'"
        )->fetch();
        $appRow = $connection->query(
            "SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL
             FROM " . self::PURCHASE_TABLE . "
             WHERE USER_ID=" . $userId . "
               AND PAID_AT>='" . $fromSql . "'
               AND PAID_AT<'" . $toSql . "'"
        )->fetch();

        return round(
            (float)($websiteRow['TOTAL'] ?? 0) + (float)($appRow['TOTAL'] ?? 0),
            2
        );
    }

    private function purchaseResult(int $purchaseId, string $outcome): array
    {
        $purchase = Application::getConnection()->query(
            "SELECT ID, SOURCE, EXTERNAL_ORDER_ID, USER_ID, REFERRER_USER_ID, PROMO,
                    AMOUNT, CURRENCY, PAID_AT, PERIOD
             FROM " . self::PURCHASE_TABLE . "
             WHERE ID=" . $purchaseId . "
             LIMIT 1"
        )->fetch();
        if (!is_array($purchase)) {
            throw new \RuntimeException('purchase_not_found');
        }

        return [
            'outcome' => $outcome,
            'storage' => 'bitrix_purchase_progress_only',
            'accrual_storage' => 'app',
            'purchase' => [
                'id' => (int)$purchase['ID'],
                'source' => (string)$purchase['SOURCE'],
                'external_order_id' => (string)$purchase['EXTERNAL_ORDER_ID'],
                'user_id' => (int)$purchase['USER_ID'],
                'referrer_user_id' => (int)($purchase['REFERRER_USER_ID'] ?? 0) > 0
                    ? (int)$purchase['REFERRER_USER_ID']
                    : null,
                'promo' => (string)$purchase['PROMO'],
                'amount' => round((float)$purchase['AMOUNT'], 2),
                'currency' => (string)$purchase['CURRENCY'],
                'paid_at' => (string)$purchase['PAID_AT'],
                'period' => (string)$purchase['PERIOD'],
            ],
        ];
    }

    private function incrementCouponUseCount(int $couponId): array
    {
        if ($couponId <= 0) {
            throw new \RuntimeException('coupon_not_found');
        }

        $connection = Application::getConnection();
        $tableName = \Bitrix\Sale\Internals\DiscountCouponTable::getTableName();
        $connection->queryExecute(
            "UPDATE " . $tableName . "
             SET USE_COUNT=COALESCE(USE_COUNT, 0) + 1
             WHERE ID=" . $couponId
        );
        $row = $connection->query(
            "SELECT ID, USE_COUNT
             FROM " . $tableName . "
             WHERE ID=" . $couponId . "
             LIMIT 1"
        )->fetch();
        if (!is_array($row)) {
            throw new \RuntimeException('coupon_usage_update_failed');
        }

        return [
            'coupon_id' => (int)$row['ID'],
            'use_count' => (int)$row['USE_COUNT'],
            'source' => 'app_paid_order',
        ];
    }

    private function parsePaidAt($value): \DateTimeImmutable
    {
        $value = trim((string)$value);
        if ($value === '') {
            return new \DateTimeImmutable();
        }
        try {
            return new \DateTimeImmutable($value);
        } catch (\Throwable $exception) {
            throw new \InvalidArgumentException('invalid_paid_at');
        }
    }
}
