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

use Bitrix\Main\Application;
use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;

if (!Loader::includeModule('main') || !Loader::includeModule('sale') || !Loader::includeModule('iblock')) {
    throw new RuntimeException('Required Bitrix modules are unavailable');
}

$connection = Application::getConnection();

function fetchAllRows(string $sql): array
{
    global $connection;

    $rows = [];
    $result = $connection->query($sql);
    while ($row = $result->fetch()) {
        $rows[] = $row;
    }

    return $rows;
}

function summarizeDiscountTree($value): array
{
    $tree = is_string($value)
        ? @unserialize($value, ['allowed_classes' => false])
        : $value;
    if (!is_array($tree)) {
        return [];
    }

    $result = [];
    $walk = static function (array $node) use (&$walk, &$result): void {
        $classId = (string)($node['CLASS_ID'] ?? '');
        $data = is_array($node['DATA'] ?? null) ? $node['DATA'] : [];
        if ($classId !== '') {
            $result[] = [
                'class_id' => $classId,
                'value' => $data['value'] ?? $data['Value'] ?? null,
                'unit' => $data['Unit'] ?? $data['UNIT'] ?? null,
            ];
        }
        foreach ($node as $child) {
            if (is_array($child)) {
                $walk($child);
            }
        }
    };
    $walk($tree);

    return $result;
}

$discounts = fetchAllRows(
    "SELECT ID, NAME, ACTIVE, USE_COUPONS, SORT, PRIORITY, LAST_DISCOUNT, CONDITIONS, ACTIONS
     FROM b_sale_discount
     WHERE ACTIVE='Y'
     ORDER BY PRIORITY ASC, SORT ASC, ID ASC"
);
foreach ($discounts as &$discount) {
    $discount['CONDITIONS_SUMMARY'] = summarizeDiscountTree($discount['CONDITIONS']);
    $discount['ACTIONS_SUMMARY'] = summarizeDiscountTree($discount['ACTIONS']);
    unset($discount['CONDITIONS'], $discount['ACTIONS']);
}
unset($discount);

$referralUsers = fetchAllRows(
    "SELECT
        u.ID, u.EMAIL, u.ACTIVE,
        uts.UF_PROMO, uts.UF_PARENT_ID, uts.UF_PERCENT,
        uts.UF_ORDER_SUMM, uts.UF_SUM_PAID_ORDERS_MONTH
     FROM b_user u
     INNER JOIN b_uts_user uts ON uts.VALUE_ID=u.ID
     WHERE
        NULLIF(TRIM(COALESCE(uts.UF_PROMO, '')), '') IS NOT NULL
        OR COALESCE(uts.UF_PARENT_ID, 0) > 0
        OR COALESCE(uts.UF_ORDER_SUMM, 0) > 0
     ORDER BY u.ID ASC
     LIMIT 200"
);
foreach ($referralUsers as &$user) {
    $user['GROUP_IDS'] = array_map(
        'intval',
        array_column(
            fetchAllRows('SELECT GROUP_ID FROM b_user_group WHERE USER_ID=' . (int)$user['ID'] . ' ORDER BY GROUP_ID'),
            'GROUP_ID'
        )
    );
}
unset($user);

$iblocks = [];
foreach ([19, 20] as $iblockId) {
    $iblock = fetchAllRows(
        "SELECT ID, NAME, CODE, ACTIVE FROM b_iblock WHERE ID=" . $iblockId . " LIMIT 1"
    );
    $properties = fetchAllRows(
        "SELECT ID, NAME, CODE, PROPERTY_TYPE, MULTIPLE, USER_TYPE
         FROM b_iblock_property
         WHERE IBLOCK_ID=" . $iblockId . "
         ORDER BY SORT ASC, ID ASC"
    );
    $count = fetchAllRows(
        "SELECT COUNT(*) AS CNT FROM b_iblock_element WHERE IBLOCK_ID=" . $iblockId
    );
    $iblocks[(string)$iblockId] = [
        'iblock' => $iblock[0] ?? null,
        'properties' => $properties,
        'element_count' => (int)($count[0]['CNT'] ?? 0),
    ];
}

$operationNames = fetchAllRows(
    "SELECT NAME, COUNT(*) AS CNT
     FROM b_iblock_element
     WHERE IBLOCK_ID=20
     GROUP BY NAME
     HAVING COUNT(*) > 1
     ORDER BY CNT DESC, NAME ASC
     LIMIT 100"
);

$output = [
    'generated_at' => date(DATE_ATOM),
    'amocrmbridge_options' => [
        'promo_min_discount_group_id' => Option::get('elixir.amocrmbridge', 'promo_min_discount_group_id', ''),
        'promo_loyalty_group_ids' => Option::get('elixir.amocrmbridge', 'promo_loyalty_group_ids', ''),
        'promo_firm_promo_codes' => Option::get('elixir.amocrmbridge', 'promo_firm_promo_codes', ''),
    ],
    'promo_options' => [
        'discount_id' => Option::get('elixir.promo', 'discount_id', ''),
        'site_id' => Option::get('elixir.promo', 'site_id', ''),
        'person_type_id' => Option::get('elixir.promo', 'person_type_id', ''),
        'catalog_iblock_id' => Option::get('elixir.promo', 'catalog_iblock_id', ''),
        'offers_iblock_id' => Option::get('elixir.promo', 'offers_iblock_id', ''),
    ],
    'active_discounts' => $discounts,
    'referral_users' => $referralUsers,
    'iblocks' => $iblocks,
    'duplicate_operation_names' => $operationNames,
];

echo json_encode($output, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL;
