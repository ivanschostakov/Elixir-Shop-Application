<?php

namespace Elixir\AmoCrmBridge\Service;

use Bitrix\Main\Application;
use Bitrix\Main\Config\Option;
use Bitrix\Main\Error;
use Bitrix\Main\Loader;
use Bitrix\Main\Result;
use Bitrix\Main\Type\DateTime;
use Bitrix\Sale\Order;
use Bitrix\Sale\OrderStatus;
use Elixir\AmoCrmBridge\Module;
use Elixir\AmoCrmBridge\Api\MoySkladApiClient;
use Elixir\AmoCrmBridge\Entity\MoySkladWebhookQueueTable;
use Elixir\AmoCrmBridge\Logger\BridgeLogger;
use Elixir\AmoCrmBridge\Repository\OrderLinkRepository;
use Elixir\AmoCrmBridge\Repository\SettingsRepository;
use Elixir\AmoCrmBridge\Repository\StatusMapRepository;

class MoySkladOrderWebhookService
{
    private SettingsRepository $settingsRepository;
    private OrderLinkRepository $orderLinkRepository;
    private StatusMapRepository $statusMapRepository;
    private MoySkladApiClient $moySkladApiClient;
    private BitrixOrderProductSyncService $bitrixOrderProductSyncService;
    private BridgeLogger $logger;
    /** @var resource|null */
    private $queueLockHandle = null;

    public function __construct(
        SettingsRepository $settingsRepository,
        OrderLinkRepository $orderLinkRepository,
        StatusMapRepository $statusMapRepository,
        MoySkladApiClient $moySkladApiClient,
        BitrixOrderProductSyncService $bitrixOrderProductSyncService,
        BridgeLogger $logger
    ) {
        $this->settingsRepository = $settingsRepository;
        $this->orderLinkRepository = $orderLinkRepository;
        $this->statusMapRepository = $statusMapRepository;
        $this->moySkladApiClient = $moySkladApiClient;
        $this->bitrixOrderProductSyncService = $bitrixOrderProductSyncService;
        $this->logger = $logger;
    }

    public function enqueueIncoming(string $siteId, array $query, array $post, string $rawBody, array $headers): Result
    {
        $result = new Result();
        $siteId = trim($siteId);
        if ($siteId === '') {
            $result->addError(new Error('Не указан site_id'));
            return $result;
        }

        if (!$this->isRequestAuthorized($siteId, $query, $headers)) {
            $result->addError(new Error('Неверный секрет вебхука'));
            return $result;
        }

        $payload = $this->decodePayload($rawBody);
        $events = is_array($payload['events'] ?? null) ? (array)$payload['events'] : [];
        if (empty($events)) {
            $events = [array_replace_recursive($payload, $post, $query)];
        }

        $requestId = $this->extractWebhookRequestId($query, $payload, $rawBody);
        $queued = 0;
        $duplicates = 0;
        foreach ($events as $index => $event) {
            if (!is_array($event)) {
                continue;
            }

            $eventPayload = [
                'query' => $query,
                'post' => $post,
                'headers' => $headers,
                'rawBody' => json_encode([
                    'auditContext' => $payload['auditContext'] ?? null,
                    'events' => [$event],
                ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
            ];

            $source = array_replace_recursive($event, $post, $query);
            $moySkladOrderId = $this->extractCustomerOrderId($this->extractOrderRef($source));
            $eventHash = hash('sha256', $requestId . '|' . $index . '|' . json_encode($event, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            $existing = MoySkladWebhookQueueTable::getList([
                'filter' => [
                    '=SITE_ID' => $siteId,
                    '=REQUEST_ID' => $requestId,
                    '=EVENT_HASH' => $eventHash,
                ],
                'select' => ['ID'],
                'limit' => 1,
            ])->fetch();
            if ($existing) {
                $duplicates++;
                continue;
            }

            $addResult = MoySkladWebhookQueueTable::add([
                'SITE_ID' => $siteId,
                'REQUEST_ID' => $requestId,
                'EVENT_HASH' => $eventHash,
                'MOYSKLAD_ORDER_ID' => $moySkladOrderId,
                'ACTION' => mb_substr((string)($event['action'] ?? ''), 0, 30),
                'UPDATED_FIELDS' => json_encode($this->extractUpdatedFields($event), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
                'STATUS' => 'new',
                'ATTEMPTS' => 0,
                'PAYLOAD' => json_encode($eventPayload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES),
                'NEXT_EXEC' => new DateTime(),
                'DATE_CREATED' => new DateTime(),
                'DATE_UPDATED' => new DateTime(),
            ]);

            if ($addResult->isSuccess()) {
                $queued++;
            } else {
                foreach ($addResult->getErrors() as $error) {
                    $result->addError($error);
                }
            }
        }

        if ($queued > 0) {
            $this->ensureQueueAgent();
        }

        $result->setData([
            'status' => 'queued',
            'queued' => $queued,
            'duplicates' => $duplicates,
            'request_id' => $requestId,
        ]);
        return $result;
    }

    public function processQueue(int $limit = 10): Result
    {
        $result = new Result();
        $limit = max(1, min(50, $limit));
        $now = new DateTime();

        if (!$this->acquireQueueLock()) {
            $result->setData([
                'processed' => 0,
                'restored_processing' => 0,
                'skipped_by_lock' => true,
            ]);
            return $result;
        }

        try {
            $restoredProcessing = $this->releaseStaleProcessingRows($now);
            $rows = MoySkladWebhookQueueTable::getList([
                'filter' => [
                    '@STATUS' => ['new', 'error'],
                    '<ATTEMPTS' => 5,
                    [
                        'LOGIC' => 'OR',
                        '<=NEXT_EXEC' => $now,
                        '=NEXT_EXEC' => null,
                    ],
                ],
                'order' => ['NEXT_EXEC' => 'ASC', 'ID' => 'ASC'],
                'limit' => $limit,
            ]);

            $processed = 0;
            while ($row = $rows->fetch()) {
                $this->processQueueRow($row);
                $processed++;
            }

            $result->setData([
                'processed' => $processed,
                'restored_processing' => $restoredProcessing,
                'skipped_by_lock' => false,
            ]);
        } finally {
            $this->releaseQueueLock();
        }

        return $result;
    }

    public function requeueFailed(int $limit = 200, string $errorContains = ''): Result
    {
        $result = new Result();
        $limit = max(1, min(1000, $limit));
        $now = new DateTime();
        $errorContains = trim($errorContains);

        $filter = ['=STATUS' => 'failed'];
        if ($errorContains !== '') {
            $filter['%LAST_ERROR'] = $errorContains;
        }

        $rows = MoySkladWebhookQueueTable::getList([
            'filter' => $filter,
            'select' => ['ID', 'LAST_ERROR'],
            'order' => ['ID' => 'ASC'],
            'limit' => $limit,
        ]);

        $requeued = 0;
        while ($row = $rows->fetch()) {
            $lastError = $this->normalizeQueueErrorMessage((string)($row['LAST_ERROR'] ?? ''));

            MoySkladWebhookQueueTable::update((int)$row['ID'], [
                'STATUS' => 'error',
                'ATTEMPTS' => 0,
                'LAST_ERROR' => $lastError !== '' ? mb_substr($lastError, 0, 5000) : 'Возвращено в очередь повторной обработки',
                'NEXT_EXEC' => $now,
                'DATE_UPDATED' => $now,
            ]);
            $requeued++;
        }

        if ($requeued > 0) {
            $this->ensureQueueAgent();
        }

        $result->setData([
            'requeued' => $requeued,
            'error_contains' => $errorContains,
        ]);
        return $result;
    }

    public function getQueueStats(int $errorLimit = 10): Result
    {
        $result = new Result();
        $stats = [];
        $errors = [];

        try {
            $connection = Application::getConnection();
            $sqlHelper = $connection->getSqlHelper();
            $table = $sqlHelper->forSql(MoySkladWebhookQueueTable::getTableName());

            $statusRows = $connection->query("
                SELECT STATUS, COUNT(*) CNT, MIN(ID) MIN_ID, MAX(ID) MAX_ID, MIN(DATE_CREATED) FIRST_CREATED, MAX(DATE_UPDATED) LAST_UPDATED
                FROM `{$table}`
                GROUP BY STATUS
                ORDER BY CNT DESC
            ");
            while ($row = $statusRows->fetch()) {
                $stats[] = [
                    'status' => (string)$row['STATUS'],
                    'count' => (int)$row['CNT'],
                    'min_id' => (int)$row['MIN_ID'],
                    'max_id' => (int)$row['MAX_ID'],
                    'first_created' => (string)$row['FIRST_CREATED'],
                    'last_updated' => (string)$row['LAST_UPDATED'],
                ];
            }

            $errorLimit = max(1, min(50, $errorLimit));
            $errorRows = $connection->query("
                SELECT LAST_ERROR, DATE_UPDATED
                FROM `{$table}`
                WHERE STATUS IN ('error', 'failed') AND LAST_ERROR IS NOT NULL AND LAST_ERROR <> ''
                ORDER BY DATE_UPDATED DESC, ID DESC
                LIMIT 1000
            ");
            $groupedErrors = [];
            while ($row = $errorRows->fetch()) {
                $message = $this->normalizeQueueErrorMessage((string)$row['LAST_ERROR']);
                if ($message === '') {
                    continue;
                }

                $groupedErrors[$message] = ($groupedErrors[$message] ?? 0) + 1;
            }

            arsort($groupedErrors);
            foreach (array_slice($groupedErrors, 0, $errorLimit, true) as $message => $count) {
                $errors[] = [
                    'count' => (int)$count,
                    'message' => (string)$message,
                ];
            }
        } catch (\Throwable $exception) {
            $result->addError(new Error($exception->getMessage()));
        }

        $result->setData([
            'statuses' => $stats,
            'errors' => $errors,
        ]);
        return $result;
    }

    private function processQueueRow(array $row): void
    {
        $rowId = (int)($row['ID'] ?? 0);
        $siteId = (string)($row['SITE_ID'] ?? '');
        $attempts = (int)($row['ATTEMPTS'] ?? 0);
        if ($rowId <= 0 || $siteId === '') {
            return;
        }

        $this->ensureBitrixUserObject();

        MoySkladWebhookQueueTable::update($rowId, [
            'STATUS' => 'processing',
            'ATTEMPTS' => $attempts + 1,
            'DATE_UPDATED' => new DateTime(),
        ]);

        $payload = json_decode((string)($row['PAYLOAD'] ?? ''), true);
        if (!is_array($payload)) {
            $this->markQueueRowError($rowId, $attempts + 1, 'Некорректный JSON очереди webhook');
            return;
        }

        try {
            InboundSyncGuard::suppressAllOrderSync();
            try {
                $result = $this->handleIncoming(
                    $siteId,
                    is_array($payload['query'] ?? null) ? (array)$payload['query'] : [],
                    is_array($payload['post'] ?? null) ? (array)$payload['post'] : [],
                    (string)($payload['rawBody'] ?? ''),
                    is_array($payload['headers'] ?? null) ? (array)$payload['headers'] : []
                );
            } finally {
                InboundSyncGuard::releaseAllOrderSync();
            }

            if (!$result->isSuccess()) {
                $this->markQueueRowError($rowId, $attempts + 1, implode('; ', $result->getErrorMessages()));
                return;
            }

            MoySkladWebhookQueueTable::update($rowId, [
                'STATUS' => 'success',
                'LAST_ERROR' => null,
                'DATE_UPDATED' => new DateTime(),
            ]);
        } catch (\Throwable $exception) {
            $this->markQueueRowError($rowId, $attempts + 1, $this->formatThrowableMessage($exception));
        }
    }

    private function ensureBitrixUserObject(): void
    {
        global $USER;

        if (is_object($USER)) {
            return;
        }

        if (class_exists('\CUser')) {
            $USER = new \CUser();
        }
    }

    private function formatThrowableMessage(\Throwable $exception): string
    {
        $message = trim($exception->getMessage());
        if ($message === '') {
            $message = get_class($exception);
        }

        $file = trim((string)$exception->getFile());
        $line = (int)$exception->getLine();
        if ($file !== '' && $line > 0) {
            $documentRoot = rtrim((string)($_SERVER['DOCUMENT_ROOT'] ?? ''), '/\\');
            if ($documentRoot !== '' && strpos($file, $documentRoot) === 0) {
                $file = ltrim(substr($file, strlen($documentRoot)), '/\\');
            }

            $message .= ' (' . $file . ':' . $line . ')';
        }

        return $message;
    }

    private function normalizeQueueErrorMessage(string $message): string
    {
        $message = trim($message);
        if ($message === '') {
            return '';
        }

        $prefix = 'Возвращено в очередь повторной обработки. Последняя ошибка:';
        if (mb_strpos($message, $prefix) === 0) {
            $message = trim(mb_substr($message, mb_strlen($prefix)));
        }

        return $message;
    }

    private function markQueueRowError(int $rowId, int $attempts, string $message): void
    {
        $nextExec = new DateTime();
        $nextExec->add('+' . min(30, max(1, $attempts * 2)) . ' minutes');

        MoySkladWebhookQueueTable::update($rowId, [
            'STATUS' => $attempts >= 5 ? 'failed' : 'error',
            'LAST_ERROR' => mb_substr($message, 0, 5000),
            'NEXT_EXEC' => $nextExec,
            'DATE_UPDATED' => new DateTime(),
        ]);
    }

    private function releaseStaleProcessingRows(DateTime $now): int
    {
        $threshold = new DateTime();
        $threshold->add('-20 minutes');
        $rows = MoySkladWebhookQueueTable::getList([
            'filter' => [
                '=STATUS' => 'processing',
                '<=DATE_UPDATED' => $threshold,
            ],
            'select' => ['ID', 'ATTEMPTS'],
            'order' => ['ID' => 'ASC'],
            'limit' => 50,
        ]);

        $restored = 0;
        while ($row = $rows->fetch()) {
            $attempts = (int)($row['ATTEMPTS'] ?? 0);
            MoySkladWebhookQueueTable::update((int)$row['ID'], [
                'STATUS' => $attempts >= 5 ? 'failed' : 'error',
                'LAST_ERROR' => 'Обработка была зависшей и возвращена в очередь',
                'NEXT_EXEC' => $now,
                'DATE_UPDATED' => $now,
            ]);
            $restored++;
        }

        return $restored;
    }

    private function acquireQueueLock(): bool
    {
        $documentRoot = rtrim((string)($_SERVER['DOCUMENT_ROOT'] ?? ''), '/\\');
        $lockDir = $documentRoot !== '' ? $documentRoot . '/bitrix/tmp' : sys_get_temp_dir();
        if (!is_dir($lockDir)) {
            @mkdir($lockDir, 0775, true);
        }

        $lockFile = rtrim($lockDir, '/\\') . '/elixir_amocrmbridge_moysklad_webhook_queue.lock';
        $handle = @fopen($lockFile, 'c');
        if (!is_resource($handle)) {
            return true;
        }

        if (!@flock($handle, LOCK_EX | LOCK_NB)) {
            @fclose($handle);
            return false;
        }

        $this->queueLockHandle = $handle;
        return true;
    }

    private function releaseQueueLock(): void
    {
        if (!is_resource($this->queueLockHandle)) {
            $this->queueLockHandle = null;
            return;
        }

        @flock($this->queueLockHandle, LOCK_UN);
        @fclose($this->queueLockHandle);
        $this->queueLockHandle = null;
    }

    private function applyOrderPositions(string $siteId, Order $order, string $moySkladOrderId): Result
    {
        $result = new Result();
        $positionsResponse = $this->moySkladApiClient->request(
            $siteId,
            'GET',
            'entity/customerorder/' . rawurlencode($moySkladOrderId) . '/positions',
            null,
            [
                'expand' => 'assortment',
                'limit' => 1000,
            ]
        );

        if (!$positionsResponse->isSuccess()) {
            foreach ($positionsResponse->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        $rows = (array)($positionsResponse->getData()['response']['rows'] ?? []);
        $products = [];
        foreach ($rows as $row) {
            if (!is_array($row)) {
                continue;
            }

            $assortment = is_array($row['assortment'] ?? null) ? (array)$row['assortment'] : [];
            $meta = is_array($assortment['meta'] ?? null) ? (array)$assortment['meta'] : [];
            $type = trim((string)($meta['type'] ?? ''));
            if ($type === 'service') {
                continue;
            }

            $msId = $this->extractMoySkladEntityIdFromHref((string)($meta['href'] ?? ''));
            if ($msId === '') {
                $msId = trim((string)($assortment['id'] ?? ''));
            }

            $productId = $this->resolveBitrixProductIdByMoySkladAssortment($siteId, $msId, $type);
            if ($productId <= 0) {
                $result->addError(new Error('Не найден товар Bitrix для позиции МойСклад: ' . (string)($assortment['name'] ?? $row['name'] ?? $msId)));
                return $result;
            }

            $quantity = (float)($row['quantity'] ?? 0);
            if ($quantity <= 0) {
                continue;
            }

            $products[] = [
                'product_id' => $productId,
                'name' => (string)($assortment['name'] ?? $row['name'] ?? ''),
                'quantity' => $quantity,
                'price' => isset($row['price']) ? ((float)$row['price'] / 100) : 0,
                'external_id' => $msId,
                'sku' => (string)($assortment['article'] ?? $assortment['code'] ?? ''),
            ];
        }

        if (empty($products)) {
            $result->addError(new Error('В заказе МойСклад нет товарных позиций для синхронизации'));
            return $result;
        }

        $syncResult = $this->bitrixOrderProductSyncService->applyResolvedProducts($order, $products, 'МойСклад');
        if (!$syncResult->isSuccess()) {
            foreach ($syncResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        $result->setData([
            'action' => 'updated',
            'order_id' => (int)$order->getId(),
            'positions_count' => count($products),
        ]);
        return $result;
    }

    private function applyOrderFinanceSnapshot(string $siteId, Order $order, string $moySkladOrderId): Result
    {
        $result = new Result();
        $snapshotResult = $this->fetchCustomerOrderFinanceSnapshot($siteId, $moySkladOrderId);
        if (!$snapshotResult->isSuccess()) {
            foreach ($snapshotResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        $snapshot = (array)$snapshotResult->getData();
        $orderPrice = (float)$order->getPrice();
        $changed = false;
        $warnings = [];

        $changed = $this->setExistingOrderProperties($order, $this->buildMoySkladFinancePropertyValues($snapshot)) || $changed;

        if ($this->isFullAmount((float)($snapshot['paid_sum'] ?? 0), $orderPrice, (float)($snapshot['sum'] ?? 0))) {
            $paymentResult = $this->markOrderPaymentsPaidInMemory($order);
            if (!$paymentResult->isSuccess()) {
                foreach ($paymentResult->getErrors() as $error) {
                    $result->addError($error);
                }
                return $result;
            }

            $changed = ((bool)($paymentResult->getData()['changed'] ?? false)) || $changed;
        }

        if ($this->isFullAmount((float)($snapshot['shipped_sum'] ?? 0), $orderPrice, (float)($snapshot['sum'] ?? 0))) {
            $shipmentResult = $this->markOrderShipmentsDeductedInMemory($order);
            if (!$shipmentResult->isSuccess()) {
                $warnings[] = implode('; ', $shipmentResult->getErrorMessages());
            } else {
                $changed = ((bool)($shipmentResult->getData()['changed'] ?? false)) || $changed;
            }
        }

        if ($changed) {
            InboundSyncGuard::suppressAllOrderSync();
            InboundSyncGuard::suppressOrderStatusSync((int)$order->getId());
            try {
                $saveResult = $order->save();
            } finally {
                InboundSyncGuard::releaseOrderStatusSync((int)$order->getId());
                InboundSyncGuard::releaseAllOrderSync();
            }

            if (!$saveResult->isSuccess()) {
                foreach ($saveResult->getErrors() as $error) {
                    $result->addError($error);
                }
                return $result;
            }
        }

        $this->orderLinkRepository->markMoySkladReverseSync($siteId, (int)$order->getId(), $snapshot, 'success');

        if (!empty($warnings)) {
            $this->logger->warning($siteId, 'moysklad_webhook', 'finance_snapshot_warnings', [
                'order_id' => (int)$order->getId(),
                'moysklad_order_id' => $moySkladOrderId,
                'message' => implode('; ', $warnings),
                'response' => $snapshot,
            ]);
        }

        $result->setData([
            'action' => $changed ? 'updated' : 'skipped',
            'reason' => $changed ? '' : 'finance_already_synced',
            'order_id' => (int)$order->getId(),
            'paid_sum' => (float)($snapshot['paid_sum'] ?? 0),
            'shipped_sum' => (float)($snapshot['shipped_sum'] ?? 0),
            'payment_status' => (string)($snapshot['payment_status'] ?? ''),
            'shipment_status' => (string)($snapshot['shipment_status'] ?? ''),
            'payments_count' => (int)($snapshot['payments_count'] ?? 0),
            'demands_count' => (int)($snapshot['demands_count'] ?? 0),
        ]);
        return $result;
    }

    private function fetchCustomerOrderFinanceSnapshot(string $siteId, string $moySkladOrderId): Result
    {
        $result = new Result();
        $response = $this->moySkladApiClient->getCustomerOrderFull($siteId, $moySkladOrderId, [
            'expand' => 'state,demands,payments,prepayments',
        ]);

        if (!$response->isSuccess()) {
            foreach ($response->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        $customerOrder = (array)($response->getData()['response'] ?? []);
        if (empty($customerOrder['id'])) {
            $result->addError(new Error('МойСклад вернул пустой заказ покупателя: ' . $moySkladOrderId));
            return $result;
        }

        $sum = $this->moySkladMoneyToFloat($customerOrder['sum'] ?? 0);
        $paidSum = $this->moySkladMoneyToFloat($customerOrder['payedSum'] ?? 0);
        $shippedSum = $this->moySkladMoneyToFloat($customerOrder['shippedSum'] ?? 0);
        $payments = array_merge(
            $this->extractMetaCollection($customerOrder, 'payments'),
            $this->extractMetaCollection($customerOrder, 'prepayments')
        );
        $demands = $this->extractMetaCollection($customerOrder, 'demands');

        $snapshot = [
            'moysklad_order_id' => (string)$customerOrder['id'],
            'moysklad_order_name' => (string)($customerOrder['name'] ?? ''),
            'moysklad_order_url' => (string)($customerOrder['meta']['uuidHref'] ?? $customerOrder['meta']['href'] ?? ''),
            'sum' => $sum,
            'paid_sum' => $paidSum,
            'shipped_sum' => $shippedSum,
            'payments_count' => count($payments),
            'demands_count' => count($demands),
            'payment_status' => $this->buildAmountStatus($paidSum, $sum),
            'shipment_status' => $this->buildAmountStatus($shippedSum, $sum),
            'state_href' => (string)($customerOrder['state']['meta']['href'] ?? ''),
            'payment_hrefs' => array_values(array_map(static function (array $row): string {
                return (string)($row['meta']['href'] ?? $row['href'] ?? '');
            }, $payments)),
            'demand_hrefs' => array_values(array_map(static function (array $row): string {
                return (string)($row['meta']['href'] ?? $row['href'] ?? '');
            }, $demands)),
        ];

        $result->setData($snapshot);
        return $result;
    }

    private function setExistingOrderProperties(Order $order, array $values): bool
    {
        if (empty($values)) {
            return false;
        }

        $propertyCollection = $order->getPropertyCollection();
        if (!$propertyCollection) {
            return false;
        }

        $changed = false;
        foreach ($propertyCollection as $propertyValue) {
            if (!is_object($propertyValue) || !method_exists($propertyValue, 'getField') || !method_exists($propertyValue, 'setValue')) {
                continue;
            }

            $code = trim((string)$propertyValue->getField('CODE'));
            if ($code === '' || !array_key_exists($code, $values)) {
                continue;
            }

            $newValue = (string)$values[$code];
            if ((string)$propertyValue->getValue() === $newValue) {
                continue;
            }

            $propertyValue->setValue($newValue);
            $changed = true;
        }

        return $changed;
    }

    private function buildMoySkladFinancePropertyValues(array $snapshot): array
    {
        $paidSum = $this->formatMoney((float)($snapshot['paid_sum'] ?? 0));
        $shippedSum = $this->formatMoney((float)($snapshot['shipped_sum'] ?? 0));
        $paymentStatus = (string)($snapshot['payment_status'] ?? '');
        $shipmentStatus = (string)($snapshot['shipment_status'] ?? '');

        return [
            'MOYSKLAD_PAID_SUM' => $paidSum,
            'MS_PAID_SUM' => $paidSum,
            'MOYSKLAD_SHIPPED_SUM' => $shippedSum,
            'MS_SHIPPED_SUM' => $shippedSum,
            'MOYSKLAD_PAYMENT_STATUS' => $paymentStatus,
            'MS_PAYMENT_STATUS' => $paymentStatus,
            'MOYSKLAD_SHIPMENT_STATUS' => $shipmentStatus,
            'MS_SHIPMENT_STATUS' => $shipmentStatus,
            'MOYSKLAD_PAYMENTS_COUNT' => (string)(int)($snapshot['payments_count'] ?? 0),
            'MS_PAYMENTS_COUNT' => (string)(int)($snapshot['payments_count'] ?? 0),
            'MOYSKLAD_DEMANDS_COUNT' => (string)(int)($snapshot['demands_count'] ?? 0),
            'MS_DEMANDS_COUNT' => (string)(int)($snapshot['demands_count'] ?? 0),
            'MOYSKLAD_ORDER_NAME' => (string)($snapshot['moysklad_order_name'] ?? ''),
            'MS_ORDER_NAME' => (string)($snapshot['moysklad_order_name'] ?? ''),
            'MOYSKLAD_ORDER_URL' => (string)($snapshot['moysklad_order_url'] ?? ''),
            'MS_ORDER_URL' => (string)($snapshot['moysklad_order_url'] ?? ''),
        ];
    }

    private function moySkladMoneyToFloat($value): float
    {
        if (!is_numeric($value)) {
            return 0.0;
        }

        return round(((float)$value) / 100, 2);
    }

    private function formatMoney(float $value): string
    {
        return number_format($value, 2, '.', '');
    }

    private function buildAmountStatus(float $actual, float $total): string
    {
        if ($total <= 0) {
            return $actual > 0 ? 'full' : 'empty';
        }

        if ($actual <= 0) {
            return 'empty';
        }

        if ($actual + 0.01 >= $total) {
            return 'full';
        }

        return 'partial';
    }

    private function isFullAmount(float $actual, float $bitrixOrderPrice, float $moySkladOrderSum): bool
    {
        $target = $moySkladOrderSum > 0 ? $moySkladOrderSum : $bitrixOrderPrice;
        return $target > 0 && $actual + 0.01 >= $target;
    }

    private function markOrderPaymentsPaidInMemory(Order $order): Result
    {
        $result = new Result();
        $changed = false;

        foreach ($order->getPaymentCollection() as $payment) {
            if ($payment->isInner() || (string)$payment->getField('PAID') === 'Y') {
                continue;
            }

            $setResult = $payment->setPaid('Y');
            if (!$setResult->isSuccess()) {
                foreach ($setResult->getErrors() as $error) {
                    $result->addError($error);
                }
                return $result;
            }

            $changed = true;
        }

        $result->setData(['changed' => $changed]);
        return $result;
    }

    private function markOrderShipmentsDeductedInMemory(Order $order): Result
    {
        $result = new Result();
        $changed = false;

        foreach ($order->getShipmentCollection() as $shipment) {
            if (!is_object($shipment) || (method_exists($shipment, 'isSystem') && $shipment->isSystem())) {
                continue;
            }

            if (method_exists($shipment, 'allowDelivery') && (string)$shipment->getField('ALLOW_DELIVERY') !== 'Y') {
                $allowResult = $shipment->allowDelivery();
                if ($allowResult instanceof Result && !$allowResult->isSuccess()) {
                    foreach ($allowResult->getErrors() as $error) {
                        $result->addError($error);
                    }
                    return $result;
                }
                $changed = true;
            }

            if ((string)$shipment->getField('DEDUCTED') !== 'Y') {
                $deductResult = $shipment->setField('DEDUCTED', 'Y');
                if ($deductResult instanceof Result && !$deductResult->isSuccess()) {
                    foreach ($deductResult->getErrors() as $error) {
                        $result->addError($error);
                    }
                    return $result;
                }
                $changed = true;
            }
        }

        $result->setData(['changed' => $changed]);
        return $result;
    }

    private function extractMetaCollection(array $source, string $field): array
    {
        $value = $source[$field] ?? [];
        if (isset($value['rows']) && is_array($value['rows'])) {
            return array_values(array_filter($value['rows'], 'is_array'));
        }

        if (is_array($value) && array_keys($value) === range(0, count($value) - 1)) {
            return array_values(array_filter($value, 'is_array'));
        }

        return [];
    }

    private function resolveBitrixProductIdByMoySkladAssortment(string $siteId, string $msId, string $type): int
    {
        $msId = trim($msId);
        $type = trim($type);
        if ($msId === '') {
            return 0;
        }

        if (Loader::includeModule('elixir.moyskladcatalog') && class_exists('\Elixir\MoySkladCatalog\Entity\LinkTable')) {
            $row = \Elixir\MoySkladCatalog\Entity\LinkTable::getList([
                'filter' => [
                    '=SITE_ID' => $siteId,
                    '=MS_ID' => $msId,
                    '=MS_TYPE' => $type !== '' ? $type : 'product',
                ],
                'select' => ['BITRIX_ELEMENT_ID', 'BITRIX_PRODUCT_ID'],
                'limit' => 1,
            ])->fetch();

            if (is_array($row)) {
                $elementId = (int)($row['BITRIX_ELEMENT_ID'] ?? 0);
                if ($elementId > 0 && $this->bitrixProductExists($elementId)) {
                    return $elementId;
                }

                $productId = (int)($row['BITRIX_PRODUCT_ID'] ?? 0);
                if ($productId > 0 && $this->bitrixProductExists($productId)) {
                    return $productId;
                }
            }
        }

        if (!Loader::includeModule('iblock')) {
            return 0;
        }

        $row = \CIBlockElement::GetList([], ['=XML_ID' => $msId], false, ['nTopCount' => 1], ['ID'])->Fetch();
        return $row ? (int)$row['ID'] : 0;
    }

    private function bitrixProductExists(int $productId): bool
    {
        if ($productId <= 0 || !Loader::includeModule('iblock')) {
            return false;
        }

        return (bool)\CIBlockElement::GetByID($productId)->Fetch();
    }

    public function handleIncoming(string $siteId, array $query, array $post, string $rawBody, array $headers): Result
    {
        $result = new Result();
        $siteId = trim($siteId);
        if ($siteId === '') {
            $result->addError(new Error('Не указан site_id'));
            return $result;
        }

        if (!$this->isRequestAuthorized($siteId, $query, $headers)) {
            $result->addError(new Error('Неверный секрет вебхука'));
            return $result;
        }

        $payload = $this->decodePayload($rawBody);
        $source = array_replace_recursive($payload, $post, $query);
        $orderRef = $this->extractOrderRef($source);
        $moySkladOrderId = $this->resolveCustomerOrderIdFromSource($siteId, $source, $orderRef);
        $stateHref = $this->extractStateHref($source);
        $directStatus = trim((string)($query['bitrix_status'] ?? $query['bitrix_status_id'] ?? $post['bitrix_status'] ?? $post['bitrix_status_id'] ?? ''));
        $updatedFields = $this->extractUpdatedFields($source);
        $syncStatus = $this->shouldSyncStatus($updatedFields);
        $syncPositions = $this->shouldSyncPositions($siteId, $updatedFields, $orderRef);
        $syncFinance = $this->shouldSyncFinance($updatedFields, $orderRef);

        if ($stateHref === '' && $moySkladOrderId !== '' && $syncStatus) {
            $stateHref = $this->fetchOrderStateHref($siteId, $moySkladOrderId);
        }

        if ($moySkladOrderId === '') {
            $result->setData([
                'order_ref' => $orderRef,
                'state_href' => $stateHref,
            ]);
            $result->addError(new Error('Не удалось определить заказ МойСклад из вебхука'));
            return $result;
        }

        $link = $this->orderLinkRepository->getByMoySkladOrderId($siteId, $moySkladOrderId);
        if (!$link) {
            $link = $this->recoverBitrixOrderLink($siteId, $moySkladOrderId);
        }
        if (!$link) {
            $this->logger->warning($siteId, 'moysklad_webhook', 'customerorder_link_not_found_skipped', [
                'request' => [
                    'order_ref' => $orderRef,
                    'moysklad_order_id' => $moySkladOrderId,
                    'state_href' => $stateHref,
                    'updated_fields' => $updatedFields,
                    'sync_status' => $syncStatus ? 'Y' : 'N',
                    'sync_positions' => $syncPositions ? 'Y' : 'N',
                    'sync_finance' => $syncFinance ? 'Y' : 'N',
                ],
                'response' => [
                    'action' => 'skipped',
                    'reason' => 'bitrix_order_link_not_found',
                ],
            ]);
            $result->setData([
                'actions' => [
                    'skipped' => [
                        'reason' => 'bitrix_order_link_not_found',
                    ],
                ],
                'moysklad_order_id' => $moySkladOrderId,
                'state_href' => $stateHref,
            ]);
            return $result;
        }

        $order = Order::load((int)$link['ORDER_ID']);
        if (!$order instanceof Order) {
            $result->addError(new Error('Заказ Bitrix не найден: #' . (int)$link['ORDER_ID']));
            return $result;
        }

        $currentOrderResult = $this->moySkladApiClient->getCustomerOrderFull($siteId, $moySkladOrderId, ['expand' => 'state']);
        if (!$currentOrderResult->isSuccess()) {
            foreach ($currentOrderResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }
        $remoteOrder = (array)($currentOrderResult->getData()['response'] ?? []);
        if (!StatusSyncService::customerOrderBelongsToOrder($siteId, $order, $remoteOrder)) {
            $this->logger->warning($siteId, 'moysklad_webhook', 'foreign_customerorder_link_blocked', [
                'order_id' => (int)$order->getId(), 'moysklad_order_id' => $moySkladOrderId,
            ]);
            $result->setData(['actions' => ['skipped' => ['reason' => 'foreign_customerorder_link']],
                'moysklad_order_id' => $moySkladOrderId]);
            return $result;
        }
        if ($syncStatus && $directStatus === '') {
            // Queue payloads can arrive late; mirror the current document state.
            $stateHref = trim((string)($remoteOrder['state']['meta']['href'] ?? ''));
        }

        $targetStatus = $directStatus;
        $map = null;
        if ($targetStatus === '' && $stateHref !== '') {
            $map = $this->statusMapRepository->getByMoySkladStateHref($siteId, $stateHref);
            if ($map) {
                $targetStatus = (string)$map['BITRIX_STATUS_ID'];
            }
        }

        if ($targetStatus === '' && $syncStatus && !$syncPositions && !$syncFinance) {
            $result->setData([
                'moysklad_order_id' => $moySkladOrderId,
                'order_id' => (int)$order->getId(),
                'state_href' => $stateHref,
                'direct_status' => $directStatus,
                'updated_fields' => $updatedFields,
            ]);
            $result->addError(new Error('Не удалось определить статус Bitrix: укажите bitrix_status в URL или заполните маппинг статуса МойСклад'));
            return $result;
        }

        $this->logger->info($siteId, 'moysklad_webhook', 'resolved_customerorder_status', [
            'order_id' => (int)$order->getId(),
            'lead_id' => (string)($link['AMO_LEAD_ID'] ?? ''),
            'moysklad_order_id' => $moySkladOrderId,
            'request' => [
                'order_ref' => $orderRef,
                'state_href' => $stateHref,
                'direct_status' => $directStatus,
                'target_status' => $targetStatus,
                'updated_fields' => $updatedFields,
                'sync_status' => $syncStatus ? 'Y' : 'N',
                'sync_positions' => $syncPositions ? 'Y' : 'N',
                'sync_finance' => $syncFinance ? 'Y' : 'N',
            ],
        ]);

        $actions = [];
        if ($syncStatus && $targetStatus !== '') {
            $applyResult = $this->applyTargetStatus($siteId, $order, $targetStatus);
            if (!$applyResult->isSuccess()) {
                return $applyResult;
            }
            $actions['status'] = $applyResult->getData();
        } elseif ($syncStatus && $targetStatus === '') {
            $this->logger->warning($siteId, 'moysklad_webhook', 'status_mapping_not_found_positions_continue', [
                'order_id' => (int)$order->getId(),
                'moysklad_order_id' => $moySkladOrderId,
                'request' => [
                    'state_href' => $stateHref,
                    'updated_fields' => $updatedFields,
                ],
                'message' => 'Статус МойСклад не сопоставлен, обработка позиций продолжается',
            ]);
        }

        if ($syncPositions) {
            $positionsResult = $this->applyOrderPositions($siteId, $order, $moySkladOrderId);
            if (!$positionsResult->isSuccess()) {
                $positionErrors = $positionsResult->getErrorMessages();
                $actions['positions'] = [
                    'action' => 'skipped',
                    'reason' => 'positions_sync_failed',
                    'errors' => $positionErrors,
                ];
                $this->logger->warning($siteId, 'moysklad_webhook', 'positions_sync_failed_non_blocking', [
                    'order_id' => (int)$order->getId(),
                    'lead_id' => (string)($link['AMO_LEAD_ID'] ?? ''),
                    'request' => [
                        'moysklad_order_id' => $moySkladOrderId,
                        'updated_fields' => $updatedFields,
                    ],
                    'response' => [
                        'errors' => $positionErrors,
                    ],
                ]);
            } else {
                $actions['positions'] = $positionsResult->getData();
            }
        }

        if ($syncFinance) {
            $financeResult = $this->applyOrderFinanceSnapshot($siteId, $order, $moySkladOrderId);
            if (!$financeResult->isSuccess()) {
                return $financeResult;
            }
            $actions['finance'] = $financeResult->getData();
        }

        if (empty($actions)) {
            $actions['skipped'] = [
                'reason' => 'updated_fields_not_supported',
                'updated_fields' => $updatedFields,
            ];
        }

        $this->logger->info($siteId, 'moysklad_webhook', 'apply_customerorder_update', [
            'order_id' => (int)$order->getId(),
            'lead_id' => (string)($link['AMO_LEAD_ID'] ?? ''),
            'moysklad_order_id' => $moySkladOrderId,
            'request' => [
                'order_ref' => $orderRef,
                'state_href' => $stateHref,
                'direct_status' => $directStatus,
                'target_status' => $targetStatus,
                'updated_fields' => $updatedFields,
                'sync_status' => $syncStatus ? 'Y' : 'N',
                'sync_positions' => $syncPositions ? 'Y' : 'N',
                'sync_finance' => $syncFinance ? 'Y' : 'N',
            ],
            'response' => $actions,
        ]);

        $result->setData([
            'actions' => $actions,
            'moysklad_order_id' => $moySkladOrderId,
            'state_href' => $stateHref,
        ]);
        return $result;
    }

    private function applyTargetStatus(string $siteId, Order $order, string $targetStatus): Result
    {
        if ($targetStatus === StatusSyncService::MAP_KEY_PAYMENT_PAID) {
            return $this->markOrderPaid($siteId, $order);
        }

        if ($targetStatus === StatusSyncService::MAP_KEY_ORDER_CANCELED) {
            return $this->cancelOrder($siteId, $order);
        }

        if (!$this->isValidBitrixOrderStatus($targetStatus)) {
            $result = new Result();
            $message = 'Статус "' . $targetStatus . '" не является статусом заказа Bitrix и не будет записан в STATUS_ID';
            $this->logger->error($siteId, 'moysklad_webhook', 'invalid_target_bitrix_status', [
                'order_id' => (int)$order->getId(),
                'request' => [
                    'target_status' => $targetStatus,
                ],
                'message' => $message,
            ]);
            $result->addError(new Error($message));
            return $result;
        }

        $result = new Result();
        $currentStatus = (string)$order->getField('STATUS_ID');
        if ($currentStatus === $targetStatus) {
            $result->setData([
                'action' => 'skipped',
                'reason' => 'status_already_synced',
                'order_id' => (int)$order->getId(),
                'bitrix_status_id' => $targetStatus,
            ]);
            return $result;
        }

        $setResult = $order->setField('STATUS_ID', $targetStatus);
        if (!$setResult->isSuccess()) {
            foreach ($setResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        InboundSyncGuard::suppressOrderStatusSync((int)$order->getId());
        try {
            $saveResult = $order->save();
        } finally {
            InboundSyncGuard::releaseOrderStatusSync((int)$order->getId());
        }
        if (!$saveResult->isSuccess()) {
            foreach ($saveResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        $result->setData([
            'action' => 'updated',
            'order_id' => (int)$order->getId(),
            'bitrix_status_id' => $targetStatus,
            'previous_status_id' => $currentStatus,
        ]);
        return $result;
    }

    private function isValidBitrixOrderStatus(string $statusId): bool
    {
        $statusId = trim($statusId);
        if ($statusId === '' || $this->statusMapRepository->isAmoMoySkladOnlyKey($statusId)) {
            return false;
        }

        return (bool)OrderStatus::getList([
            'filter' => ['=ID' => $statusId],
            'select' => ['ID'],
            'limit' => 1,
        ])->fetch();
    }

    private function markOrderPaid(string $siteId, Order $order): Result
    {
        $result = new Result();
        $changed = false;
        foreach ($order->getPaymentCollection() as $payment) {
            if ($payment->isInner() || (string)$payment->getField('PAID') === 'Y') {
                continue;
            }

            $setResult = $payment->setPaid('Y');
            if (!$setResult->isSuccess()) {
                foreach ($setResult->getErrors() as $error) {
                    $result->addError($error);
                }
                return $result;
            }

            $changed = true;
        }

        if (!$changed) {
            $result->setData([
                'action' => 'skipped',
                'reason' => 'payment_already_synced',
                'order_id' => (int)$order->getId(),
            ]);
            return $result;
        }

        InboundSyncGuard::suppressOrderStatusSync((int)$order->getId());
        try {
            $saveResult = $order->save();
        } finally {
            InboundSyncGuard::releaseOrderStatusSync((int)$order->getId());
        }
        if (!$saveResult->isSuccess()) {
            foreach ($saveResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        $result->setData([
            'action' => 'updated',
            'order_id' => (int)$order->getId(),
            'payment_paid' => 'Y',
        ]);
        return $result;
    }

    private function cancelOrder(string $siteId, Order $order): Result
    {
        $result = new Result();
        if ((string)$order->getField('CANCELED') === 'Y') {
            $result->setData([
                'action' => 'skipped',
                'reason' => 'cancel_already_synced',
                'order_id' => (int)$order->getId(),
            ]);
            return $result;
        }

        $setResult = $order->setField('CANCELED', 'Y');
        if (!$setResult->isSuccess()) {
            foreach ($setResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        InboundSyncGuard::suppressOrderStatusSync((int)$order->getId());
        try {
            $saveResult = $order->save();
        } finally {
            InboundSyncGuard::releaseOrderStatusSync((int)$order->getId());
        }
        if (!$saveResult->isSuccess()) {
            foreach ($saveResult->getErrors() as $error) {
                $result->addError($error);
            }
            return $result;
        }

        $result->setData([
            'action' => 'updated',
            'order_id' => (int)$order->getId(),
            'canceled' => 'Y',
        ]);
        return $result;
    }

    private function fetchOrderStateHref(string $siteId, string $moySkladOrderId): string
    {
        $response = $this->moySkladApiClient->request(
            $siteId,
            'GET',
            'entity/customerorder/' . rawurlencode($moySkladOrderId),
            null,
            ['expand' => 'state']
        );

        if (!$response->isSuccess()) {
            $this->logger->error($siteId, 'moysklad_webhook', 'fetch_customerorder_failed', [
                'moysklad_order_id' => $moySkladOrderId,
                'message' => implode('; ', $response->getErrorMessages()),
            ]);
            return '';
        }

        $order = $response->getData()['response'] ?? [];
        return trim((string)($order['state']['meta']['href'] ?? ''));
    }

    private function decodePayload(string $rawBody): array
    {
        $rawBody = trim($rawBody);
        if ($rawBody === '') {
            return [];
        }

        $decoded = json_decode($rawBody, true);
        return is_array($decoded) ? $decoded : [];
    }

    private function extractOrderRef(array $source): string
    {
        $paths = [
            ['events', 0, 'meta', 'href'],
            ['events', 0, 'entity', 'meta', 'href'],
            ['events', 0, 'object', 'meta', 'href'],
            ['rows', 0, 'meta', 'href'],
            ['rows', 0, 'entity', 'meta', 'href'],
            ['rows', 0, 'object', 'meta', 'href'],
            ['customerorder', 'meta', 'href'],
            ['entity', 'meta', 'href'],
            ['object', 'meta', 'href'],
            ['meta', 'href'],
            ['href'],
            ['events', 0, 'id'],
            ['events', 0, 'entity', 'id'],
            ['events', 0, 'object', 'id'],
            ['rows', 0, 'id'],
            ['rows', 0, 'entity', 'id'],
            ['rows', 0, 'object', 'id'],
            ['customerorder', 'id'],
            ['entity', 'id'],
            ['object', 'id'],
            ['events', 0, 'objectId'],
            ['rows', 0, 'objectId'],
            ['objectId'],
            ['id'],
            ['moysklad_order_id'],
            ['ms_order_id'],
        ];

        foreach ($paths as $path) {
            $value = $this->valueByPath($source, $path);
            if (is_scalar($value) && trim((string)$value) !== '') {
                return trim((string)$value);
            }
        }

        return '';
    }

    private function extractStateHref(array $source): string
    {
        $paths = [
            ['events', 0, 'state', 'meta', 'href'],
            ['events', 0, 'entity', 'state', 'meta', 'href'],
            ['events', 0, 'object', 'state', 'meta', 'href'],
            ['rows', 0, 'state', 'meta', 'href'],
            ['rows', 0, 'entity', 'state', 'meta', 'href'],
            ['rows', 0, 'object', 'state', 'meta', 'href'],
            ['state', 'meta', 'href'],
            ['customerorder', 'state', 'meta', 'href'],
            ['entity', 'state', 'meta', 'href'],
            ['object', 'state', 'meta', 'href'],
            ['state_href'],
            ['moysklad_state_href'],
        ];

        foreach ($paths as $path) {
            $value = $this->valueByPath($source, $path);
            if (is_scalar($value) && trim((string)$value) !== '') {
                return trim((string)$value);
            }
        }

        return '';
    }

    private function extractUpdatedFields(array $source): array
    {
        $paths = [
            ['events', 0, 'updatedFields'],
            ['updatedFields'],
        ];

        foreach ($paths as $path) {
            $value = $this->valueByPath($source, $path);
            if (!is_array($value)) {
                continue;
            }

            $fields = [];
            foreach ($value as $field) {
                $field = trim((string)$field);
                if ($field !== '') {
                    $fields[] = $field;
                }
            }

            return array_values(array_unique($fields));
        }

        return [];
    }

    private function shouldSyncStatus(array $updatedFields): bool
    {
        if (empty($updatedFields)) {
            return true;
        }

        foreach ($updatedFields as $field) {
            $field = mb_strtolower((string)$field);
            if ($field === 'state' || mb_strpos($field, 'state.') === 0) {
                return true;
            }
        }

        return false;
    }

    private function shouldSyncPositions(string $siteId, array $updatedFields, string $entityRef = ''): bool
    {
        if (Option::get(Module::ID, 'ms_order_webhook_sync_positions', 'N', $siteId) !== 'Y') {
            return false;
        }

        [$entityType] = $this->extractEntityTypeAndIdFromRef($entityRef);
        if ($entityType !== '' && $entityType !== 'customerorder') {
            return false;
        }

        if (empty($updatedFields)) {
            return false;
        }

        foreach ($updatedFields as $field) {
            $field = mb_strtolower((string)$field);
            if ($field === 'positions' || $field === 'position' || mb_strpos($field, 'positions.') === 0) {
                return true;
            }
        }

        return false;
    }

    private function shouldSyncFinance(array $updatedFields, string $entityRef = ''): bool
    {
        [$entityType] = $this->extractEntityTypeAndIdFromRef($entityRef);
        if ($entityType !== '' && $entityType !== 'customerorder') {
            return in_array($entityType, ['demand', 'retaildemand', 'paymentin', 'prepayment'], true);
        }

        if (empty($updatedFields)) {
            return true;
        }

        $supportedFields = [
            'payedsum',
            'shippedsum',
            'payments',
            'prepayments',
            'demands',
            'customerorder',
            'operations',
            'sum',
            'moment',
            'applicable',
        ];

        foreach ($updatedFields as $field) {
            $field = mb_strtolower(trim((string)$field));
            foreach ($supportedFields as $supportedField) {
                if ($field === $supportedField || mb_strpos($field, $supportedField . '.') === 0) {
                    return true;
                }
            }
        }

        return false;
    }

    private function resolveCustomerOrderIdFromSource(string $siteId, array $source, string $entityRef): string
    {
        $customerOrderHref = $this->extractCustomerOrderHrefFromSource($source);
        if ($customerOrderHref !== '') {
            $customerOrderId = $this->extractCustomerOrderId($customerOrderHref);
            if ($customerOrderId !== '') {
                return $customerOrderId;
            }
        }

        $customerOrderId = $this->extractCustomerOrderId($entityRef);
        if ($customerOrderId !== '') {
            return $customerOrderId;
        }

        [$parsedEntityType, $parsedEntityId] = $this->extractEntityTypeAndIdFromRef($entityRef);
        if ($parsedEntityType === '' && $parsedEntityId === '' && trim($entityRef) !== '') {
            $sourceEntityType = $this->extractEntityTypeFromSource($source);
            if ($sourceEntityType !== '') {
                if ($sourceEntityType === 'customerorder') {
                    return trim($entityRef);
                }

                return $this->fetchCustomerOrderIdFromRelatedDocument($siteId, $sourceEntityType, $entityRef);
            }
        }

        [$entityType, $entityId] = $this->extractEntityTypeAndIdFromRef($entityRef);
        if ($entityType === '' || $entityId === '') {
            return '';
        }

        return $this->fetchCustomerOrderIdFromRelatedDocument($siteId, $entityType, $entityId);
    }

    private function extractCustomerOrderHrefFromSource(array $source): string
    {
        $paths = [
            ['customerOrder', 'meta', 'href'],
            ['customerorder', 'meta', 'href'],
            ['events', 0, 'customerOrder', 'meta', 'href'],
            ['events', 0, 'entity', 'customerOrder', 'meta', 'href'],
            ['events', 0, 'object', 'customerOrder', 'meta', 'href'],
            ['rows', 0, 'customerOrder', 'meta', 'href'],
            ['rows', 0, 'entity', 'customerOrder', 'meta', 'href'],
            ['rows', 0, 'object', 'customerOrder', 'meta', 'href'],
        ];

        foreach ($paths as $path) {
            $value = $this->valueByPath($source, $path);
            if (is_scalar($value) && trim((string)$value) !== '') {
                return trim((string)$value);
            }
        }

        return '';
    }

    private function extractEntityTypeFromSource(array $source): string
    {
        $paths = [
            ['events', 0, 'meta', 'type'],
            ['events', 0, 'entity', 'meta', 'type'],
            ['events', 0, 'object', 'meta', 'type'],
            ['rows', 0, 'meta', 'type'],
            ['rows', 0, 'entity', 'meta', 'type'],
            ['rows', 0, 'object', 'meta', 'type'],
            ['meta', 'type'],
            ['entity', 'meta', 'type'],
            ['object', 'meta', 'type'],
            ['events', 0, 'objectType'],
            ['events', 0, 'entityType'],
            ['events', 0, 'type'],
            ['rows', 0, 'objectType'],
            ['rows', 0, 'entityType'],
            ['rows', 0, 'type'],
            ['objectType'],
            ['entityType'],
            ['type'],
        ];

        foreach ($paths as $path) {
            $value = $this->valueByPath($source, $path);
            if (!is_scalar($value)) {
                continue;
            }

            $type = $this->normalizeMoySkladEntityType((string)$value);
            if ($type !== '') {
                return $type;
            }
        }

        return '';
    }

    private function normalizeMoySkladEntityType(string $type): string
    {
        $type = trim($type);
        if ($type === '') {
            return '';
        }

        if (preg_match('~/entity/([^/]+)/~', $type, $matches)) {
            $type = (string)$matches[1];
        }

        $key = mb_strtolower(str_replace(['_', '-', ' '], '', $type));
        $map = [
            'customerorder' => 'customerorder',
            'заказпокупателя' => 'customerorder',
            'demand' => 'demand',
            'отгрузка' => 'demand',
            'retaildemand' => 'retaildemand',
            'paymentin' => 'paymentin',
            'входящийплатеж' => 'paymentin',
            'prepayment' => 'prepayment',
            'предоплата' => 'prepayment',
        ];

        return $map[$key] ?? '';
    }

    private function fetchCustomerOrderIdFromRelatedDocument(string $siteId, string $entityType, string $entityId, array $visited = []): string
    {
        $entityType = mb_strtolower(trim($entityType));
        $entityId = trim($entityId);
        if ($entityType === '' || $entityId === '') {
            return '';
        }

        if ($entityType === 'customerorder') {
            return $entityId;
        }

        $visitKey = $entityType . ':' . $entityId;
        if (isset($visited[$visitKey])) {
            return '';
        }
        $visited[$visitKey] = true;

        $query = [];
        if ($entityType === 'paymentin') {
            $query['expand'] = 'operations';
        } elseif (in_array($entityType, ['demand', 'retaildemand', 'prepayment'], true)) {
            $query['expand'] = 'customerOrder';
        }

        $response = $this->moySkladApiClient->request($siteId, 'GET', 'entity/' . rawurlencode($entityType) . '/' . rawurlencode($entityId), null, $query);

        if (!$response->isSuccess()) {
            $this->logger->error($siteId, 'moysklad_webhook', 'fetch_related_document_failed', [
                'request' => [
                    'entity_type' => $entityType,
                    'entity_id' => $entityId,
                ],
                'message' => implode('; ', $response->getErrorMessages()),
            ]);
            return '';
        }

        $document = (array)($response->getData()['response'] ?? []);
        $customerOrderId = $this->extractCustomerOrderId((string)($document['customerOrder']['meta']['href'] ?? ''));
        if ($customerOrderId !== '') {
            return $customerOrderId;
        }

        foreach ($this->extractMetaCollection($document, 'operations') as $operation) {
            $href = (string)($operation['meta']['href'] ?? $operation['href'] ?? '');
            [$operationType, $operationId] = $this->extractEntityTypeAndIdFromRef($href);
            if ($operationType === '' || $operationId === '') {
                continue;
            }

            if ($operationType === 'customerorder') {
                return $operationId;
            }

            if (in_array($operationType, ['demand', 'retaildemand', 'prepayment'], true)) {
                $customerOrderId = $this->fetchCustomerOrderIdFromRelatedDocument($siteId, $operationType, $operationId, $visited);
                if ($customerOrderId !== '') {
                    return $customerOrderId;
                }
            }
        }

        return '';
    }

    private function extractEntityTypeAndIdFromRef(string $ref): array
    {
        $ref = trim($ref);
        if ($ref === '') {
            return ['', ''];
        }

        $path = (string)parse_url($ref, PHP_URL_PATH);
        if ($path === '') {
            $path = $ref;
        }

        if (preg_match('~/entity/([^/]+)/([^/?#]+)~', $path, $matches)) {
            return [mb_strtolower((string)$matches[1]), (string)$matches[2]];
        }

        return ['', ''];
    }

    private function recoverBitrixOrderLink(string $siteId, string $moySkladOrderId): ?array
    {
        $response = $this->moySkladApiClient->getCustomerOrderFull($siteId, $moySkladOrderId, ['expand' => 'state']);
        if (!$response->isSuccess()) {
            $this->logger->error($siteId, 'moysklad_webhook', 'recover_order_link_fetch_failed', [
                'moysklad_order_id' => $moySkladOrderId,
                'message' => implode('; ', $response->getErrorMessages()),
            ]);
            return null;
        }

        $customerOrder = (array)($response->getData()['response'] ?? []);
        $orderId = $this->extractBitrixOrderIdFromCustomerOrder($siteId, $customerOrder);
        if ($orderId <= 0 || !Loader::includeModule('sale')) {
            return null;
        }

        $order = Order::load($orderId);
        if (!$order instanceof Order) {
            return null;
        }

        $orderSiteId = (string)$order->getSiteId();
        if ($orderSiteId !== '') {
            $siteId = $orderSiteId;
        }

        $moySkladUrl = (string)($customerOrder['meta']['uuidHref'] ?? $customerOrder['meta']['href'] ?? '');
        $this->orderLinkRepository->markMoySkladSuccess($siteId, $orderId, $moySkladOrderId, $moySkladUrl !== '' ? $moySkladUrl : null);

        return $this->orderLinkRepository->getByOrderId($siteId, $orderId);
    }

    private function extractBitrixOrderIdFromCustomerOrder(string $siteId, array $customerOrder): int
    {
        $externalCode = trim((string)($customerOrder['externalCode'] ?? ''));
        if (mb_strpos($externalCode, 'bitrix-') === 0) {
            return MoySkladExternalCode::extractOrderId($siteId, $externalCode);
        }

        $description = trim((string)($customerOrder['description'] ?? ''));
        if ($description !== '' && preg_match('~(?:Заказ\s+Bitrix|Bitrix\s+order)\s*#?\s*(\d+)~ui', $description, $matches)) {
            return (int)$matches[1];
        }

        $name = trim((string)($customerOrder['name'] ?? ''));
        if ($name !== '' && preg_match('~#?(\d{2,})~', $name, $matches)) {
            return (int)$matches[1];
        }

        return 0;
    }

    private function extractCustomerOrderId(string $value): string
    {
        $value = trim($value);
        if ($value === '') {
            return '';
        }

        if (preg_match('~/entity/customerorder/([^/?#]+)~', $value, $matches)) {
            return (string)$matches[1];
        }

        if (preg_match('~^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$~i', $value)) {
            return $value;
        }

        return '';
    }

    private function extractMoySkladEntityIdFromHref(string $href): string
    {
        $href = trim($href);
        if ($href === '') {
            return '';
        }

        $path = (string)parse_url($href, PHP_URL_PATH);
        if (preg_match('~/entity/[^/]+/([^/?#]+)~', $path, $matches)) {
            return (string)$matches[1];
        }

        return '';
    }

    private function extractWebhookRequestId(array $query, array $payload, string $rawBody): string
    {
        foreach (['requestId', 'request_id'] as $key) {
            $value = trim((string)($query[$key] ?? $payload[$key] ?? ''));
            if ($value !== '') {
                return mb_substr($value, 0, 128);
            }
        }

        return 'local-' . hash('sha256', $rawBody !== '' ? $rawBody : json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    }

    private function ensureQueueAgent(): void
    {
        if (!class_exists('\CAgent')) {
            return;
        }

        $name = '\\Elixir\\AmoCrmBridge\\Service\\MoySkladOrderWebhookAgent::processQueue();';
        $normalizedName = ltrim($name, '\\');
        $keepId = 0;
        $agents = \CAgent::GetList(['ID' => 'ASC'], [
            'MODULE_ID' => 'elixir.amocrmbridge',
        ]);

        while ($agent = $agents->Fetch()) {
            if (ltrim(trim((string)($agent['NAME'] ?? '')), '\\') !== $normalizedName) {
                continue;
            }

            $agentId = (int)($agent['ID'] ?? 0);
            if ($keepId <= 0) {
                $keepId = $agentId;
                if ((string)($agent['ACTIVE'] ?? '') !== 'Y') {
                    \CAgent::Update($agentId, ['ACTIVE' => 'Y']);
                }
                continue;
            }

            if ((string)($agent['ACTIVE'] ?? '') === 'Y') {
                \CAgent::Update($agentId, ['ACTIVE' => 'N']);
            }
        }

        if ($keepId > 0) {
            return;
        }

        \CAgent::AddAgent(
            $name,
            'elixir.amocrmbridge',
            'N',
            60,
            '',
            'Y',
            ConvertTimeStamp(time() + 60, 'FULL')
        );
    }

    private function valueByPath(array $source, array $path)
    {
        $cursor = $source;
        foreach ($path as $key) {
            if (!is_array($cursor) || !array_key_exists($key, $cursor)) {
                return null;
            }
            $cursor = $cursor[$key];
        }

        return $cursor;
    }

    private function isRequestAuthorized(string $siteId, array $query, array $headers): bool
    {
        $connection = $this->settingsRepository->getConnectionBySite($siteId);
        $expectedSecret = trim((string)($connection['WEBHOOK_SECRET'] ?? ''));
        $expectedToken = trim((string)($connection['SERVICE_TOKEN'] ?? ''));

        if ($expectedSecret === '' && $expectedToken === '') {
            return true;
        }

        $providedSecret = trim((string)($query['webhook_secret'] ?? $query['secret'] ?? ''));
        if ($expectedSecret !== '' && $providedSecret !== '' && hash_equals($expectedSecret, $providedSecret)) {
            return true;
        }
        if ($expectedToken !== '' && $providedSecret !== '' && hash_equals($expectedToken, $providedSecret)) {
            return true;
        }

        $providedToken = trim((string)($query['service_token'] ?? $query['token'] ?? ''));
        if ($providedToken === '' && isset($headers['x-service-token'])) {
            $providedToken = trim((string)$headers['x-service-token']);
        }
        if ($providedToken === '' && isset($headers['x-elixir-secret'])) {
            $providedToken = trim((string)$headers['x-elixir-secret']);
        }
        if ($providedToken === '' && isset($headers['authorization'])) {
            $authorization = trim((string)$headers['authorization']);
            if (stripos($authorization, 'Bearer ') === 0) {
                $providedToken = trim(substr($authorization, 7));
            }
        }

        return $expectedToken !== '' && $providedToken !== '' && hash_equals($expectedToken, $providedToken);
    }
}
