<?php

use Bitrix\Main\Config\Option;
use Bitrix\Main\Localization\Loc;
use Bitrix\Main\ModuleManager;
use Bitrix\Main\SystemException;

Loc::loadMessages(__FILE__);

class elixir_delivery extends CModule
{
    public $MODULE_ID = 'elixir.delivery';
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
        $this->MODULE_VERSION_DATE = (string)($arModuleVersion['VERSION_DATE'] ?? '2026-07-30 00:00:00');
        $this->MODULE_NAME = Loc::getMessage('ELIXIR_DELIVERY_MODULE_NAME');
        $this->MODULE_DESCRIPTION = Loc::getMessage('ELIXIR_DELIVERY_MODULE_DESCRIPTION');
    }

    public function DoInstall()
    {
        if (version_compare(PHP_VERSION, '8.1.0', '<')) {
            throw new SystemException('Для установки требуется PHP 8.1 или новее.');
        }
        foreach (['sale', 'catalog', 'iblock', 'ipol.sdek'] as $requiredModule) {
            if (!ModuleManager::isModuleInstalled($requiredModule)) {
                throw new SystemException(sprintf('Для установки требуется модуль %s.', $requiredModule));
            }
        }

        ModuleManager::registerModule($this->MODULE_ID);
        try {
            $this->InstallFiles();
            $this->InstallOptions();
        } catch (\Throwable $exception) {
            $this->UnInstallFiles();
            ModuleManager::unRegisterModule($this->MODULE_ID);
            throw $exception;
        }
    }

    public function DoUninstall()
    {
        $this->UnInstallFiles();
        ModuleManager::unRegisterModule($this->MODULE_ID);
    }

    public function InstallFiles()
    {
        $source = __DIR__ . '/tools';
        $destination = $_SERVER['DOCUMENT_ROOT'] . '/bitrix/tools/elixir.delivery';
        if (!is_dir($source)) {
            throw new SystemException('В дистрибутиве отсутствует API endpoint.');
        }
        CheckDirPath($destination . '/');
        CopyDirFiles($source, $destination, true, true);
        if (!is_file($destination . '/quote.php')) {
            throw new SystemException('Не удалось установить endpoint расчёта доставки.');
        }
        return true;
    }

    public function UnInstallFiles()
    {
        DeleteDirFilesEx('/bitrix/tools/elixir.delivery');
        return true;
    }

    private function InstallOptions(): void
    {
        $defaults = [
            'enabled' => 'N',
            'allowed_ips' => '',
            'rate_limit' => '120',
            'rate_limit_window_seconds' => '60',
            'max_items' => '100',
            'private_dir' => dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-delivery',
            'site_id' => 's1',
            'person_type_id' => '1',
            'currency' => 'RUB',
            'pickup_service_code' => 'sdek:pickup',
            'courier_service_code' => 'sdek:courier',
            'app_only_product_xml_ids' => '',
        ];
        foreach ($defaults as $name => $value) {
            if (Option::get($this->MODULE_ID, $name, '__ELIXIR_OPTION_NOT_SET__') === '__ELIXIR_OPTION_NOT_SET__') {
                Option::set($this->MODULE_ID, $name, $value);
            }
        }
    }
}
