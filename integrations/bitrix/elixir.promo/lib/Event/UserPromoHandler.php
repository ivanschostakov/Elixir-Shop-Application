<?php

namespace Elixir\Promo\Event;

use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Elixir\Promo\Service\PromoService;

final class UserPromoHandler
{
    private const MODULE_ID = 'elixir.promo';

    public static function onAfterUserSave(array &$fields): void
    {
        if (($fields['RESULT'] ?? true) === false) {
            return;
        }
        if (Option::get(self::MODULE_ID, 'auto_create_enabled', 'N') !== 'Y') {
            return;
        }
        if (!Loader::includeModule(self::MODULE_ID)) {
            return;
        }

        $userId = (int)($fields['ID'] ?? 0);
        if ($userId <= 0) {
            return;
        }

        $promo = trim((string)($fields['UF_PROMO'] ?? ''));
        if ($promo === '') {
            $row = \CUser::GetByID($userId)->Fetch();
            $promo = trim((string)($row['UF_PROMO'] ?? ''));
        }
        if ($promo === '') {
            return;
        }

        try {
            (new PromoService())->ensureCouponForUser($userId, $promo);
        } catch (\Throwable $exception) {
            if (function_exists('AddMessage2Log')) {
                AddMessage2Log(
                    'Automatic promo creation failed for Bitrix user ID ' . $userId . ': ' . get_class($exception),
                    self::MODULE_ID
                );
            }
        }
    }
}
