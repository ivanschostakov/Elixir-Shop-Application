<?php

namespace Elixir\Promo\Service;

use Bitrix\Main\Application;

final class AppCustomerService
{
    public function ensureCustomer(array $payload): array
    {
        $email = mb_strtolower(trim((string)($payload['user_email'] ?? '')));
        $appUserId = filter_var($payload['app_user_id'] ?? null, FILTER_VALIDATE_INT);
        if (!$appUserId || $appUserId < 1 || !filter_var($email, FILTER_VALIDATE_EMAIL)
            || strlen($email) > 254 || ($payload['email_verified'] ?? false) !== true) {
            throw new \InvalidArgumentException('verified_customer_required');
        }
        $connection = Application::getConnection();
        $helper = $connection->getSqlHelper();
        $lock = $helper->forSql('elixir-customer-' . substr(hash('sha256', $email), 0, 40));
        $held = $connection->query("SELECT GET_LOCK('" . $lock . "', 10) AS HELD")->fetch();
        if ((int)($held['HELD'] ?? 0) !== 1) {
            throw new \RuntimeException('customer_sync_busy');
        }
        try {
            $xmlId = 'elixir-app-user:' . $appUserId;
            $emailSql = $helper->forSql($email, 254);
            $xmlSql = $helper->forSql($xmlId, 255);
            $rows = $connection->query(
                "SELECT ID, EMAIL, ACTIVE, XML_ID FROM b_user WHERE EMAIL='" . $emailSql
                . "' OR XML_ID='" . $xmlSql . "' ORDER BY ID ASC LIMIT 3"
            );
            $matches = [];
            while ($row = $rows->fetch()) {
                $matches[] = $row;
            }
            if (count($matches) > 1) {
                throw new \DomainException('customer_identity_ambiguous');
            }
            if ($matches !== []) {
                $row = $matches[0];
                if (mb_strtolower(trim((string)$row['EMAIL'])) !== $email) {
                    throw new \DomainException('customer_identity_conflict');
                }
                if ($row['ACTIVE'] !== 'Y') {
                    throw new \DomainException('customer_inactive');
                }
                return ['user_id' => (int)$row['ID'], 'outcome' => 'existing'];
            }
            $password = bin2hex(random_bytes(32)) . 'Aa1!';
            $api = new \CUser();
            $id = (int)$api->Add([
                'LOGIN' => 'app_' . substr(hash('sha256', $xmlId), 0, 36),
                'XML_ID' => $xmlId, 'EMAIL' => $email, 'ACTIVE' => 'Y',
                'NAME' => mb_substr(trim((string)($payload['name'] ?? '')), 0, 50),
                'LAST_NAME' => mb_substr(trim((string)($payload['last_name'] ?? '')), 0, 50),
                'PASSWORD' => $password, 'CONFIRM_PASSWORD' => $password,
                'GROUP_ID' => [2],
            ]);
            if ($id < 1) {
                throw new \RuntimeException('customer_create_failed');
            }
            return ['user_id' => $id, 'outcome' => 'created'];
        } finally {
            $connection->query("SELECT RELEASE_LOCK('" . $lock . "')");
        }
    }
}
