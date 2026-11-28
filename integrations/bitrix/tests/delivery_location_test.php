<?php
declare(strict_types=1);

namespace Bitrix\Sale\Location {
    final class LocationTable {
        public static array $rows = [];
        public static function getById(int $id): object {
            return new class { public function fetch(): array { return ['CODE' => 'IPOL']; } };
        }
        public static function getList(array $params): object {
            if ($params['filter'] !== ['=EXTERNAL.SERVICE.CODE' => 'FIAS',
                '=EXTERNAL.XML_ID' => '00000000-0000-4000-8000-000000000011'] || $params['limit'] !== 2) {
                throw new \RuntimeException('Unsafe location lookup');
            }
            return new class { public function fetchAll(): array { return LocationTable::$rows; } };
        }
    }
}
namespace {
    use Bitrix\Sale\Location\LocationTable;
    use Elixir\Delivery\Service\DeliveryQuoteService;
    require __DIR__ . '/../elixir.delivery/lib/Service/DeliveryQuoteService.php';
    class sqlSdekCity {
        public static function getBySId(int $id): array { return $id === 1 ? ['BITRIX_ID' => 11] : []; }
    }
    $method = new ReflectionMethod(DeliveryQuoteService::class, 'resolveLocation');
    $service = new DeliveryQuoteService();
    $guid = '00000000-0000-4000-8000-000000000011';
    foreach ([[1, '', [], 'IPOL'], [2, $guid, [['CODE' => 'EXACT']], 'EXACT'],
        [2, $guid, [], null], [2, '', [], null], [2, $guid, [['CODE' => 'A'], ['CODE' => 'B']], null]] as [$id, $key, $rows, $expected]) {
        LocationTable::$rows = $rows;
        try {
            $actual = $method->invoke($service, $id, $key)['code'];
        } catch (DomainException $e) {
            if ($e->getMessage() !== 'destination_not_found') { throw $e; }
            $actual = null;
        }
        if ($expected !== $actual) { throw new RuntimeException('Unexpected delivery location'); }
    }
    echo "5 delivery location cases passed\n";
}
