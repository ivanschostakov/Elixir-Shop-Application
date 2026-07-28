<?php

declare(strict_types=1);

$documentRoot = rtrim((string)getenv('ELIXIR_BITRIX_DOCUMENT_ROOT'), '/');
$statePath = trim((string)getenv('ELIXIR_SMOKE_STATE_PATH'));
if ($documentRoot === '' || $statePath === '') {
    fwrite(STDERR, "Smoke cleanup configuration is unavailable\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
define('SITE_ID', 's1');
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Application;
use Bitrix\Main\Loader;
use Bitrix\Sale\Internals\DiscountCouponTable;
use Sotbit\Reviews\Internals\ReviewsTable;

$state = is_file($statePath)
    ? json_decode((string)file_get_contents($statePath), true)
    : [];
if (!is_array($state)) {
    $state = [];
}
$email = trim((string)getenv('ELIXIR_SMOKE_EMAIL'));
if ((int)($state['user_id'] ?? 0) <= 0 && $email !== '') {
    $by = 'id';
    $order = 'asc';
    $user = CUser::GetList($by, $order, ['=EMAIL' => $email], ['FIELDS' => ['ID']])->Fetch();
    if ($user) {
        $state['user_id'] = (int)$user['ID'];
    }
}

if (Loader::includeModule('sotbit.reviews')) {
    if ((int)($state['review_id'] ?? 0) > 0) {
        ReviewsTable::delete((int)$state['review_id']);
    }
    if ((int)($state['user_id'] ?? 0) > 0) {
        $rows = ReviewsTable::getList([
            'select' => ['ID'],
            'filter' => ['=ID_USER' => (int)$state['user_id']],
        ])->fetchAll();
        foreach ($rows as $row) {
            ReviewsTable::delete((int)$row['ID']);
        }
    }
}
$promo = trim((string)($state['promo'] ?? getenv('ELIXIR_SMOKE_PROMO')));
if (Loader::includeModule('sale') && $promo !== '') {
    $coupon = DiscountCouponTable::getList([
        'select' => ['ID'],
        'filter' => ['=COUPON' => $promo],
        'limit' => 1,
    ])->fetch();
    if ($coupon) {
        DiscountCouponTable::delete((int)$coupon['ID']);
    }
}
if ((int)($state['user_id'] ?? 0) > 0) {
    CUser::Delete((int)$state['user_id']);
}
@unlink($statePath);
echo 'SMOKE_FIXTURES_REMOVED' . PHP_EOL;
