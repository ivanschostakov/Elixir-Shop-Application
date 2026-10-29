<?php

namespace Elixir\AmoCrmBridge\Service;

use Bitrix\Sale\Order;
use Elixir\AmoCrmBridge\Api\AmoApiClient;
use Elixir\AmoCrmBridge\Api\MoySkladApiClient;
use Elixir\AmoCrmBridge\Logger\BridgeLogger;
use Elixir\AmoCrmBridge\Repository\OrderLinkRepository;
use Elixir\AmoCrmBridge\Repository\StatusMapRepository;

class StatusSyncService
{
    public const MAP_KEY_PAYMENT_PAID = '__PAYED__';
    public const MAP_KEY_ORDER_CANCELED = '__CANCELED__';

    private const STATUS_PROGRESS = [
        81419122 => 10, 74461446 => 15, 82756582 => 15, 75784938 => 20,
        75784946 => 30, 75784942 => 40, 76566302 => 50, 76566306 => 60, 142 => 70,
    ];

    private AmoApiClient $apiClient;
    private MoySkladApiClient $moySkladApiClient;
    private OrderLinkRepository $orderLinkRepository;
    private StatusMapRepository $statusMapRepository;
    private BridgeLogger $logger;

    public function __construct(
        AmoApiClient $apiClient,
        MoySkladApiClient $moySkladApiClient,
        OrderLinkRepository $orderLinkRepository,
        StatusMapRepository $statusMapRepository,
        BridgeLogger $logger
    ) {
        $this->apiClient = $apiClient;
        $this->moySkladApiClient = $moySkladApiClient;
        $this->orderLinkRepository = $orderLinkRepository;
        $this->statusMapRepository = $statusMapRepository;
        $this->logger = $logger;
    }

    public function syncOrderStatus(Order $order, string $siteId): void
    {
        $this->syncOrderByMapKey($order, $siteId, (string)$order->getField('STATUS_ID'), 'update_lead_status');
    }

    public function syncOrderPaymentPaid(Order $order, string $siteId): void
    {
        $this->syncOrderByMapKey($order, $siteId, self::MAP_KEY_PAYMENT_PAID, 'update_lead_status_payment_paid');
    }

    public function syncOrderCanceled(Order $order, string $siteId): void
    {
        $this->syncOrderByMapKey($order, $siteId, self::MAP_KEY_ORDER_CANCELED, 'update_lead_status_order_canceled');
    }

    public function syncMoySkladOrderStatus(Order $order, string $siteId): void
    {
        $this->syncMoySkladByMapKey($order, $siteId, (string)$order->getField('STATUS_ID'), 'update_moysklad_status');
    }

    public function syncMoySkladPaymentPaid(Order $order, string $siteId): void
    {
        $this->syncMoySkladByMapKey($order, $siteId, self::MAP_KEY_PAYMENT_PAID, 'update_moysklad_status_payment_paid');
    }

    public function syncMoySkladCanceled(Order $order, string $siteId): void
    {
        $this->syncMoySkladByMapKey($order, $siteId, self::MAP_KEY_ORDER_CANCELED, 'update_moysklad_status_order_canceled');
    }

    private function syncOrderByMapKey(Order $order, string $siteId, string $mapKey, string $operation): void
    {
        $orderId = (int)$order->getId();
        $link = $this->orderLinkRepository->getByOrderId($siteId, $orderId);
        if (!$link) {
            $this->logger->info($siteId, 'status_sync', $operation . '_no_link', [
                'order_id' => $orderId,
                'request' => [
                    'map_key' => $mapKey,
                ],
            ]);
            return;
        }

        $map = $this->statusMapRepository->getByBitrixStatus($siteId, $mapKey);
        if (!$map) {
            $this->logger->info($siteId, 'status_sync', $operation . '_no_map', [
                'order_id' => $orderId,
                'lead_id' => (string)$link['AMO_LEAD_ID'],
                'request' => [
                    'map_key' => $mapKey,
                ],
            ]);
            return;
        }

        if (!$this->syncMoySkladState($siteId, $order, $link, $map, $operation)) {
            // A rejected stale MS update must not reach amoCRM by the other path.
            return;
        }

        if (empty($link['AMO_LEAD_ID'])) {
            $this->logger->info($siteId, 'status_sync', $operation . '_no_amo_link', [
                'order_id' => $orderId,
                'request' => [
                    'map_key' => $mapKey,
                    'moysklad_state_href' => (string)($map['MOYSKLAD_STATE_HREF'] ?? ''),
                ],
            ]);
            return;
        }

        if (empty($map['AMO_STATUS_ID'])) {
            $this->logger->info($siteId, 'status_sync', $operation . '_amo_status_empty', [
                'order_id' => $orderId,
                'lead_id' => (string)$link['AMO_LEAD_ID'],
                'request' => [
                    'map_key' => $mapKey,
                    'moysklad_state_href' => (string)($map['MOYSKLAD_STATE_HREF'] ?? ''),
                ],
            ]);
            return;
        }

        $currentLead = $this->apiClient->request($siteId, 'GET', 'leads/' . (int)$link['AMO_LEAD_ID']);
        if (!$currentLead->isSuccess()) {
            $this->logger->warning($siteId, 'status_sync', $operation . '_current_state_unavailable', [
                'order_id' => $orderId, 'lead_id' => (string)$link['AMO_LEAD_ID'],
            ]);
            return;
        }
        $currentStatus = (int)($currentLead->getData()['response']['status_id'] ?? 0);
        $targetStatus = (int)$map['AMO_STATUS_ID'];
        if ($currentStatus === $targetStatus) {
            return;
        }
        if (self::isStatusRegression($currentStatus, $targetStatus)) {
            $this->logger->warning($siteId, 'status_sync', $operation . '_regression_blocked', [
                'order_id' => $orderId, 'lead_id' => (string)$link['AMO_LEAD_ID'],
                'current_status' => $currentStatus, 'target_status' => $targetStatus,
            ]);
            return;
        }

        $payload = [
            'id' => (int)$link['AMO_LEAD_ID'],
            'status_id' => (int)$map['AMO_STATUS_ID'],
        ];
        if (!empty($map['AMO_PIPELINE_ID'])) {
            $payload['pipeline_id'] = (int)$map['AMO_PIPELINE_ID'];
        }

        $result = $this->apiClient->request($siteId, 'PATCH', 'leads', [$payload]);
        if ($result->isSuccess()) {
            $this->orderLinkRepository->markSuccess($siteId, $orderId, (string)$link['AMO_LEAD_ID'], $link['AMO_LEAD_URL'] ?? null);
            $this->logger->info($siteId, 'status_sync', $operation, [
                'order_id' => $orderId,
                'lead_id' => (string)$link['AMO_LEAD_ID'],
                'request' => $payload,
            ]);
            return;
        }

        $this->orderLinkRepository->markError($siteId, $orderId, implode('; ', $result->getErrorMessages()));
        $this->logger->error($siteId, 'status_sync', $operation, [
            'order_id' => $orderId,
            'lead_id' => (string)$link['AMO_LEAD_ID'],
            'request' => $payload,
            'message' => implode('; ', $result->getErrorMessages()),
        ]);
    }

    private function syncMoySkladByMapKey(Order $order, string $siteId, string $mapKey, string $operation): void
    {
        $orderId = (int)$order->getId();
        $link = $this->orderLinkRepository->getByOrderId($siteId, $orderId);
        if (!$link) {
            $this->logger->info($siteId, 'moysklad_order_status', $operation . '_no_link', [
                'order_id' => $orderId,
                'request' => [
                    'map_key' => $mapKey,
                ],
            ]);
            return;
        }

        $map = $this->statusMapRepository->getByBitrixStatus($siteId, $mapKey);
        if (!$map) {
            $this->logger->info($siteId, 'moysklad_order_status', $operation . '_no_map', [
                'order_id' => $orderId,
                'lead_id' => (string)($link['AMO_LEAD_ID'] ?? ''),
                'request' => [
                    'map_key' => $mapKey,
                ],
            ]);
            return;
        }

        $this->syncMoySkladState($siteId, $order, $link, $map, $operation);
    }

    private function syncMoySkladState(string $siteId, Order $order, array $link, array $map, string $operation): bool
    {
        $orderId = (int)$order->getId();
        $stateHref = trim((string)($map['MOYSKLAD_STATE_HREF'] ?? ''));
        if ($stateHref === '') {
            return true;
        }

        $moySkladOrderId = trim((string)($link['MOYSKLAD_ORDER_ID'] ?? ''));
        if ($moySkladOrderId === '') {
            $this->logger->warning($siteId, 'moysklad_order_status', $operation . '_missing_customerorder_link', [
                'order_id' => $orderId,
                'lead_id' => (string)($link['AMO_LEAD_ID'] ?? ''),
                'state_href' => $stateHref,
                'message' => 'Не найден ID заказа МойСклад для локальной смены статуса',
            ]);
            return true;
        }

        $currentResult = $this->moySkladApiClient->getCustomerOrderFull($siteId, $moySkladOrderId, ['expand' => 'state']);
        if (!$currentResult->isSuccess()) {
            $this->logger->warning($siteId, 'moysklad_order_status', $operation . '_current_state_unavailable', [
                'order_id' => $orderId, 'moysklad_order_id' => $moySkladOrderId,
            ]);
            return false;
        }
        $remoteOrder = (array)($currentResult->getData()['response'] ?? []);
        if (!self::customerOrderBelongsToOrder($siteId, $order, $remoteOrder)) {
            $this->logger->error($siteId, 'moysklad_order_status', $operation . '_foreign_link_blocked', [
                'order_id' => $orderId, 'moysklad_order_id' => $moySkladOrderId,
                'remote_name' => (string)($remoteOrder['name'] ?? ''),
            ]);
            return false;
        }
        $currentState = (array)($remoteOrder['state'] ?? []);
        $currentHref = trim((string)($currentState['meta']['href'] ?? ''));
        if ($currentHref === '') {
            return false;
        }
        if ($currentHref === $stateHref) {
            return true;
        }
        $currentMap = $this->statusMapRepository->getByMoySkladStateHref($siteId, $currentHref);
        $currentStatus = (int)($currentMap['AMO_STATUS_ID'] ?? 0);
        $targetStatus = (int)($map['AMO_STATUS_ID'] ?? 0);
        $terminal = in_array((string)($currentState['stateType'] ?? ''), ['Successful', 'Unsuccessful'], true)
            || in_array((string)($currentState['name'] ?? ''), ['Груз доставлен / Успех', 'Груз доставлен', 'Отменен', 'Отменён'], true);
        $explicitCancellation = in_array($targetStatus, [143, 82657618], true);
        if (($terminal && !$explicitCancellation) || self::isStatusRegression($currentStatus, $targetStatus)) {
            $this->logger->warning($siteId, 'moysklad_order_status', $operation . '_regression_blocked', [
                'order_id' => $orderId, 'moysklad_order_id' => $moySkladOrderId,
                'current_state_href' => $currentHref, 'target_state_href' => $stateHref,
                'current_state' => (string)($currentState['name'] ?? ''),
            ]);
            return false;
        }

        $result = $this->moySkladApiClient->updateCustomerOrderState($siteId, $moySkladOrderId, $stateHref);
        if (!$result->isSuccess()) {
            $this->logger->error($siteId, 'moysklad_order_status', $operation . '_update_state_failed', [
                'order_id' => $orderId,
                'lead_id' => (string)($link['AMO_LEAD_ID'] ?? ''),
                'moysklad_order_id' => $moySkladOrderId,
                'state_href' => $stateHref,
                'message' => implode('; ', $result->getErrorMessages()),
            ]);
            return false;
        }

        $this->logger->info($siteId, 'moysklad_order_status', $operation . '_update_state_success', [
            'order_id' => $orderId,
            'lead_id' => (string)($link['AMO_LEAD_ID'] ?? ''),
            'moysklad_order_id' => $moySkladOrderId,
            'state_href' => $stateHref,
        ]);
        return true;
    }

    private static function isStatusRegression(int $current, int $target): bool
    {
        if (in_array($target, [143, 82657618], true)) {
            return false;
        }
        if (in_array($current, [143, 82657618], true)) {
            return true;
        }
        return isset(self::STATUS_PROGRESS[$current], self::STATUS_PROGRESS[$target])
            && self::STATUS_PROGRESS[$target] < self::STATUS_PROGRESS[$current];
    }

    public static function customerOrderBelongsToOrder(string $siteId, Order $order, array $remote): bool
    {
        $orderId = (int)$order->getId();
        $externalCode = trim((string)($remote['externalCode'] ?? ''));
        if ($externalCode === MoySkladExternalCode::buildOrderCode($siteId, $orderId)) {
            return true;
        }
        if (strpos($externalCode, 'bitrix-') === 0) {
            return false;
        }
        $expectedName = MoySkladExternalCode::buildOrderName($siteId, (string)$order->getField('ACCOUNT_NUMBER'), $orderId);
        return trim((string)($remote['name'] ?? '')) === $expectedName
            && preg_match('/Заказ Bitrix #' . $orderId . '(?![0-9])/u', (string)($remote['description'] ?? '')) === 1;
    }
}
