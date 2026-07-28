<?php

namespace Elixir\ReviewSync\Service;

use Bitrix\Main\Type\DateTime;
use Bitrix\Main\UserTable;
use Sotbit\Reviews\Internals\ReviewsTable;

final class ReviewSyncService
{
    private const MAX_PAGE_SIZE = 100;
    private const META_KEY = '_elixir_sync';

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
                'ANONYMITY', 'ADD_FIELDS',
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
            throw new \RuntimeException('Product mapping is missing');
        }

        $status = (string)($incoming['status'] ?? 'pending');
        if (!in_array($status, ['pending', 'published', 'rejected'], true)) {
            $status = 'pending';
        }
        $authorEmail = trim((string)($incoming['author_email'] ?? ''));
        $userId = $this->userIdByEmail($authorEmail);
        $metadata = $this->metadata($existing['ADD_FIELDS'] ?? null);
        $metadata[self::META_KEY] = [
            'app_review_id' => $appReviewId,
            'origin' => (string)($metadata[self::META_KEY]['origin'] ?? 'app'),
        ];

        $fields = [
            'ID_ELEMENT' => $productId,
            'XML_ID_ELEMENT' => $productSystemId,
            'ID_USER' => $userId,
            'RATING' => max(0, min(5, (int)($incoming['rating'] ?? 0))),
            'TEXT' => $this->text($incoming['text'] ?? null),
            'ANSWER' => $this->text($incoming['answer'] ?? null),
            'LIKES' => max(0, (int)($incoming['likes'] ?? 0)),
            'DISLIKES' => max(0, (int)($incoming['dislikes'] ?? 0)),
            'MODERATED' => $status === 'published' ? 'Y' : 'N',
            'ACTIVE' => $status === 'rejected' ? 'N' : 'Y',
            'ANONYMITY' => $userId > 0 ? 'N' : 'Y',
            'ADD_FIELDS' => serialize($metadata),
        ];

        if ($existing === null) {
            $fields += [
                'DATE_CREATION' => $this->bitrixDate($incoming['created_at'] ?? null),
                'DATE_CHANGE' => $this->bitrixDate($incoming['updated_at'] ?? null),
                'RECOMMENDATED' => 'Y',
                'SHOWS' => 0,
                'FILES' => serialize([]),
                'IP_USER' => $this->sourceIp(),
            ];
            $addResult = ReviewsTable::add($fields);
            if (!$addResult->isSuccess()) {
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

        $incomingTimestamp = $this->timestamp($incoming['updated_at'] ?? null);
        $remoteTimestamp = $this->timestamp($this->effectiveUpdatedAt($existing));
        if ($incomingTimestamp > 0 && $remoteTimestamp > $incomingTimestamp) {
            return [
                'remote_id' => (int)$existing['ID'],
                'outcome' => 'conflict',
                'updated_at' => $this->effectiveUpdatedAt($existing),
            ];
        }

        $fields['DATE_CHANGE'] = DateTime::createFromTimestamp(time());
        $updateResult = ReviewsTable::update((int)$existing['ID'], $fields);
        if (!$updateResult->isSuccess()) {
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
        foreach (['XML_ID_ELEMENT', 'TEXT', 'ANSWER', 'MODERATED', 'ACTIVE', 'ANONYMITY', 'ADD_FIELDS'] as $key) {
            if ((string)$existing[$key] !== (string)$fields[$key]) {
                return false;
            }
        }
        return true;
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
        $iterator = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            ['ID' => $productIds],
            false,
            false,
            ['ID', 'XML_ID']
        );
        while ($row = $iterator->Fetch()) {
            $result[(int)$row['ID']] = trim((string)$row['XML_ID']);
        }
        return $result;
    }

    private function productIdBySystemId(string $systemId): int
    {
        if ($systemId === '') {
            return 0;
        }
        $row = \CIBlockElement::GetList(
            ['ID' => 'ASC'],
            ['=XML_ID' => $systemId],
            false,
            ['nTopCount' => 1],
            ['ID']
        )->Fetch();
        return $row ? (int)$row['ID'] : 0;
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
