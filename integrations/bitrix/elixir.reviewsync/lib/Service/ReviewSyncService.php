<?php

namespace Elixir\ReviewSync\Service;

use Bitrix\Main\Config\Option;
use Bitrix\Main\Type\DateTime;
use Bitrix\Main\UserTable;
use Bitrix\Main\Web\HttpClient;
use Sotbit\Reviews\Internals\ReviewsTable;

final class ReviewSyncService
{
    private const MAX_PAGE_SIZE = 100;
    private const MAX_ATTACHMENTS = 6;
    private const MAX_ATTACHMENT_SIZE = 8388608;
    private const MAX_ATTACHMENTS_TOTAL_SIZE = 25165824;
    private const ALLOWED_ATTACHMENT_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
    private const META_KEY = '_elixir_sync';
    private const APP_SYSTEM_ID_PROPERTY = 'ELIXIR_APP_SYSTEM_ID';

    public function handle(array $payload): array
    {
        $action = (string)($payload['action'] ?? '');
        if ($action === 'pull') {
            return $this->pull(
                max(0, (int)($payload['offset'] ?? 0)),
                max(1, min(self::MAX_PAGE_SIZE, (int)($payload['limit'] ?? self::MAX_PAGE_SIZE)))
            );
        }
        if ($action === 'push') {
            return $this->push(is_array($payload['reviews'] ?? null) ? $payload['reviews'] : []);
        }
        throw new \InvalidArgumentException('Unknown action');
    }

    private function pull(int $offset, int $limit): array
    {
        $rows = ReviewsTable::getList([
            'select' => [
                'ID', 'ID_ELEMENT', 'XML_ID_ELEMENT', 'ID_USER', 'RATING', 'TEXT', 'ANSWER',
                'LIKES', 'DISLIKES', 'DATE_CREATION', 'DATE_CHANGE', 'MODERATED', 'ACTIVE',
                'ANONYMITY', 'ADD_FIELDS', 'FILES',
            ],
            'order' => ['ID' => 'ASC'],
            'offset' => $offset,
            'limit' => $limit,
        ])->fetchAll();

        $authors = $this->loadAuthors(array_values(array_unique(array_filter(array_map(
            static fn(array $row): int => (int)$row['ID_USER'],
            $rows
        )))));
        $productSystemIds = $this->loadProductSystemIds(array_values(array_unique(array_filter(array_map(
            static fn(array $row): int => (int)$row['ID_ELEMENT'],
            $rows
        )))));
        $reviews = [];
        foreach ($rows as $row) {
            $productSystemId = trim((string)($productSystemIds[(int)$row['ID_ELEMENT']] ?? ''));
            if ($productSystemId === '') {
                $productSystemId = trim((string)$row['XML_ID_ELEMENT']);
            }
            $author = $authors[(int)$row['ID_USER']] ?? ['name' => 'Покупатель с сайта', 'email' => null];
            $reviews[] = [
                'remote_id' => (int)$row['ID'],
                'app_review_id' => $this->appReviewId($row['ADD_FIELDS']),
                'product_system_id' => $productSystemId,
                'rating' => (int)$row['RATING'],
                'text' => $this->nullableText($row['TEXT']),
                'answer' => $this->nullableText($row['ANSWER']),
                'likes' => max(0, (int)$row['LIKES']),
                'dislikes' => max(0, (int)$row['DISLIKES']),
                'status' => $this->status($row),
                'author_name' => $author['name'],
                'author_email' => $author['email'],
                'attachments' => $this->exportAttachments($row['FILES'], $row['ADD_FIELDS']),
                'created_at' => $this->dateIso($row['DATE_CREATION']),
                'updated_at' => $this->dateIso($row['DATE_CHANGE'] ?: $row['DATE_CREATION']),
            ];
        }

        return [
            'reviews' => $reviews,
            'offset' => $offset,
            'limit' => $limit,
            'total' => (int)ReviewsTable::getCount([]),
        ];
    }

    private function push(array $incomingReviews): array
    {
        if (count($incomingReviews) > self::MAX_PAGE_SIZE) {
            throw new \InvalidArgumentException('Too many reviews');
        }
        $appReviewMap = $this->loadAppReviewMap();
        $results = [];
        foreach ($incomingReviews as $incoming) {
            if (!is_array($incoming)) {
                continue;
            }
            $appReviewId = max(0, (int)($incoming['app_review_id'] ?? 0));
            $remoteId = max(0, (int)($incoming['remote_id'] ?? 0));
            if ($remoteId <= 0 && $appReviewId > 0) {
                $remoteId = (int)($appReviewMap[$appReviewId] ?? 0);
            }
            $existing = $remoteId > 0 ? ReviewsTable::getByPrimary($remoteId)->fetch() : null;
            $result = $this->upsert($incoming, $existing ?: null, $appReviewId);
            $results[] = [
                'app_review_id' => $appReviewId,
                'remote_id' => $result['remote_id'],
                'outcome' => $result['outcome'],
                'updated_at' => $result['updated_at'],
            ];
        }
        return ['results' => $results];
    }

    private function upsert(array $incoming, ?array $existing, int $appReviewId): array
    {
        $productSystemId = trim((string)($incoming['product_system_id'] ?? ''));
        $productId = $this->productIdBySystemId($productSystemId);
        if ($productId <= 0) {
            return [
                'remote_id' => 0,
                'outcome' => 'skipped_missing_product',
                'updated_at' => null,
            ];
        }

        $authorEmail = trim((string)($incoming['author_email'] ?? ''));
        $userId = $this->userIdByEmail($authorEmail);
        if ($existing !== null) {
            $incomingTimestamp = $this->timestamp($incoming['updated_at'] ?? null);
            $remoteTimestamp = $this->timestamp($this->effectiveUpdatedAt($existing));
            if ($incomingTimestamp > 0 && $remoteTimestamp > $incomingTimestamp) {
                return [
                    'remote_id' => (int)$existing['ID'],
                    'outcome' => 'conflict',
                    'updated_at' => $this->effectiveUpdatedAt($existing),
                ];
            }
        }
        $metadata = $this->metadata($existing['ADD_FIELDS'] ?? null);
        $syncMetadata = is_array($metadata[self::META_KEY] ?? null) ? $metadata[self::META_KEY] : [];
        $syncMetadata['app_review_id'] = $appReviewId;
        $syncMetadata['origin'] = (string)($syncMetadata['origin'] ?? ($existing === null ? 'app' : 'website'));
        [$fileIds, $attachmentMap, $createdFileIds] = $this->importAttachments(
            is_array($incoming['attachments'] ?? null) ? $incoming['attachments'] : [],
            $existing,
            $syncMetadata
        );
        $syncMetadata['attachments'] = $attachmentMap;
        $metadata[self::META_KEY] = $syncMetadata;

        $fields = [
            'ID_ELEMENT' => $productId,
            'XML_ID_ELEMENT' => $productSystemId,
            'ID_USER' => $userId,
            'RATING' => max(0, min(5, (int)($incoming['rating'] ?? 0))),
            'TEXT' => $this->text($incoming['text'] ?? null),
            'ANSWER' => $this->text($incoming['answer'] ?? null),
            'LIKES' => max(0, (int)($incoming['likes'] ?? 0)),
            'DISLIKES' => max(0, (int)($incoming['dislikes'] ?? 0)),
            // Bitrix is the only moderation authority. App-created reviews always
            // enter its moderation queue and later app pushes cannot change the decision.
            'MODERATED' => $existing === null ? 'N' : (string)$existing['MODERATED'],
            'ACTIVE' => $existing === null ? 'Y' : (string)$existing['ACTIVE'],
            'ANONYMITY' => $userId > 0 ? 'N' : 'Y',
            'ADD_FIELDS' => serialize($metadata),
            'FILES' => $fileIds === [] ? 'N;' : serialize(array_map('strval', $fileIds)),
        ];

        if ($existing === null) {
            $fields += [
                'DATE_CREATION' => $this->bitrixDate($incoming['created_at'] ?? null),
                'DATE_CHANGE' => $this->bitrixDate($incoming['updated_at'] ?? null),
                'RECOMMENDATED' => 'Y',
                'SHOWS' => 0,
                'IP_USER' => $this->sourceIp(),
            ];
            $addResult = ReviewsTable::add($fields);
            if (!$addResult->isSuccess()) {
                $this->deleteFiles($createdFileIds);
                throw new \RuntimeException(implode('; ', $addResult->getErrorMessages()));
            }
            $remoteId = (int)$addResult->getId();
            $row = ReviewsTable::getByPrimary($remoteId)->fetch();
            return ['remote_id' => $remoteId, 'outcome' => 'created', 'updated_at' => $this->effectiveUpdatedAt($row ?: $fields)];
        }

        if ($this->sameReview($existing, $fields)) {
            return [
                'remote_id' => (int)$existing['ID'],
                'outcome' => 'unchanged',
                'updated_at' => $this->effectiveUpdatedAt($existing),
            ];
        }

        $fields['DATE_CHANGE'] = DateTime::createFromTimestamp(time());
        $updateResult = ReviewsTable::update((int)$existing['ID'], $fields);
        if (!$updateResult->isSuccess()) {
            $this->deleteFiles($createdFileIds);
            throw new \RuntimeException(implode('; ', $updateResult->getErrorMessages()));
        }
        $row = ReviewsTable::getByPrimary((int)$existing['ID'])->fetch();
        return [
            'remote_id' => (int)$existing['ID'],
            'outcome' => 'updated',
            'updated_at' => $this->effectiveUpdatedAt($row ?: $fields),
        ];
    }

    private function loadAppReviewMap(): array
    {
        $result = [];
        $rows = ReviewsTable::getList(['select' => ['ID', 'ADD_FIELDS']])->fetchAll();
        foreach ($rows as $row) {
            $appReviewId = $this->appReviewId($row['ADD_FIELDS']);
            if ($appReviewId > 0) {
                $result[$appReviewId] = (int)$row['ID'];
            }
        }
        return $result;
    }

    private function appReviewId($serialized): int
    {
        $metadata = $this->metadata($serialized);
        return max(0, (int)($metadata[self::META_KEY]['app_review_id'] ?? 0));
    }

    private function metadata($serialized): array
    {
        if (!is_string($serialized) || $serialized === '') {
            return [];
        }
        $result = @unserialize($serialized, ['allowed_classes' => false]);
        return is_array($result) ? $result : [];
    }

    private function sameReview(array $existing, array $fields): bool
    {
        foreach (['ID_ELEMENT', 'ID_USER', 'RATING', 'LIKES', 'DISLIKES'] as $key) {
            if ((int)$existing[$key] !== (int)$fields[$key]) {
                return false;
            }
        }
        foreach (['XML_ID_ELEMENT', 'TEXT', 'ANSWER', 'MODERATED', 'ACTIVE', 'ANONYMITY', 'ADD_FIELDS', 'FILES'] as $key) {
            if ((string)$existing[$key] !== (string)$fields[$key]) {
                return false;
            }
        }
        return true;
    }

    private function exportAttachments($serializedFiles, $serializedMetadata): array
    {
        $fileIds = $this->fileIds($serializedFiles);
        if ($fileIds === []) {
            return [];
        }
        $metadata = $this->metadata($serializedMetadata);
        $syncMetadata = is_array($metadata[self::META_KEY] ?? null) ? $metadata[self::META_KEY] : [];
        $attachmentMap = is_array($syncMetadata['attachments'] ?? null) ? $syncMetadata['attachments'] : [];
        $appAttachmentByFileId = [];
        foreach ($attachmentMap as $appAttachmentId => $fileId) {
            $fileId = (int)$fileId;
            if ((int)$appAttachmentId > 0 && $fileId > 0) {
                $appAttachmentByFileId[$fileId] = (int)$appAttachmentId;
            }
        }

        $baseUrl = rtrim(Option::get('elixir.reviewsync', 'site_public_base_url', 'https://elixirpeptide.com'), '/');
        $result = [];
        foreach ($fileIds as $fileId) {
            $file = \CFile::GetFileArray($fileId);
            if (!is_array($file) || empty($file['SRC'])) {
                continue;
            }
            $result[] = [
                'website_file_id' => $fileId,
                'app_attachment_id' => $appAttachmentByFileId[$fileId] ?? null,
                'url' => $baseUrl . '/' . ltrim((string)$file['SRC'], '/'),
                'filename' => trim((string)($file['ORIGINAL_NAME'] ?? '')) ?: basename((string)$file['SRC']),
                'mime_type' => $this->normalizeMimeType($file['CONTENT_TYPE'] ?? null),
                'size' => max(0, (int)($file['FILE_SIZE'] ?? 0)),
            ];
        }
        return $result;
    }

    private function importAttachments(array $incomingAttachments, ?array $existing, array $syncMetadata): array
    {
        if (count($incomingAttachments) > self::MAX_ATTACHMENTS) {
            throw new \InvalidArgumentException('Too many review attachments');
        }
        $existingFileIds = $this->fileIds($existing['FILES'] ?? null);
        $existingMap = is_array($syncMetadata['attachments'] ?? null) ? $syncMetadata['attachments'] : [];
        $resultMap = [];
        $managedFileIds = [];
        $createdFileIds = [];
        $totalSize = 0;

        try {
            foreach ($incomingAttachments as $attachment) {
                if (!is_array($attachment)) {
                    continue;
                }
                $appAttachmentId = max(0, (int)($attachment['app_attachment_id'] ?? 0));
                if ($appAttachmentId <= 0) {
                    throw new \InvalidArgumentException('Review attachment ID is missing');
                }
                $existingFileId = max(0, (int)($existingMap[$appAttachmentId] ?? 0));
                $websiteFileId = max(0, (int)($attachment['website_file_id'] ?? 0));
                if (
                    $existingFileId <= 0
                    && $websiteFileId > 0
                    && in_array($websiteFileId, $existingFileIds, true)
                ) {
                    // The attachment originated in Bitrix and was downloaded by
                    // the app. Reuse the same file instead of uploading a copy
                    // back into the review on every later app-side update.
                    $existingFileId = $websiteFileId;
                }
                if ($existingFileId > 0 && in_array($existingFileId, $existingFileIds, true)) {
                    $file = \CFile::GetFileArray($existingFileId);
                    if (is_array($file)) {
                        $totalSize += max(0, (int)($file['FILE_SIZE'] ?? 0));
                        if ($totalSize > self::MAX_ATTACHMENTS_TOTAL_SIZE) {
                            throw new \InvalidArgumentException('Review attachments are too large');
                        }
                        $resultMap[$appAttachmentId] = $existingFileId;
                        $managedFileIds[] = $existingFileId;
                        continue;
                    }
                }

                [$fileId, $fileSize] = $this->downloadAttachment($attachment);
                $createdFileIds[] = $fileId;
                $totalSize += $fileSize;
                if ($totalSize > self::MAX_ATTACHMENTS_TOTAL_SIZE) {
                    throw new \InvalidArgumentException('Review attachments are too large');
                }
                $resultMap[$appAttachmentId] = $fileId;
                $managedFileIds[] = $fileId;
            }
        } catch (\Throwable $exception) {
            foreach ($createdFileIds as $fileId) {
                \CFile::Delete($fileId);
            }
            throw $exception;
        }

        $previousManagedIds = array_values(array_filter(array_map('intval', $existingMap)));
        $unmanagedFileIds = array_values(array_filter(
            $existingFileIds,
            static fn(int $fileId): bool => !in_array($fileId, $previousManagedIds, true)
        ));
        return [
            array_values(array_unique(array_merge($unmanagedFileIds, $managedFileIds))),
            $resultMap,
            $createdFileIds,
        ];
    }

    private function deleteFiles(array $fileIds): void
    {
        foreach ($fileIds as $fileId) {
            \CFile::Delete((int)$fileId);
        }
    }

    private function downloadAttachment(array $attachment): array
    {
        $url = trim((string)($attachment['url'] ?? ''));
        $allowedBaseUrl = rtrim(Option::get('elixir.reviewsync', 'app_media_base_url', ''), '/') . '/';
        if (
            $allowedBaseUrl === '/'
            || !str_starts_with($allowedBaseUrl, 'https://')
            || !str_starts_with($url, $allowedBaseUrl)
        ) {
            throw new \InvalidArgumentException('Review attachment URL is not allowed');
        }

        $declaredMimeType = $this->normalizeMimeType($attachment['mime_type'] ?? null);
        if (!in_array($declaredMimeType, self::ALLOWED_ATTACHMENT_TYPES, true)) {
            throw new \InvalidArgumentException('Review attachment type is not allowed');
        }

        $privateDir = rtrim(Option::get(
            'elixir.reviewsync',
            'private_dir',
            dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-reviewsync'
        ), '/');
        $temporaryDir = $privateDir . '/attachments';
        if (!is_dir($temporaryDir) && !mkdir($temporaryDir, 0700, true) && !is_dir($temporaryDir)) {
            throw new \RuntimeException('Unable to create review attachment directory');
        }
        $temporaryPath = tempnam($temporaryDir, 'review-');
        if ($temporaryPath === false) {
            throw new \RuntimeException('Unable to create temporary review attachment');
        }

        try {
            $http = new HttpClient([
                'socketTimeout' => 15,
                'streamTimeout' => 30,
                'redirect' => false,
                'bodyLengthMax' => self::MAX_ATTACHMENT_SIZE + 1,
            ]);
            if (!$http->download($url, $temporaryPath) || $http->getStatus() !== 200) {
                throw new \RuntimeException('Unable to download review attachment');
            }
            $size = (int)filesize($temporaryPath);
            if ($size <= 0 || $size > self::MAX_ATTACHMENT_SIZE) {
                throw new \InvalidArgumentException('Review attachment size is not allowed');
            }
            $detectedMimeType = $this->detectMimeType($temporaryPath);
            if (!in_array($detectedMimeType, self::ALLOWED_ATTACHMENT_TYPES, true)) {
                throw new \InvalidArgumentException('Review attachment content is not allowed');
            }

            $file = \CFile::MakeFileArray($temporaryPath, $detectedMimeType);
            if (!is_array($file)) {
                throw new \RuntimeException('Unable to prepare review attachment');
            }
            $file['name'] = $this->safeAttachmentName(
                (string)($attachment['filename'] ?? ''),
                $detectedMimeType
            );
            $file['MODULE_ID'] = 'sotbit.reviews';
            $fileId = (int)\CFile::SaveFile($file, 'sotbit.reviews');
            if ($fileId <= 0) {
                throw new \RuntimeException('Unable to save review attachment');
            }
            return [$fileId, $size];
        } finally {
            @unlink($temporaryPath);
        }
    }

    private function fileIds($serialized): array
    {
        if (is_array($serialized)) {
            $values = $serialized;
        } elseif (is_string($serialized) && $serialized !== '') {
            $decoded = @unserialize($serialized, ['allowed_classes' => false]);
            $values = is_array($decoded) ? $decoded : [];
        } else {
            $values = [];
        }
        return array_values(array_unique(array_filter(array_map('intval', $values))));
    }

    private function normalizeMimeType($value): string
    {
        $mimeType = strtolower(trim(explode(';', (string)$value, 2)[0]));
        return $mimeType === 'image/jpg' ? 'image/jpeg' : $mimeType;
    }

    private function detectMimeType(string $path): string
    {
        $finfo = new \finfo(FILEINFO_MIME_TYPE);
        return $this->normalizeMimeType($finfo->file($path) ?: '');
    }

    private function safeAttachmentName(string $name, string $mimeType): string
    {
        $extensionByMimeType = [
            'image/jpeg' => 'jpg',
            'image/png' => 'png',
            'image/webp' => 'webp',
        ];
        $baseName = pathinfo(basename($name), PATHINFO_FILENAME);
        $baseName = preg_replace('/[^a-zA-Z0-9._-]+/', '-', $baseName) ?: 'review-image';
        return substr($baseName, 0, 100) . '.' . $extensionByMimeType[$mimeType];
    }

    private function loadAuthors(array $userIds): array
    {
        if (!$userIds) {
            return [];
        }
        $result = [];
        $iterator = UserTable::getList([
            'filter' => ['=ID' => $userIds],
            'select' => ['ID', 'NAME', 'LAST_NAME', 'EMAIL', 'LOGIN'],
        ]);
        while ($user = $iterator->fetch()) {
            $name = trim((string)$user['NAME'] . ' ' . (string)$user['LAST_NAME']);
            if ($name === '') {
                $name = trim((string)$user['LOGIN']) ?: 'Покупатель';
            }
            $result[(int)$user['ID']] = ['name' => $name, 'email' => $this->nullableText($user['EMAIL'])];
        }
        return $result;
    }

    private function userIdByEmail(string $email): int
    {
        if ($email === '') {
            return 0;
        }
        $row = UserTable::getList([
            'filter' => ['=EMAIL' => $email],
            'select' => ['ID'],
            'limit' => 1,
        ])->fetch();
        return $row ? (int)$row['ID'] : 0;
    }

    private function loadProductSystemIds(array $productIds): array
    {
        if (!$productIds) {
            return [];
        }
        $result = [];
        $elementIds = [];
        $iterator = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            [
                'IBLOCK_ID' => $this->catalogIblockId(),
                'ID' => $productIds,
            ],
            false,
            false,
            ['ID', 'XML_ID']
        );
        while ($row = $iterator->Fetch()) {
            $elementId = (int)$row['ID'];
            $elementIds[] = $elementId;
            $result[$elementId] = trim((string)$row['XML_ID']);
        }
        if ($elementIds === []) {
            return $result;
        }

        $properties = [];
        \CIBlockElement::GetPropertyValuesArray(
            $properties,
            $this->catalogIblockId(),
            ['ID' => $elementIds],
            ['CODE' => [self::APP_SYSTEM_ID_PROPERTY]]
        );
        foreach ($elementIds as $elementId) {
            $appSystemId = trim((string)(
                $properties[$elementId][self::APP_SYSTEM_ID_PROPERTY]['VALUE'] ?? ''
            ));
            if ($appSystemId !== '') {
                $result[$elementId] = $appSystemId;
            }
        }
        return $result;
    }

    private function productIdBySystemId(string $systemId): int
    {
        if ($systemId === '') {
            return 0;
        }

        $mappedProductId = $this->uniqueProductId([
            'IBLOCK_ID' => $this->catalogIblockId(),
            '=PROPERTY_' . self::APP_SYSTEM_ID_PROPERTY => $systemId,
        ]);
        if ($mappedProductId > 0) {
            return $mappedProductId;
        }
        return $this->uniqueProductId([
            'IBLOCK_ID' => $this->catalogIblockId(),
            '=XML_ID' => $systemId,
        ]);
    }

    private function uniqueProductId(array $filter): int
    {
        $iterator = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            $filter,
            false,
            ['nTopCount' => 2],
            ['ID']
        );
        $ids = [];
        while ($row = $iterator->Fetch()) {
            $ids[] = (int)$row['ID'];
        }
        return count($ids) === 1 ? $ids[0] : 0;
    }

    private function catalogIblockId(): int
    {
        return max(1, (int)Option::get('elixir.reviewsync', 'catalog_iblock_id', '21'));
    }

    private function status(array $row): string
    {
        if ((string)$row['ACTIVE'] === 'N') {
            return 'rejected';
        }
        return (string)$row['MODERATED'] === 'Y' ? 'published' : 'pending';
    }

    private function nullableText($value): ?string
    {
        $result = $this->text($value);
        return $result === '' ? null : $result;
    }

    private function text($value): string
    {
        return trim((string)$value);
    }

    private function bitrixDate($value): DateTime
    {
        $timestamp = $this->timestamp($value);
        return DateTime::createFromTimestamp($timestamp > 0 ? $timestamp : time());
    }

    private function timestamp($value): int
    {
        if ($value instanceof DateTime) {
            return $value->getTimestamp();
        }
        if ($value instanceof \DateTimeInterface) {
            return $value->getTimestamp();
        }
        $timestamp = strtotime((string)$value);
        return $timestamp === false ? 0 : $timestamp;
    }

    private function dateIso($value): ?string
    {
        $timestamp = $this->timestamp($value);
        return $timestamp > 0 ? date(DATE_ATOM, $timestamp) : null;
    }

    private function effectiveUpdatedAt(array $row): ?string
    {
        return $this->dateIso($row['DATE_CHANGE'] ?? null) ?: $this->dateIso($row['DATE_CREATION'] ?? null);
    }

    private function sourceIp(): string
    {
        $remoteAddress = trim((string)($_SERVER['REMOTE_ADDR'] ?? ''));
        return filter_var($remoteAddress, FILTER_VALIDATE_IP) ? $remoteAddress : '127.0.0.1';
    }
}
