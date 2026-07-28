<?php

declare(strict_types=1);

$documentRoot = rtrim((string)getenv('ELIXIR_BITRIX_DOCUMENT_ROOT'), '/');
$email = trim((string)getenv('ELIXIR_SMOKE_EMAIL'));
$password = (string)getenv('ELIXIR_SMOKE_PASSWORD');
$promo = trim((string)getenv('ELIXIR_SMOKE_PROMO'));
$statePath = trim((string)getenv('ELIXIR_SMOKE_STATE_PATH'));
if (
    $documentRoot === ''
    || !filter_var($email, FILTER_VALIDATE_EMAIL)
    || strlen($password) < 12
    || $promo === ''
    || $statePath === ''
) {
    fwrite(STDERR, "Invalid smoke fixture configuration\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
define('SITE_ID', 's1');
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Loader;
use Elixir\Promo\Service\PromoService;
use Sotbit\Reviews\Internals\ReviewsTable;

if (!Loader::includeModule('elixir.promo') || !Loader::includeModule('sotbit.reviews') || !Loader::includeModule('iblock')) {
    throw new RuntimeException('Required module is unavailable');
}

$by = 'id';
$order = 'asc';
$existing = CUser::GetList(
    $by,
    $order,
    ['=EMAIL' => $email],
    ['FIELDS' => ['ID']]
)->Fetch();
if ($existing) {
    throw new RuntimeException('Smoke user already exists');
}

$userApi = new CUser();
$userId = (int)$userApi->Add([
    'LOGIN' => $email,
    'EMAIL' => $email,
    'NAME' => 'Elixir',
    'LAST_NAME' => 'Smoke',
    'PASSWORD' => $password,
    'CONFIRM_PASSWORD' => $password,
    'ACTIVE' => 'Y',
    'LID' => 's1',
    'GROUP_ID' => [2],
    'UF_PROMO' => $promo,
]);
if ($userId <= 0) {
    throw new RuntimeException('Unable to create smoke user');
}

(new PromoService())->ensureCouponForUser($userId, $promo);

$product = CIBlockElement::GetList(
    ['ID' => 'ASC'],
    ['IBLOCK_ID' => 2, 'ACTIVE' => 'Y'],
    false,
    ['nTopCount' => 1],
    ['ID', 'XML_ID']
)->Fetch();
if (!$product) {
    CUser::Delete($userId);
    throw new RuntimeException('No active product for smoke review');
}

$now = Bitrix\Main\Type\DateTime::createFromTimestamp(time());
$reviewResult = ReviewsTable::add([
    'ID_ELEMENT' => (int)$product['ID'],
    'XML_ID_ELEMENT' => (string)$product['XML_ID'],
    'ID_USER' => $userId,
    'RATING' => 5,
    'TEXT' => 'ELIXIR_SMOKE_REVIEW: temporary integration check',
    'ANSWER' => '',
    'LIKES' => 0,
    'DISLIKES' => 0,
    'DATE_CREATION' => $now,
    'DATE_CHANGE' => $now,
    'MODERATED' => 'Y',
    'ACTIVE' => 'Y',
    'ANONYMITY' => 'N',
    'RECOMMENDATED' => 'Y',
    'SHOWS' => 0,
    'ADD_FIELDS' => serialize([]),
    'FILES' => serialize([]),
    'IP_USER' => '127.0.0.1',
]);
if (!$reviewResult->isSuccess()) {
    CUser::Delete($userId);
    throw new RuntimeException('Unable to create smoke review: ' . implode('; ', $reviewResult->getErrorMessages()));
}

$state = [
    'user_id' => $userId,
    'review_id' => (int)$reviewResult->getId(),
    'promo' => $promo,
];
file_put_contents($statePath, json_encode($state, JSON_UNESCAPED_SLASHES), LOCK_EX);
chmod($statePath, 0600);
echo 'SMOKE_FIXTURES_CREATED user=1 review=1 coupon=1' . PHP_EOL;
