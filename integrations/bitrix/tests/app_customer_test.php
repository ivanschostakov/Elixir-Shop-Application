<?php

namespace Bitrix\Main {
    final class Application {
        public static $connection;
        public static function getConnection() { return self::$connection; }
    }
}

namespace {
    final class Result {
        private array $rows;
        public function __construct(array $rows) { $this->rows = $rows; }
        public function fetch() { return array_shift($this->rows) ?: false; }
    }
    final class FakeConnection {
        public array $users = [];
        public array $queries = [];
        public function getSqlHelper() { return $this; }
        public function forSql($value, $length = null) { return addslashes($value); }
        public function query($sql) {
            $this->queries[] = $sql;
            if (str_contains($sql, 'GET_LOCK')) { return new Result([['HELD' => 1]]); }
            if (str_contains($sql, 'RELEASE_LOCK')) { return new Result([['RELEASED' => 1]]); }
            return new Result($this->users);
        }
    }
    final class CUser {
        public static array $created = [];
        public function Add($fields) {
            self::$created[] = $fields;
            $id = count(self::$created) + 100;
            \Bitrix\Main\Application::$connection->users[] = ['ID' => $id, 'EMAIL' => $fields['EMAIL'],
                'ACTIVE' => $fields['ACTIVE'], 'XML_ID' => $fields['XML_ID']];
            return $id;
        }
    }
    function check($condition, $message) {
        if (!$condition) { throw new \RuntimeException($message); }
    }
    require dirname(__DIR__) . '/elixir.promo/lib/Service/AppCustomerService.php';
    $service = new \Elixir\Promo\Service\AppCustomerService();
    $payload = ['app_user_id' => 7, 'user_email' => 'customer@example.test', 'email_verified' => true,
        'name' => 'Test', 'last_name' => 'Customer'];
    $db = new FakeConnection();
    \Bitrix\Main\Application::$connection = $db;
    $first = $service->ensureCustomer($payload);
    $second = $service->ensureCustomer($payload);
    check($first['user_id'] === $second['user_id'] && $second['outcome'] === 'existing', 'Customer was duplicated');
    check(count(CUser::$created) === 1, 'Second call created another customer');
    check(CUser::$created[0]['GROUP_ID'] === [2], 'Unexpected user privileges');
    check(strlen(CUser::$created[0]['PASSWORD']) >= 64, 'Password entropy is insufficient');
    check(count(array_filter($db->queries, fn($sql) => str_contains($sql, 'RELEASE_LOCK'))) === 2, 'Locks were not released');
    foreach ([
        [['ID' => 2, 'EMAIL' => $payload['user_email'], 'ACTIVE' => 'N']],
        [['ID' => 2, 'EMAIL' => 'another@example.test', 'ACTIVE' => 'Y']],
        [['ID' => 2, 'EMAIL' => $payload['user_email'], 'ACTIVE' => 'Y'], ['ID' => 3, 'EMAIL' => $payload['user_email'], 'ACTIVE' => 'Y']],
    ] as $rows) {
        $db->users = $rows;
        try {
            $service->ensureCustomer($payload);
            throw new \RuntimeException('Conflicting identity accepted');
        } catch (\DomainException $expected) {}
    }
    try {
        $service->ensureCustomer(array_merge($payload, ['email_verified' => false]));
        throw new \RuntimeException('Unverified email accepted');
    } catch (\InvalidArgumentException $expected) {}
    check(count(CUser::$created) === 1, 'A rejected request created a customer');
    echo "App customer: repeat, privileges, lock release, ambiguity, inactive and unverified checks passed\n";
}
