<?php

declare(strict_types=1);

$documentRoot = rtrim((string)getenv('ELIXIR_BITRIX_DOCUMENT_ROOT'), '/');
$statePath = trim((string)getenv('ELIXIR_SMOKE_STATE_PATH'));
if (
    $documentRoot === ''
    || $statePath === ''
    || !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')
) {
    fwrite(STDERR, "Invalid referral smoke cleanup configuration\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Application;
use Bitrix\Main\Loader;
use Bitrix\Sale\Internals\DiscountCouponTable;

$state = is_file($statePath)
    ? json_decode((string)file_get_contents($statePath), true)
    : null;
if (!is_array($state)) {
    $suffix = strtoupper(trim((string)getenv('ELIXIR_SMOKE_SUFFIX')));
    if (!preg_match('/^[A-Z0-9]{8,24}$/', $suffix)) {
        fwrite(STDERR, "Referral smoke state was not found\n");
        exit(2);
    }
    $connection = Application::getConnection();
    $users = [];
    foreach (['super', 'referrer', 'buyer'] as $role) {
        $promo = $suffix . '-' . strtoupper($role);
        $promoSql = $connection->getSqlHelper()->forSql($promo, 100);
        $row = $connection->query(
            "SELECT VALUE_ID FROM b_uts_user WHERE UF_PROMO='" . $promoSql . "' LIMIT 1"
        )->fetch();
        if (is_array($row)) {
            $users[$role] = [
                'user_id' => (int)$row['VALUE_ID'],
                'promo' => $promo,
            ];
        }
    }
    $state = [
        'suffix' => $suffix,
        'users' => $users,
        'external_order_id' => 'SMOKE-' . $suffix . '-BUYER',
        'external_order_ids' => [
            'SMOKE-' . $suffix . '-SUPER',
            'SMOKE-' . $suffix . '-REFERRER',
            'SMOKE-' . $suffix . '-BUYER',
            'SMOKE-' . $suffix,
        ],
    ];
}

$connection = Application::getConnection();
$externalOrderIds = is_array($state['external_order_ids'] ?? null)
    ? $state['external_order_ids']
    : [$state['external_order_id'] ?? ''];
$stateSuffix = strtoupper(trim((string)($state['suffix'] ?? '')));
if (preg_match('/^[A-Z0-9]{8,24}$/', $stateSuffix)) {
    $externalOrderIds[] = 'SMOKE-' . $stateSuffix;
}
$externalOrderIds = array_values(array_unique(array_filter(array_map(
    static fn($value): string => trim((string)$value),
    $externalOrderIds
))));
$purchaseIds = [];
foreach ($externalOrderIds as $externalOrderId) {
    $externalOrderSql = $connection->getSqlHelper()->forSql($externalOrderId, 100);
    $purchase = $connection->query(
        "SELECT ID FROM b_elixir_referral_app_purchase
         WHERE SOURCE='app' AND EXTERNAL_ORDER_ID='" . $externalOrderSql . "'
         LIMIT 1"
    )->fetch();
    if (is_array($purchase)) {
        $purchaseIds[] = (int)$purchase['ID'];
    }
}

if (
    $purchaseIds !== []
    && $connection->isTableExists('b_elixir_referral_app_accrual')
    && Loader::includeModule('iblock')
) {
    $accruals = $connection->query(
        'SELECT PURCHASE_ID, BENEFICIARY_USER_ID, LEVEL
         FROM b_elixir_referral_app_accrual
         WHERE PURCHASE_ID IN (' . implode(',', $purchaseIds) . ')'
    );
    while ($accrual = $accruals->fetch()) {
        $sourceKey = sprintf(
            'app-purchase:%d:level:%d:user:%d',
            (int)$accrual['PURCHASE_ID'],
            (int)$accrual['LEVEL'],
            (int)$accrual['BENEFICIARY_USER_ID']
        );
        $operations = CIBlockElement::GetList(
            [],
            ['IBLOCK_ID' => 20, '=PROPERTY_SOURCE_KEY' => $sourceKey],
            false,
            false,
            ['ID']
        );
        while ($operation = $operations->Fetch()) {
            CIBlockElement::Delete((int)$operation['ID']);
        }
    }
}

foreach ($purchaseIds as $purchaseId) {
    $connection->queryExecute(
        'DELETE FROM b_elixir_referral_app_purchase WHERE ID=' . $purchaseId
    );
}

$users = is_array($state['users'] ?? null) ? $state['users'] : [];
foreach (array_reverse($users) as $row) {
    $userId = (int)($row['user_id'] ?? 0);
    $promo = trim((string)($row['promo'] ?? ''));
    if ($promo !== '' && Loader::includeModule('sale')) {
        $coupon = DiscountCouponTable::getList([
            'select' => ['ID'],
            'filter' => ['=COUPON' => $promo],
            'limit' => 1,
        ])->fetch();
        if ($coupon) {
            DiscountCouponTable::delete((int)$coupon['ID']);
        }
    }
    if ($userId > 0 && Loader::includeModule('iblock')) {
        $accounts = CIBlockElement::GetList(
            [],
            ['IBLOCK_ID' => 19, '=PROPERTY_USER' => $userId],
            false,
            false,
            ['ID']
        );
        while ($account = $accounts->Fetch()) {
            CIBlockElement::Delete((int)$account['ID']);
        }
    }
    if ($userId > 0) {
        CUser::Delete($userId);
    }
}

@unlink($statePath);
echo "REFERRAL_SMOKE_FIXTURES_REMOVED\n";
