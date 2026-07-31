<?php

namespace Elixir\Promo\Service;

use Bitrix\Main\Application;
use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;

final class ReferralAccrualService
{
    private const MODULE_ID = 'elixir.promo';
    private const PURCHASE_TABLE = 'b_elixir_referral_app_purchase';
    private const ACCRUAL_TABLE = 'b_elixir_referral_partner_accrual';
    private const NETWORK_MONTHLY_TABLE = 'b_elixir_partner_network_monthly';

    public static function finalizePreviousMonthAgent(): string
    {
        $agentName = '\\Elixir\\Promo\\Service\\ReferralAccrualService::finalizePreviousMonthAgent();';
        try {
            if (Loader::includeModule(self::MODULE_ID)) {
                $service = new self();
                $period = (new \DateTimeImmutable('first day of last month'))->format('Y-m');
                $service->finalizePeriodForAll($period);
            }
        } catch (\Throwable $exception) {
            if (function_exists('AddMessage2Log')) {
                AddMessage2Log(
                    'Partner month finalization failed: ' . $exception->getMessage(),
                    self::MODULE_ID
                );
            }
        }

        return $agentName;
    }

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
        $participatesInProgram = $referrerUserId > 0
            || !empty($discountContext['is_firm_promo']);
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
            'storage' => 'calculation',
            'bitrix_writes' => false,
            'promo' => $order['promo'],
            'promo_mode' => (string)$discountContext['mode'],
            'participates_in_program' => $participatesInProgram,
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

        $order = $this->normalizePaidOrder($payload, false);
        $buyer = $this->resolveUserByEmail($order['user_email']);
        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $externalOrderSql = $sqlHelper->forSql($order['external_order_id'], 100);
        $siteContext = new SiteDiscountContext();
        $connection->startTransaction();
        try {
            $existing = $connection->query(
                "SELECT ID FROM " . self::PURCHASE_TABLE . "
                 WHERE SOURCE='app' AND EXTERNAL_ORDER_ID='" . $externalOrderSql . "'
                 LIMIT 1 FOR UPDATE"
            )->fetch();
            if (is_array($existing)) {
                $connection->commitTransaction();
                return $this->purchaseResult((int)$existing['ID'], 'already_recorded');
            }

            $promoSql = $sqlHelper->forSql($order['promo'], 100);
            $currencySql = $sqlHelper->forSql($order['currency'], 3);
            $periodSql = $sqlHelper->forSql($order['period'], 7);
            $paidAtSql = $sqlHelper->forSql($order['paid_at']->format('Y-m-d H:i:s'), 19);
            $connection->queryExecute(
                "INSERT IGNORE INTO " . self::PURCHASE_TABLE . "
                    (SOURCE, EXTERNAL_ORDER_ID, USER_ID, REFERRER_USER_ID, PROMO,
                     AMOUNT, CURRENCY, PAID_AT, PERIOD, PROGRAM, STATUS, CREATED_AT, UPDATED_AT)
                 VALUES
                    ('app', '" . $externalOrderSql . "', " . (int)$buyer['user_id'] . ",
                     NULL, '" . $promoSql . "', "
                    . number_format((float)$order['amount'], 2, '.', '') . ", '" . $currencySql . "', '"
                    . $paidAtSql . "', '" . $periodSql . "', 'combined', 'posted', NOW(), NOW())"
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

            $promoLookup = null;
            $assignment = [
                'outcome' => 'no_promo',
                'user_id' => (int)$buyer['user_id'],
                'referrer_user_id' => null,
                'progress_reset' => false,
            ];
            $calculation = [
                'promo' => null,
                'promo_mode' => SiteDiscountContext::MODE_NONE,
                'participates_in_program' => false,
                'buyer' => $buyer,
                'amount' => $order['amount'],
                'currency' => $order['currency'],
                'paid_at' => $order['paid_at']->format(DATE_ATOM),
                'period' => $order['period'],
                'accruals' => [],
            ];
            if ($order['promo'] !== '') {
                $promoLookup = (new PromoService())->lookup($order['promo']);
                $discountContext = $siteContext->resolve(
                    $order['promo'],
                    (int)$buyer['user_id']
                );
                $assignment = !empty($discountContext['is_firm_promo'])
                    ? [
                        'outcome' => 'firm_promo',
                        'user_id' => (int)$buyer['user_id'],
                        'referrer_user_id' => null,
                        'progress_reset' => false,
                    ]
                    : $siteContext->attachReferrer(
                        $order['promo'],
                        (int)$buyer['user_id']
                    );
                $calculation = $this->quotePaidOrder($payload);
            }
            $assignmentOutcome = (string)($assignment['outcome'] ?? '');
            $participatesInProgram = in_array(
                $assignmentOutcome,
                ['attached', 'changed', 'unchanged', 'firm_promo'],
                true
            );
            $referrerUserId = in_array(
                $assignmentOutcome,
                ['attached', 'changed', 'unchanged'],
                true
            )
                ? (int)($assignment['referrer_user_id'] ?? 0)
                : 0;
            $connection->queryExecute(
                "UPDATE " . self::PURCHASE_TABLE . "
                 SET REFERRER_USER_ID=" . ($referrerUserId > 0 ? $referrerUserId : 'NULL') . ",
                     PROGRAM='" . ($participatesInProgram ? 'combined' : 'none') . "',
                     UPDATED_AT=NOW()
                 WHERE ID=" . $purchaseId
            );

            $storedAccruals = $this->storeAccruals(
                $purchaseId,
                $order,
                (array)($calculation['accruals'] ?? [])
            );
            $couponUsage = null;
            if (is_array($promoLookup) && (int)($promoLookup['coupon_id'] ?? 0) > 0) {
                $couponUsage = $this->incrementCouponUseCount(
                    (int)$promoLookup['coupon_id']
                );
                $connection->queryExecute(
                    "UPDATE " . self::PURCHASE_TABLE . "
                     SET COUPON_ID=" . (int)$couponUsage['coupon_id'] . ",
                         DISCOUNT_ID=" . (int)$couponUsage['discount_id'] . ",
                         COUPON_USE_COUNT_BEFORE="
                            . (int)$couponUsage['use_count_before'] . ",
                         COUPON_USE_COUNT_AFTER="
                            . (int)$couponUsage['use_count_after'] . ",
                         UPDATED_AT=NOW()
                     WHERE ID=" . $purchaseId
                );
            }
            $purchaseProgress = $participatesInProgram
                ? $siteContext->addPaidPurchase(
                    (int)$buyer['user_id'],
                    (float)$order['amount'],
                    $order['currency']
                )
                : $this->unchangedPurchaseProgress(
                    $siteContext,
                    (int)$buyer['user_id'],
                    $order['currency']
                );
            $this->refreshAffectedNetworkMonthlyBonuses(
                (int)$buyer['user_id'],
                (string)$order['period']
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
            'calculation' => $calculation,
            'stored_accrual_count' => count($storedAccruals ?? []),
        ];
    }

    public function reversePaidPurchase(array $payload): array
    {
        if (
            !Loader::includeModule('main')
            || !Loader::includeModule('iblock')
            || !Loader::includeModule('sale')
        ) {
            throw new \RuntimeException('required_module_unavailable');
        }

        $externalOrderId = trim((string)($payload['external_order_id'] ?? ''));
        if ($externalOrderId === '' || strlen($externalOrderId) > 100) {
            throw new \InvalidArgumentException('invalid_paid_order');
        }

        $connection = Application::getConnection();
        $externalOrderSql = $connection->getSqlHelper()->forSql($externalOrderId, 100);
        $connection->startTransaction();
        try {
            $purchase = $connection->query(
                "SELECT ID, USER_ID, AMOUNT, CURRENCY, PROGRAM, COUPON_ID, STATUS, PERIOD
                 FROM " . self::PURCHASE_TABLE . "
                 WHERE SOURCE='app' AND EXTERNAL_ORDER_ID='" . $externalOrderSql . "'
                 LIMIT 1 FOR UPDATE"
            )->fetch();
            if (!is_array($purchase)) {
                throw new \DomainException('purchase_not_found');
            }
            if ((string)($purchase['STATUS'] ?? '') === 'reversed') {
                $connection->commitTransaction();
                return $this->purchaseResult((int)$purchase['ID'], 'already_reversed');
            }

            $couponReversal = null;
            $couponId = (int)($purchase['COUPON_ID'] ?? 0);
            if ($couponId > 0) {
                $couponReversal = $this->decrementCouponUseCount($couponId);
            }
            $siteContext = new SiteDiscountContext();
            $purchaseProgress = (string)($purchase['PROGRAM'] ?? '') === 'combined'
                ? $siteContext->subtractPaidPurchase(
                    (int)$purchase['USER_ID'],
                    (float)$purchase['AMOUNT'],
                    (string)$purchase['CURRENCY']
                )
                : $this->unchangedPurchaseProgress(
                    $siteContext,
                    (int)$purchase['USER_ID'],
                    (string)$purchase['CURRENCY']
                );
            if ($connection->isTableExists(self::ACCRUAL_TABLE)) {
                $connection->queryExecute(
                    "UPDATE " . self::ACCRUAL_TABLE . "
                     SET STATUS='rejected', REASON='order_reversed',
                         FINALIZED_AT=NOW(), UPDATED_AT=NOW()
                     WHERE PURCHASE_ID=" . (int)$purchase['ID']
                );
            }
            $connection->queryExecute(
                "UPDATE " . self::PURCHASE_TABLE . "
                 SET STATUS='reversed', REFUNDED_AT=NOW(), UPDATED_AT=NOW()
                 WHERE ID=" . (int)$purchase['ID']
            );
            $this->refreshAffectedNetworkMonthlyBonuses(
                (int)$purchase['USER_ID'],
                (string)$purchase['PERIOD']
            );
            $connection->commitTransaction();
        } catch (\Throwable $exception) {
            $connection->rollbackTransaction();
            throw $exception;
        }

        return $this->purchaseResult((int)$purchase['ID'], 'reversed') + [
            'coupon_reversal' => $couponReversal,
            'purchase_progress' => $purchaseProgress,
        ];
    }

    public function recordPaidOrder(array $payload): array
    {
        return $this->recordPaidPurchase($payload);
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

        $eligibility = $this->eligibilityForPeriod(new SiteDiscountContext(), $userId, $period);
        $updated = $this->updateAccrualStatuses($userId, $period, $eligibility);

        return $eligibility + ['updated_accruals' => $updated];
    }

    public function partnerSummary(array $payload): array
    {
        $userId = isset($payload['user_id']) && is_numeric($payload['user_id'])
            ? max(0, (int)$payload['user_id'])
            : 0;
        if ($userId <= 0) {
            $userEmail = trim((string)($payload['user_email'] ?? ''));
            $userId = (int)$this->resolveUserByEmail($userEmail)['user_id'];
        }

        $profile = (new SiteDiscountContext())->getProgramProfile($userId);
        $connection = Application::getConnection();
        $summary = [
            'count' => 0,
            'pending_amount' => 0.0,
            'approved_amount' => 0.0,
            'rejected_amount' => 0.0,
        ];
        if ($connection->isTableExists(self::ACCRUAL_TABLE)) {
            $row = $connection->query(
                "SELECT
                    COUNT(*) AS CNT,
                    COALESCE(SUM(CASE WHEN STATUS='pending' THEN COMMISSION_AMOUNT ELSE 0 END), 0) AS PENDING_AMOUNT,
                    COALESCE(SUM(CASE WHEN STATUS='approved' THEN COMMISSION_AMOUNT ELSE 0 END), 0) AS APPROVED_AMOUNT,
                    COALESCE(SUM(CASE WHEN STATUS='rejected' THEN COMMISSION_AMOUNT ELSE 0 END), 0) AS REJECTED_AMOUNT
                 FROM " . self::ACCRUAL_TABLE . "
                 WHERE BENEFICIARY_USER_ID=" . $userId
            )->fetch();
            if (is_array($row)) {
                $summary = [
                    'count' => (int)$row['CNT'],
                    'pending_amount' => round((float)$row['PENDING_AMOUNT'], 2),
                    'approved_amount' => round((float)$row['APPROVED_AMOUNT'], 2),
                    'rejected_amount' => round((float)$row['REJECTED_AMOUNT'], 2),
                ];
            }
        }

        $requestedPeriod = trim((string)($payload['period'] ?? ''));
        $period = preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $requestedPeriod)
            ? $requestedPeriod
            : (new \DateTimeImmutable())->format('Y-m');

        return [
            'user_id' => $userId,
            'currency' => (string)Option::get(self::MODULE_ID, 'currency', 'RUB'),
            'own_promo' => $profile['own_promo'] ?? null,
            'referrer_promo' => $profile['referrer_promo'] ?? null,
            'personal_purchase_total' => round((float)($profile['order_sum']['amount'] ?? 0), 2),
            'personal_discount_percent' => max(
                0.0,
                (float)($profile['group_discount_percent'] ?? 0),
                (float)($profile['stored_discount_percent'] ?? 0)
            ),
            'app_partner_accruals' => $summary,
            'network_monthly_bonus' => $this->calculateNetworkMonthlyBonus($userId, $period, false),
            'site_partner_balance' => $this->sitePartnerBalance($userId),
        ];
    }

    public function removeLegacyAccrualStorage(): array
    {
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
            'agent_removed' => false,
            'accrual_table_removed' => !$connection->isTableExists('b_elixir_referral_app_accrual'),
            'properties_removed' => $removedProperties,
            'purchase_tracking_retained' => $connection->isTableExists(self::PURCHASE_TABLE),
            'partner_ledger_retained' => $connection->isTableExists(self::ACCRUAL_TABLE),
        ];
    }

    private function finalizePeriodForAll(string $period): void
    {
        if (!preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $period)) {
            throw new \InvalidArgumentException('invalid_period');
        }

        $connection = Application::getConnection();
        $userIds = [];
        if ($connection->isTableExists(self::ACCRUAL_TABLE)) {
            $rows = $connection->query(
                "SELECT DISTINCT BENEFICIARY_USER_ID AS USER_ID
                 FROM " . self::ACCRUAL_TABLE . "
                 WHERE PERIOD='" . $connection->getSqlHelper()->forSql($period, 7) . "'"
            );
            while ($row = $rows->fetch()) {
                $userIds[] = (int)$row['USER_ID'];
            }
        }
        $partnerRows = $connection->query(
            "SELECT VALUE_ID AS USER_ID
             FROM b_uts_user
             WHERE CAST(SUBSTRING_INDEX(COALESCE(UF_ORDER_SUMM, '0'), '|', 1) AS DECIMAL(18,2))>=200000"
        );
        while ($row = $partnerRows->fetch()) {
            $userIds[] = (int)$row['USER_ID'];
        }
        $userIds = array_values(array_unique(array_filter($userIds)));

        $siteContext = new SiteDiscountContext();
        foreach ($userIds as $userId) {
            $eligibility = $this->eligibilityForPeriod($siteContext, $userId, $period);
            $this->updateAccrualStatuses($userId, $period, $eligibility);
            $this->calculateNetworkMonthlyBonus($userId, $period, true);
        }
    }

    private function normalizePaidOrder(array $payload, bool $requirePromo = true): array
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
            || ($requirePromo && $promo === '')
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

    private function unchangedPurchaseProgress(
        SiteDiscountContext $siteContext,
        int $userId,
        string $currency
    ): array {
        $profile = $siteContext->getProgramProfile($userId);
        $total = round((float)($profile['order_sum']['amount'] ?? 0), 2);

        return [
            'previous_total' => $total,
            'new_total' => $total,
            'currency' => strtoupper(trim($currency)) ?: 'RUB',
            'discount_percent' => max(
                0.0,
                (float)($profile['group_discount_percent'] ?? 0),
                (float)($profile['stored_discount_percent'] ?? 0)
            ),
            'discount_group_id' => null,
            'participates_in_program' => false,
        ];
    }

    private function storeAccruals(int $purchaseId, array $order, array $accruals): array
    {
        if ($purchaseId <= 0 || $accruals === []) {
            return [];
        }

        $connection = Application::getConnection();
        if (!$connection->isTableExists(self::ACCRUAL_TABLE)) {
            throw new \RuntimeException('partner_accrual_table_unavailable');
        }
        $sqlHelper = $connection->getSqlHelper();
        $sourceSql = $sqlHelper->forSql('app', 20);
        $externalOrderSql = $sqlHelper->forSql((string)$order['external_order_id'], 100);
        $promoSql = $sqlHelper->forSql((string)$order['promo'], 100);
        $currencySql = $sqlHelper->forSql((string)$order['currency'], 3);
        $periodSql = $sqlHelper->forSql((string)$order['period'], 7);
        $stored = [];

        foreach ($accruals as $accrual) {
            if (!is_array($accrual)) {
                continue;
            }
            $beneficiary = is_array($accrual['beneficiary'] ?? null)
                ? $accrual['beneficiary']
                : [];
            $beneficiaryUserId = (int)($beneficiary['user_id'] ?? 0);
            $referralUserId = (int)($accrual['referral_user_id'] ?? 0);
            $level = (int)($accrual['level'] ?? 0);
            if ($beneficiaryUserId <= 0 || $referralUserId <= 0 || !in_array($level, [1, 2], true)) {
                continue;
            }

            $eligibility = is_array($accrual['eligibility'] ?? null)
                ? $accrual['eligibility']
                : [];
            $status = in_array((string)($eligibility['status'] ?? ''), ['pending', 'approved', 'rejected'], true)
                ? (string)$eligibility['status']
                : 'pending';
            $reason = trim((string)($eligibility['reason'] ?? ''));
            $reasonSql = $sqlHelper->forSql($reason, 100);
            $eligibilityJson = json_encode(
                $eligibility,
                JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
            );
            $eligibilitySql = $sqlHelper->forSql(is_string($eligibilityJson) ? $eligibilityJson : '{}');
            $connection->queryExecute(
                "INSERT IGNORE INTO " . self::ACCRUAL_TABLE . "
                    (PURCHASE_ID, SOURCE, EXTERNAL_ORDER_ID, BENEFICIARY_USER_ID, REFERRAL_USER_ID,
                     LEVEL, PROMO, BASE_AMOUNT, CURRENCY, BUYER_DISCOUNT_PERCENT,
                     REFERRER_DISCOUNT_PERCENT, COMMISSION_PERCENT, COMMISSION_AMOUNT,
                     PERIOD, STATUS, REASON, ELIGIBILITY_JSON, CREATED_AT, UPDATED_AT)
                 VALUES
                    (" . $purchaseId . ", '" . $sourceSql . "', '" . $externalOrderSql . "',
                     " . $beneficiaryUserId . ", " . $referralUserId . ", " . $level . ",
                     '" . $promoSql . "', " . number_format((float)$order['amount'], 2, '.', '') . ",
                     '" . $currencySql . "', "
                     . number_format((float)($accrual['referral_discount_percent'] ?? 0), 2, '.', '') . ", "
                     . number_format((float)($accrual['referrer_discount_percent'] ?? 0), 2, '.', '') . ", "
                     . number_format((float)($accrual['percent'] ?? 0), 2, '.', '') . ", "
                     . number_format((float)($accrual['amount'] ?? 0), 2, '.', '') . ",
                     '" . $periodSql . "', '" . $sqlHelper->forSql($status, 20) . "', "
                     . ($reason !== '' ? "'" . $reasonSql . "'" : 'NULL') . ",
                     '" . $eligibilitySql . "', NOW(), NOW())"
            );
        }

        $rows = $connection->query(
            "SELECT ID, BENEFICIARY_USER_ID, REFERRAL_USER_ID, LEVEL,
                    BUYER_DISCOUNT_PERCENT, REFERRER_DISCOUNT_PERCENT,
                    COMMISSION_PERCENT, COMMISSION_AMOUNT, CURRENCY, PERIOD,
                    STATUS, REASON, ELIGIBILITY_JSON
             FROM " . self::ACCRUAL_TABLE . "
             WHERE SOURCE='" . $sourceSql . "' AND EXTERNAL_ORDER_ID='" . $externalOrderSql . "'
             ORDER BY LEVEL ASC"
        );
        while ($row = $rows->fetch()) {
            $stored[] = $this->serializeAccrualRow($row);
        }

        return $stored;
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
        $eligible = $lifetimeTotal >= 100000.0;
        $reason = null;
        if ($isClosed && !$eligible) {
            $reason = 'lifetime_purchase_minimum_not_met';
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
            'monthly_minimum' => 0.0,
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
            "SELECT COALESCE(SUM(GREATEST(PRICE - COALESCE(PRICE_DELIVERY, 0), 0)), 0) AS TOTAL
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
               AND PAID_AT<'" . $toSql . "'
               AND PROGRAM='combined'
               AND STATUS='posted'"
        )->fetch();

        return round(
            (float)($websiteRow['TOTAL'] ?? 0) + (float)($appRow['TOTAL'] ?? 0),
            2
        );
    }

    private function calculateNetworkMonthlyBonus(
        int $userId,
        string $period,
        bool $persist
    ): array
    {
        $periodStart = new \DateTimeImmutable($period . '-01 00:00:00');
        $periodEnd = $periodStart->modify('+1 month');
        $isClosed = $periodEnd <= new \DateTimeImmutable('first day of this month 00:00:00');
        $siteContext = new SiteDiscountContext();
        $lifetimeTotal = $this->lifetimeProgramTotal($siteContext, $userId);
        $monthlyOwnPurchases = $this->monthlyOwnPurchases($userId, $periodStart, $periodEnd);
        $levelOneIds = $this->userIdsAtMinimumDiscount(
            $siteContext,
            $this->directReferralIds([$userId]),
            20.0
        );
        $levelTwoIds = $this->directReferralIds($levelOneIds);
        $levelOneTurnover = $this->networkPurchaseTotal($levelOneIds, $periodStart, $periodEnd);
        $levelTwoTurnover = $this->networkPurchaseTotal($levelTwoIds, $periodStart, $periodEnd);
        $networkTurnover = round($levelOneTurnover + $levelTwoTurnover, 2);

        $rate = 0.0;
        if ($networkTurnover > 0) {
            $rate = $networkTurnover > 1000000.0
                ? 5.0
                : ($networkTurnover > 500000.0 ? 4.0 : 3.0);
        }
        $eligible = $lifetimeTotal >= 200000.0
            && $monthlyOwnPurchases >= 10000.0
            && $networkTurnover > 0;
        $status = $isClosed ? ($eligible ? 'approved' : 'rejected') : 'pending';
        $reason = null;
        if ($isClosed && !$eligible) {
            if ($lifetimeTotal < 200000.0) {
                $reason = 'lifetime_purchase_minimum_not_met';
            } elseif ($monthlyOwnPurchases < 10000.0) {
                $reason = 'monthly_purchase_minimum_not_met';
            } else {
                $reason = 'network_turnover_missing';
            }
        }

        $result = [
            'user_id' => $userId,
            'period' => $period,
            'period_closed' => $isClosed,
            'status' => $status,
            'eligible' => $isClosed ? $eligible : null,
            'reason' => $reason,
            'lifetime_purchase_total' => $lifetimeTotal,
            'lifetime_minimum' => 200000.0,
            'monthly_own_purchase_total' => $monthlyOwnPurchases,
            'monthly_minimum' => 10000.0,
            'level_one_turnover' => $levelOneTurnover,
            'level_two_turnover' => $levelTwoTurnover,
            'network_turnover' => $networkTurnover,
            'rate_percent' => $rate,
            'amount' => round($networkTurnover * $rate / 100, 2),
            'currency' => (string)Option::get(self::MODULE_ID, 'currency', 'RUB'),
            'calculation_mode' => 'additional_network_rate_on_full_eligible_turnover',
        ];
        if ($persist) {
            $this->storeNetworkMonthlyBonus($result);
        }

        return $result;
    }

    private function directReferralIds(array $parentIds): array
    {
        $parentIds = array_values(array_unique(array_filter(
            array_map('intval', $parentIds),
            static fn(int $id): bool => $id > 0
        )));
        if ($parentIds === []) {
            return [];
        }

        $ids = [];
        $rows = Application::getConnection()->query(
            "SELECT u.ID
             FROM b_user u
             INNER JOIN b_uts_user uts ON uts.VALUE_ID=u.ID
             WHERE u.ACTIVE='Y'
               AND uts.UF_PARENT_ID IN (" . implode(',', $parentIds) . ")"
        );
        while ($row = $rows->fetch()) {
            $ids[] = (int)$row['ID'];
        }

        return array_values(array_unique(array_filter($ids)));
    }

    private function userIdsAtMinimumDiscount(
        SiteDiscountContext $siteContext,
        array $userIds,
        float $minimumPercent
    ): array {
        $eligible = [];
        foreach ($userIds as $userId) {
            $userId = (int)$userId;
            if (
                $userId > 0
                && $this->userDiscountPercent($siteContext, $userId, false) >= $minimumPercent
            ) {
                $eligible[] = $userId;
            }
        }

        return array_values(array_unique($eligible));
    }

    private function refreshAffectedNetworkMonthlyBonuses(int $buyerUserId, string $period): void
    {
        if ($buyerUserId <= 0 || !preg_match('/^\d{4}-(0[1-9]|1[0-2])$/', $period)) {
            return;
        }

        $beneficiaryIds = [$buyerUserId];
        $siteContext = new SiteDiscountContext();
        $buyerProfile = $siteContext->getProgramProfile($buyerUserId);
        $parentUserId = (int)($buyerProfile['referrer_user_id'] ?? 0);
        if ($parentUserId > 0) {
            $beneficiaryIds[] = $parentUserId;
            $parentProfile = $siteContext->getProgramProfile($parentUserId);
            $superReferrerUserId = (int)($parentProfile['referrer_user_id'] ?? 0);
            if ($superReferrerUserId > 0) {
                $beneficiaryIds[] = $superReferrerUserId;
            }
        }

        foreach (array_values(array_unique($beneficiaryIds)) as $beneficiaryId) {
            $this->calculateNetworkMonthlyBonus((int)$beneficiaryId, $period, true);
        }
    }

    private function networkPurchaseTotal(
        array $userIds,
        \DateTimeImmutable $periodStart,
        \DateTimeImmutable $periodEnd
    ): float {
        $userIds = array_values(array_unique(array_filter(
            array_map('intval', $userIds),
            static fn(int $id): bool => $id > 0
        )));
        if ($userIds === []) {
            return 0.0;
        }

        $connection = Application::getConnection();
        $sqlHelper = $connection->getSqlHelper();
        $fromSql = $sqlHelper->forSql($periodStart->format('Y-m-d H:i:s'), 19);
        $toSql = $sqlHelper->forSql($periodEnd->format('Y-m-d H:i:s'), 19);
        $idsSql = implode(',', $userIds);
        $websiteRow = $connection->query(
            "SELECT COALESCE(SUM(GREATEST(PRICE - COALESCE(PRICE_DELIVERY, 0), 0)), 0) AS TOTAL
             FROM b_sale_order
             WHERE USER_ID IN (" . $idsSql . ")
               AND PAYED='Y'
               AND CANCELED='N'
               AND DATE_PAYED>='" . $fromSql . "'
               AND DATE_PAYED<'" . $toSql . "'"
        )->fetch();
        $appRow = $connection->query(
            "SELECT COALESCE(SUM(AMOUNT), 0) AS TOTAL
             FROM " . self::PURCHASE_TABLE . "
             WHERE USER_ID IN (" . $idsSql . ")
               AND PAID_AT>='" . $fromSql . "'
               AND PAID_AT<'" . $toSql . "'
               AND PROGRAM='combined'
               AND STATUS='posted'"
        )->fetch();

        return round(
            (float)($websiteRow['TOTAL'] ?? 0) + (float)($appRow['TOTAL'] ?? 0),
            2
        );
    }

    private function storeNetworkMonthlyBonus(array $calculation): void
    {
        $connection = Application::getConnection();
        if (!$connection->isTableExists(self::NETWORK_MONTHLY_TABLE)) {
            return;
        }

        $sqlHelper = $connection->getSqlHelper();
        $periodSql = $sqlHelper->forSql((string)$calculation['period'], 7);
        $currencySql = $sqlHelper->forSql((string)$calculation['currency'], 3);
        $statusSql = $sqlHelper->forSql((string)$calculation['status'], 20);
        $reason = trim((string)($calculation['reason'] ?? ''));
        $reasonSql = $sqlHelper->forSql($reason, 100);
        $json = json_encode($calculation, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        $jsonSql = $sqlHelper->forSql(is_string($json) ? $json : '{}');
        $finalizedSql = (string)$calculation['status'] === 'pending' ? 'NULL' : 'NOW()';

        $connection->queryExecute(
            "INSERT INTO " . self::NETWORK_MONTHLY_TABLE . "
                (BENEFICIARY_USER_ID, PERIOD, LEVEL_ONE_TURNOVER, LEVEL_TWO_TURNOVER,
                 NETWORK_TURNOVER, OWN_MONTHLY_PURCHASES, LIFETIME_PURCHASES,
                 RATE_PERCENT, AMOUNT, CURRENCY, STATUS, REASON, CALCULATION_JSON,
                 FINALIZED_AT, CREATED_AT, UPDATED_AT)
             VALUES
                (" . (int)$calculation['user_id'] . ", '" . $periodSql . "', "
                . number_format((float)$calculation['level_one_turnover'], 2, '.', '') . ", "
                . number_format((float)$calculation['level_two_turnover'], 2, '.', '') . ", "
                . number_format((float)$calculation['network_turnover'], 2, '.', '') . ", "
                . number_format((float)$calculation['monthly_own_purchase_total'], 2, '.', '') . ", "
                . number_format((float)$calculation['lifetime_purchase_total'], 2, '.', '') . ", "
                . number_format((float)$calculation['rate_percent'], 2, '.', '') . ", "
                . number_format((float)$calculation['amount'], 2, '.', '') . ", '"
                . $currencySql . "', '" . $statusSql . "', "
                . ($reason !== '' ? "'" . $reasonSql . "'" : 'NULL') . ", '"
                . $jsonSql . "', " . $finalizedSql . ", NOW(), NOW())
             ON DUPLICATE KEY UPDATE
                LEVEL_ONE_TURNOVER=VALUES(LEVEL_ONE_TURNOVER),
                LEVEL_TWO_TURNOVER=VALUES(LEVEL_TWO_TURNOVER),
                NETWORK_TURNOVER=VALUES(NETWORK_TURNOVER),
                OWN_MONTHLY_PURCHASES=VALUES(OWN_MONTHLY_PURCHASES),
                LIFETIME_PURCHASES=VALUES(LIFETIME_PURCHASES),
                RATE_PERCENT=VALUES(RATE_PERCENT),
                AMOUNT=VALUES(AMOUNT),
                CURRENCY=VALUES(CURRENCY),
                STATUS=VALUES(STATUS),
                REASON=VALUES(REASON),
                CALCULATION_JSON=VALUES(CALCULATION_JSON),
                FINALIZED_AT=VALUES(FINALIZED_AT),
                UPDATED_AT=NOW()"
        );
    }

    private function purchaseResult(int $purchaseId, string $outcome): array
    {
        $connection = Application::getConnection();
        $purchase = $connection->query(
            "SELECT ID, SOURCE, EXTERNAL_ORDER_ID, USER_ID, REFERRER_USER_ID, PROMO,
                    AMOUNT, CURRENCY, PAID_AT, PERIOD, PROGRAM, COUPON_ID, DISCOUNT_ID,
                    COUPON_USE_COUNT_BEFORE, COUPON_USE_COUNT_AFTER, STATUS, REFUNDED_AT
             FROM " . self::PURCHASE_TABLE . "
             WHERE ID=" . $purchaseId . "
             LIMIT 1"
        )->fetch();
        if (!is_array($purchase)) {
            throw new \RuntimeException('purchase_not_found');
        }

        $accruals = [];
        if ($connection->isTableExists(self::ACCRUAL_TABLE)) {
            $rows = $connection->query(
                "SELECT ID, BENEFICIARY_USER_ID, REFERRAL_USER_ID, LEVEL,
                        BUYER_DISCOUNT_PERCENT, REFERRER_DISCOUNT_PERCENT,
                        COMMISSION_PERCENT, COMMISSION_AMOUNT, CURRENCY, PERIOD,
                        STATUS, REASON, ELIGIBILITY_JSON
                 FROM " . self::ACCRUAL_TABLE . "
                 WHERE PURCHASE_ID=" . $purchaseId . "
                 ORDER BY LEVEL ASC"
            );
            while ($row = $rows->fetch()) {
                $accruals[] = $this->serializeAccrualRow($row);
            }
        }

        return [
            'outcome' => $outcome,
            'storage' => 'bitrix',
            'accrual_storage' => 'bitrix_and_app_mirror',
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
                'program' => (string)($purchase['PROGRAM'] ?? 'combined'),
                'coupon_id' => (int)($purchase['COUPON_ID'] ?? 0) > 0
                    ? (int)$purchase['COUPON_ID']
                    : null,
                'discount_id' => (int)($purchase['DISCOUNT_ID'] ?? 0) > 0
                    ? (int)$purchase['DISCOUNT_ID']
                    : null,
                'coupon_use_count_before' => $purchase['COUPON_USE_COUNT_BEFORE'] !== null
                    ? (int)$purchase['COUPON_USE_COUNT_BEFORE']
                    : null,
                'coupon_use_count_after' => $purchase['COUPON_USE_COUNT_AFTER'] !== null
                    ? (int)$purchase['COUPON_USE_COUNT_AFTER']
                    : null,
                'status' => (string)($purchase['STATUS'] ?? 'posted'),
                'refunded_at' => trim((string)($purchase['REFUNDED_AT'] ?? '')) ?: null,
            ],
            'accruals' => $accruals,
        ];
    }

    private function updateAccrualStatuses(int $userId, string $period, array $eligibility): int
    {
        $connection = Application::getConnection();
        if (!$connection->isTableExists(self::ACCRUAL_TABLE)) {
            return 0;
        }

        $status = (string)($eligibility['status'] ?? 'pending');
        if (!in_array($status, ['pending', 'approved', 'rejected'], true)) {
            $status = 'pending';
        }
        $reason = trim((string)($eligibility['reason'] ?? ''));
        $json = json_encode($eligibility, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        $sqlHelper = $connection->getSqlHelper();
        $periodSql = $sqlHelper->forSql($period, 7);
        $statusSql = $sqlHelper->forSql($status, 20);
        $reasonSql = $sqlHelper->forSql($reason, 100);
        $jsonSql = $sqlHelper->forSql(is_string($json) ? $json : '{}');
        $connection->queryExecute(
            "UPDATE " . self::ACCRUAL_TABLE . "
             SET STATUS='" . $statusSql . "',
                 REASON=" . ($reason !== '' ? "'" . $reasonSql . "'" : 'NULL') . ",
                 ELIGIBILITY_JSON='" . $jsonSql . "',
                 FINALIZED_AT=" . ($status === 'pending' ? 'NULL' : 'NOW()') . ",
                 UPDATED_AT=NOW()
             WHERE BENEFICIARY_USER_ID=" . $userId . "
               AND PERIOD='" . $periodSql . "'
               AND STATUS='pending'"
        );

        return (int)$connection->getAffectedRowsCount();
    }

    private function serializeAccrualRow(array $row): array
    {
        $eligibility = json_decode((string)($row['ELIGIBILITY_JSON'] ?? ''), true);

        return [
            'id' => (int)$row['ID'],
            'beneficiary_user_id' => (int)$row['BENEFICIARY_USER_ID'],
            'referral_user_id' => (int)$row['REFERRAL_USER_ID'],
            'level' => (int)$row['LEVEL'],
            'buyer_discount_percent' => round(
                (float)($row['BUYER_DISCOUNT_PERCENT'] ?? 0),
                2
            ),
            'referrer_discount_percent' => round(
                (float)($row['REFERRER_DISCOUNT_PERCENT'] ?? 0),
                2
            ),
            'percent' => round((float)$row['COMMISSION_PERCENT'], 2),
            'amount' => round((float)$row['COMMISSION_AMOUNT'], 2),
            'currency' => (string)$row['CURRENCY'],
            'period' => (string)$row['PERIOD'],
            'status' => (string)$row['STATUS'],
            'reason' => trim((string)($row['REASON'] ?? '')) ?: null,
            'eligibility' => is_array($eligibility) ? $eligibility : [],
        ];
    }

    private function sitePartnerBalance(int $userId): float
    {
        if ($userId <= 0 || !Loader::includeModule('iblock')) {
            return 0.0;
        }

        $row = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            [
                'IBLOCK_ID' => 19,
                'ACTIVE' => 'Y',
                'PROPERTY_USER' => $userId,
            ],
            false,
            ['nTopCount' => 1],
            ['ID', 'PROPERTY_BALANCE']
        )->Fetch();

        return is_array($row)
            ? max(0.0, round((float)($row['PROPERTY_BALANCE_VALUE'] ?? 0), 2))
            : 0.0;
    }

    private function incrementCouponUseCount(int $couponId): array
    {
        if ($couponId <= 0) {
            throw new \RuntimeException('coupon_not_found');
        }

        $connection = Application::getConnection();
        $tableName = \Bitrix\Sale\Internals\DiscountCouponTable::getTableName();
        $row = $connection->query(
            "SELECT ID, DISCOUNT_ID, ACTIVE, ACTIVE_FROM, ACTIVE_TO, MAX_USE, USE_COUNT
             FROM " . $tableName . "
             WHERE ID=" . $couponId . "
             LIMIT 1 FOR UPDATE"
        )->fetch();
        if (!is_array($row)) {
            throw new \RuntimeException('coupon_not_found');
        }
        $now = new \DateTimeImmutable();
        if ((string)$row['ACTIVE'] !== 'Y') {
            throw new \DomainException('promo_not_active');
        }
        if (
            trim((string)($row['ACTIVE_FROM'] ?? '')) !== ''
            && new \DateTimeImmutable((string)$row['ACTIVE_FROM']) > $now
        ) {
            throw new \DomainException('promo_not_active');
        }
        if (
            trim((string)($row['ACTIVE_TO'] ?? '')) !== ''
            && new \DateTimeImmutable((string)$row['ACTIVE_TO']) < $now
        ) {
            throw new \DomainException('promo_not_active');
        }
        $before = max(0, (int)($row['USE_COUNT'] ?? 0));
        $maxUse = max(0, (int)($row['MAX_USE'] ?? 0));
        if ($maxUse > 0 && $before >= $maxUse) {
            throw new \DomainException('promo_usage_limit_reached');
        }
        $after = $before + 1;
        $connection->queryExecute(
            "UPDATE " . $tableName . "
             SET USE_COUNT=" . $after . ", DATE_APPLY=NOW(), TIMESTAMP_X=NOW()
             WHERE ID=" . $couponId
        );

        return [
            'coupon_id' => $couponId,
            'discount_id' => (int)$row['DISCOUNT_ID'],
            'use_count_before' => $before,
            'use_count_after' => $after,
            'source' => 'app_paid_order',
        ];
    }

    private function decrementCouponUseCount(int $couponId): array
    {
        $connection = Application::getConnection();
        $tableName = \Bitrix\Sale\Internals\DiscountCouponTable::getTableName();
        $row = $connection->query(
            "SELECT ID, DISCOUNT_ID, USE_COUNT
             FROM " . $tableName . "
             WHERE ID=" . $couponId . "
             LIMIT 1 FOR UPDATE"
        )->fetch();
        if (!is_array($row)) {
            throw new \RuntimeException('coupon_not_found');
        }
        $before = max(0, (int)($row['USE_COUNT'] ?? 0));
        $after = max(0, $before - 1);
        $connection->queryExecute(
            "UPDATE " . $tableName . "
             SET USE_COUNT=" . $after . ", TIMESTAMP_X=NOW()
             WHERE ID=" . $couponId
        );

        return [
            'coupon_id' => $couponId,
            'discount_id' => (int)$row['DISCOUNT_ID'],
            'use_count_before' => $before,
            'use_count_after' => $after,
            'source' => 'app_order_reversal',
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
