<?php

declare(strict_types=1);

use Bitrix\Main\Loader;
use Elixir\ReviewSync\Service\ReviewSyncService;
use Sotbit\Reviews\Internals\ReviewsTable;

$documentRoot = rtrim((string)getenv('BITRIX_DOCUMENT_ROOT'), '/');
if ($documentRoot === '' || !is_file($documentRoot . '/bitrix/modules/main/include/prolog_before.php')) {
    throw new RuntimeException('BITRIX_DOCUMENT_ROOT is invalid');
}

$_SERVER['DOCUMENT_ROOT'] = $documentRoot;
$_SERVER['REMOTE_ADDR'] = '127.0.0.1';
require $documentRoot . '/bitrix/modules/main/include/prolog_before.php';

if (
    !Loader::includeModule('elixir.reviewsync')
    || !Loader::includeModule('sotbit.reviews')
    || !Loader::includeModule('iblock')
) {
    throw new RuntimeException('Required review modules are unavailable');
}

$sourceReview = ReviewsTable::getList([
    'select' => ['ID_ELEMENT'],
    'filter' => ['>ID_ELEMENT' => 0],
    'order' => ['ID' => 'ASC'],
    'limit' => 1,
])->fetch();
if (!$sourceReview) {
    throw new RuntimeException('No product-backed review is available for smoke testing');
}
$product = \CIBlockElement::GetByID((int)$sourceReview['ID_ELEMENT'])->Fetch();
$productSystemId = trim((string)($product['XML_ID'] ?? ''));
if ($productSystemId === '') {
    throw new RuntimeException('Smoke-test product has no XML_ID');
}

$appReviewId = random_int(900000000, 2000000000);
$remoteId = 0;
try {
    $baseReview = [
        'app_review_id' => $appReviewId,
        'product_system_id' => $productSystemId,
        'rating' => 5,
        'text' => 'ELIXIR_REVIEW_SYNC_SMOKE_' . $appReviewId,
        'answer' => null,
        'likes' => 0,
        'dislikes' => 0,
        'status' => 'published',
        'author_name' => 'Elixir smoke test',
        'author_email' => null,
        'attachments' => [],
        'created_at' => date(DATE_ATOM),
        'updated_at' => date(DATE_ATOM),
    ];
    $service = new ReviewSyncService();
    $created = $service->handle(['action' => 'push', 'reviews' => [$baseReview]]);
    $remoteId = (int)($created['results'][0]['remote_id'] ?? 0);
    $row = $remoteId > 0 ? ReviewsTable::getByPrimary($remoteId)->fetch() : null;
    if (!$row || (string)$row['MODERATED'] !== 'N' || (string)$row['ACTIVE'] !== 'Y') {
        throw new RuntimeException('New app review did not enter the pending moderation state');
    }

    $baseReview['remote_id'] = $remoteId;
    $baseReview['status'] = 'published';
    $baseReview['updated_at'] = date(DATE_ATOM, time() + 1);
    $service->handle(['action' => 'push', 'reviews' => [$baseReview]]);
    $row = ReviewsTable::getByPrimary($remoteId)->fetch();
    if (!$row || (string)$row['MODERATED'] !== 'N' || (string)$row['ACTIVE'] !== 'Y') {
        throw new RuntimeException('App push overwrote the Bitrix moderation decision');
    }

    echo json_encode([
        'ok' => true,
        'remote_id' => $remoteId,
        'app_review_id' => $appReviewId,
        'moderated' => $row['MODERATED'],
        'active' => $row['ACTIVE'],
        'cleanup' => 'pending',
    ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL;
} finally {
    if ($remoteId > 0) {
        ReviewsTable::delete($remoteId);
    }
}

echo json_encode([
    'ok' => true,
    'cleanup' => 'complete',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL;
