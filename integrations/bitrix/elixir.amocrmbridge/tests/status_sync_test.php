<?php
namespace SyncTest {
    class Result {
        public function __construct(private array $data = [], private bool $success = true) {}
        public function isSuccess(): bool { return $this->success; }
        public function getData(): array { return ['response' => $this->data]; }
        public function getErrorMessages(): array { return ['test failure']; }
    }
}
namespace Bitrix\Sale {
    class Order {
        public function getId(): int { return 7; }
        public function getField(string $field): string { return $field === 'ACCOUNT_NUMBER' ? '7' : 'P'; }
    }
}
namespace Elixir\AmoCrmBridge\Api {
    class AmoApiClient {
        public int $writes = 0;
        public int $status = 75784942;
        public function request(string $site, string $method, string $path, ?array $payload = null): \SyncTest\Result {
            if ($method !== 'GET') {
                $this->writes++;
                $this->status = (int)$payload[0]['status_id'];
            }
            return new \SyncTest\Result(['status_id' => $this->status]);
        }
    }
    class MoySkladApiClient {
        public int $writes = 0;
        public int $status = 142;
        public bool $available = true;
        public bool $missingState = false;
        public bool $foreign = false;
        public function getCustomerOrderFull(string $site, string $id, array $query): \SyncTest\Result {
            return new \SyncTest\Result(['name' => $this->foreign ? '01-8U0KR3' : '7',
                'externalCode' => $this->foreign ? 'foreign-code' : 'bitrix-s1-7',
                'state' => $this->missingState ? [] : [
                'meta' => ['href' => 'state/' . $this->status],
                'stateType' => $this->status === 142 ? 'Successful' : 'Regular',
            ]], $this->available);
        }
        public function updateCustomerOrderState(string $site, string $id, string $href): \SyncTest\Result {
            $this->writes++;
            $this->status = (int)substr($href, 6);
            return new \SyncTest\Result();
        }
    }
}
namespace Elixir\AmoCrmBridge\Repository {
    class OrderLinkRepository {
        public function getByOrderId(string $site, int $id): array {
            return ['MOYSKLAD_ORDER_ID' => 'ms-order', 'AMO_LEAD_ID' => '42'];
        }
        public function markSuccess(...$args): void {}
        public function markError(...$args): void {}
    }
    class StatusMapRepository {
        public int $target = 75784942;
        public function getByBitrixStatus(string $site, string $key): array {
            return ['MOYSKLAD_STATE_HREF' => 'state/' . $this->target, 'AMO_STATUS_ID' => $this->target];
        }
        public function getByMoySkladStateHref(string $site, string $href): array {
            return ['AMO_STATUS_ID' => (int)substr($href, 6)];
        }
    }
}
namespace Elixir\AmoCrmBridge\Logger {
    class BridgeLogger {
        public function info(...$args): void {}
        public function warning(...$args): void {}
        public function error(...$args): void {}
    }
}
namespace Elixir\AmoCrmBridge\Service {
    class MoySkladExternalCode {
        public static function buildOrderCode(string $site, int $id): string { return 'bitrix-' . $site . '-' . $id; }
        public static function buildOrderName(string $site, string $number, int $id): string { return $number; }
    }
}
namespace {
    require __DIR__ . '/../lib/Service/StatusSyncService.php';
    $cases = [
        [142, 75784942, 0], [76566306, 75784942, 0], [76566302, 75784942, 0],
        [75784942, 75784946, 0], [75784942, 76566302, 1],
        [142, 82657618, 1], [82657618, 75784942, 0], [75784942, 75784942, 0],
    ];
    foreach ($cases as [$current, $target, $expected]) {
        $amo = new \Elixir\AmoCrmBridge\Api\AmoApiClient();
        $ms = new \Elixir\AmoCrmBridge\Api\MoySkladApiClient();
        $map = new \Elixir\AmoCrmBridge\Repository\StatusMapRepository();
        $ms->status = $current;
        $amo->status = $current;
        $map->target = $target;
        $service = new \Elixir\AmoCrmBridge\Service\StatusSyncService($amo, $ms,
            new \Elixir\AmoCrmBridge\Repository\OrderLinkRepository(), $map,
            new \Elixir\AmoCrmBridge\Logger\BridgeLogger());
        for ($i = 0; $i < 3; $i++) {
            $service->syncOrderStatus(new \Bitrix\Sale\Order(), 's1');
            if ($ms->writes !== $expected || $amo->writes !== $expected) {
                throw new \RuntimeException("Unexpected writes for $current -> $target");
            }
        }
        $ms->available = false;
        $ms->writes = $amo->writes = 0;
        $service->syncOrderStatus(new \Bitrix\Sale\Order(), 's1');
        if ($ms->writes || $amo->writes) { throw new \RuntimeException('Write during state lookup outage'); }
        $ms->available = true;
        $ms->missingState = true;
        $service->syncOrderStatus(new \Bitrix\Sale\Order(), 's1');
        if ($ms->writes || $amo->writes) { throw new \RuntimeException('Write with missing current state'); }
        $ms->missingState = false;
        $ms->foreign = true;
        $service->syncOrderStatus(new \Bitrix\Sale\Order(), 's1');
        if ($ms->writes || $amo->writes) { throw new \RuntimeException('Write to another customer order'); }
    }
    echo "24 transition replays, 16 unavailable-state and 8 foreign-link checks passed\n";
}
