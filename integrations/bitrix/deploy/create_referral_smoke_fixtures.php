<?php

declare(strict_types=1);

$documentRoot = rtrim((string)getenv('ELIXIR_BITRIX_DOCUMENT_ROOT'), '/');
$statePath = trim((string)getenv('ELIXIR_SMOKE_STATE_PATH'));
$suffix = strtoupper(trim((string)getenv('ELIXIR_SMOKE_SUFFIX')));
if (
    $documentRoot === ''
    || $statePath === ''
    || !preg_match('/^[A-Z0-9]{8,24}$/', $suffix)
    || !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')
) {
    fwrite(STDERR, "Invalid referral smoke configuration\n");
    exit(2);
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['HTTP_HOST'] = 'elixirpeptide.com';
define('NO_KEEP_STATISTIC', true);
define('NOT_CHECK_PERMISSIONS', true);
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

use Bitrix\Main\Loader;
use Elixir\Promo\Service\PromoService;

if (!Loader::includeModule('elixir.promo')) {
    throw new RuntimeException('elixir.promo is unavailable');
}

$promoService = new PromoService();
$created = [];
$roles = [
    'super' => ['group' => 43, 'total' => '200000.00|RUB'],
    'referrer' => ['group' => 43, 'total' => '200000.00|RUB'],
    'buyer' => ['group' => null, 'total' => '0.00|RUB'],
];
try {
    foreach ($roles as $role => $settings) {
        $email = strtolower($role . '-' . $suffix . '@example.invalid');
        $promo = $suffix . '-' . strtoupper($role);
        $password = bin2hex(random_bytes(16)) . 'Aa1!';
        $userApi = new CUser();
        $userId = (int)$userApi->Add([
            'LOGIN' => $email,
            'EMAIL' => $email,
            'NAME' => 'Elixir',
            'LAST_NAME' => 'Smoke ' . ucfirst($role),
            'PASSWORD' => $password,
            'CONFIRM_PASSWORD' => $password,
            'ACTIVE' => 'Y',
            'LID' => 's1',
            'GROUP_ID' => array_values(array_filter([2, 3, 4, 5, $settings['group']])),
            'UF_PROMO' => $promo,
            'UF_ORDER_SUMM' => $settings['total'],
            'UF_PERCENT' => $settings['group'] ? 20 : 0,
        ]);
        if ($userId <= 0) {
            throw new RuntimeException('Could not create ' . $role . ': ' . $userApi->LAST_ERROR);
        }
        $promoService->ensureCouponForUser($userId, $promo);
        $created[$role] = [
            'user_id' => $userId,
            'email' => $email,
            'promo' => $promo,
        ];
    }

    $referrerApi = new CUser();
    if (!$referrerApi->Update((int)$created['referrer']['user_id'], [
        'UF_PARENT_ID' => (int)$created['super']['user_id'],
    ])) {
        throw new RuntimeException('Could not connect smoke referral tree');
    }

    $state = [
        'suffix' => $suffix,
        'users' => $created,
        'external_order_id' => 'SMOKE-' . $suffix . '-BUYER',
        'external_order_ids' => [
            'SMOKE-' . $suffix . '-SUPER',
            'SMOKE-' . $suffix . '-REFERRER',
            'SMOKE-' . $suffix . '-BUYER',
        ],
    ];
    $stateDirectory = dirname($statePath);
    if (!is_dir($stateDirectory) && !mkdir($stateDirectory, 0700, true) && !is_dir($stateDirectory)) {
        throw new RuntimeException('Could not create smoke state directory');
    }
    $written = file_put_contents(
        $statePath,
        json_encode($state, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
        LOCK_EX
    );
    if ($written === false) {
        throw new RuntimeException('Could not write smoke state');
    }
    chmod($statePath, 0600);
    echo json_encode($state, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL;
} catch (Throwable $exception) {
    foreach (array_reverse($created) as $row) {
        CUser::Delete((int)$row['user_id']);
    }
    throw $exception;
}
