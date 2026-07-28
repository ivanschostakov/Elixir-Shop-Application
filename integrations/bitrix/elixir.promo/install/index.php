<?php

use Bitrix\Main\Config\Option;
use Bitrix\Main\Application;
use Bitrix\Main\EventManager;
use Bitrix\Main\Localization\Loc;
use Bitrix\Main\ModuleManager;
use Bitrix\Main\SystemException;

Loc::loadMessages(__FILE__);

class elixir_promo extends CModule
{
    public $MODULE_ID = 'elixir.promo';
    public $MODULE_VERSION;
    public $MODULE_VERSION_DATE;
    public $MODULE_NAME;
    public $MODULE_DESCRIPTION;
    public $PARTNER_NAME = 'ElixirPeptide';
    public $PARTNER_URI = 'https://elixirpeptide.com/';

    public function __construct()
    {
        $arModuleVersion = [];
        include __DIR__ . '/version.php';
        $this->MODULE_VERSION = (string)($arModuleVersion['VERSION'] ?? '1.0.0');
        $this->MODULE_VERSION_DATE = (string)($arModuleVersion['VERSION_DATE'] ?? '2026-07-28 00:00:00');
        $this->MODULE_NAME = Loc::getMessage('ELIXIR_PROMO_MODULE_NAME');
        $this->MODULE_DESCRIPTION = Loc::getMessage('ELIXIR_PROMO_MODULE_DESCRIPTION');
    }

    public function DoInstall()
    {
        if (version_compare(PHP_VERSION, '8.1.0', '<')) {
            throw new SystemException('Для установки требуется PHP 8.1 или новее.');
        }
        foreach (['sale', 'catalog', 'iblock'] as $requiredModule) {
            if (!ModuleManager::isModuleInstalled($requiredModule)) {
                throw new SystemException(sprintf('Для установки требуется модуль %s.', $requiredModule));
            }
        }

        ModuleManager::registerModule($this->MODULE_ID);
        try {
            $this->InstallDB();
            $this->InstallFiles();
            $this->InstallEvents();
            $this->InstallOptions();
        } catch (\Throwable $exception) {
            $this->UnInstallEvents();
            $this->UnInstallFiles();
            ModuleManager::unRegisterModule($this->MODULE_ID);
            throw $exception;
        }
    }

    public function DoUninstall()
    {
        $this->UnInstallEvents();
        $this->UnInstallFiles();
        ModuleManager::unRegisterModule($this->MODULE_ID);
    }

    public function InstallFiles()
    {
        $source = __DIR__ . '/tools';
        $destination = $_SERVER['DOCUMENT_ROOT'] . '/bitrix/tools/elixir.promo';
        if (!is_dir($source)) {
            throw new SystemException('В дистрибутиве отсутствуют API endpoint.');
        }
        CheckDirPath($destination . '/');
        CopyDirFiles($source, $destination, true, true);
        foreach (['api.php'] as $fileName) {
            if (!is_file($destination . '/' . $fileName)) {
                throw new SystemException('Не удалось установить ' . $fileName . '.');
            }
        }
        return true;
    }

    public function UnInstallFiles()
    {
        DeleteDirFilesEx('/bitrix/tools/elixir.promo');
        return true;
    }

    public function InstallEvents()
    {
        $eventManager = EventManager::getInstance();
        foreach (['OnAfterUserAdd', 'OnAfterUserUpdate'] as $eventName) {
            $eventManager->registerEventHandlerCompatible(
                'main',
                $eventName,
                $this->MODULE_ID,
                \Elixir\Promo\Event\UserPromoHandler::class,
                'onAfterUserSave'
            );
        }
        return true;
    }

    public function UnInstallEvents()
    {
        $eventManager = EventManager::getInstance();
        foreach (['OnAfterUserAdd', 'OnAfterUserUpdate'] as $eventName) {
            $eventManager->unRegisterEventHandler(
                'main',
                $eventName,
                $this->MODULE_ID,
                \Elixir\Promo\Event\UserPromoHandler::class,
                'onAfterUserSave'
            );
        }
        CAgent::RemoveAgent(
            '\\Elixir\\Promo\\Service\\ReferralAccrualService::finalizePreviousMonthAgent();',
            $this->MODULE_ID
        );
        return true;
    }

    public function InstallDB()
    {
        $connection = Application::getConnection();
        $connection->queryExecute(
            "CREATE TABLE IF NOT EXISTS b_elixir_referral_app_purchase (
                ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                SOURCE VARCHAR(20) NOT NULL,
                EXTERNAL_ORDER_ID VARCHAR(100) NOT NULL,
                USER_ID INT NOT NULL,
                REFERRER_USER_ID INT NULL,
                PROMO VARCHAR(100) NOT NULL,
                AMOUNT DECIMAL(18,2) NOT NULL,
                CURRENCY CHAR(3) NOT NULL,
                PAID_AT DATETIME NOT NULL,
                PERIOD CHAR(7) NOT NULL,
                CREATED_AT DATETIME NOT NULL,
                PRIMARY KEY (ID),
                UNIQUE KEY UX_ELIXIR_REFERRAL_APP_ORDER (SOURCE, EXTERNAL_ORDER_ID),
                KEY IX_ELIXIR_REFERRAL_APP_USER (USER_ID, PAID_AT),
                KEY IX_ELIXIR_REFERRAL_APP_PERIOD (PERIOD)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
        );
        return true;
    }

    private function InstallOptions(): void
    {
        $defaults = [
            'enabled' => 'N',
            'auto_create_enabled' => 'N',
            'discount_id' => '24',
            'catalog_iblock_id' => '2',
            'offers_iblock_id' => '3',
            'site_id' => 's1',
            'person_type_id' => '1',
            'currency' => 'RUB',
            'allowed_ips' => '',
            'rate_limit' => '300',
            'rate_limit_window_seconds' => '60',
            'max_items' => '100',
            'private_dir' => dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-promo',
        ];
        foreach ($defaults as $name => $value) {
            if (Option::get($this->MODULE_ID, $name, '__ELIXIR_OPTION_NOT_SET__') === '__ELIXIR_OPTION_NOT_SET__') {
                Option::set($this->MODULE_ID, $name, $value);
            }
        }
    }
}
