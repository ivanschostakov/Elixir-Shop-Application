<?php

use Bitrix\Main\Config\Option;
use Bitrix\Main\Loader;
use Bitrix\Main\Localization\Loc;
use Bitrix\Main\ModuleManager;
use Bitrix\Main\SystemException;

Loc::loadMessages(__FILE__);

class elixir_catalogsync extends CModule
{
    public const DESCRIPTION_PROPERTY = 'ELIXIR_APP_DESCRIPTION';
    public const USAGE_PROPERTY = 'ELIXIR_APP_USAGE';
    public const STORAGE_PROPERTY = 'ELIXIR_APP_STORAGE';
    public const SYSTEM_ID_PROPERTY = 'ELIXIR_APP_SYSTEM_ID';

    public $MODULE_ID = 'elixir.catalogsync';
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
        $this->MODULE_NAME = Loc::getMessage('ELIXIR_CATALOGSYNC_MODULE_NAME');
        $this->MODULE_DESCRIPTION = Loc::getMessage('ELIXIR_CATALOGSYNC_MODULE_DESCRIPTION');
    }

    public function DoInstall()
    {
        if (version_compare(PHP_VERSION, '8.1.0', '<')) {
            throw new SystemException('Для установки требуется PHP 8.1 или новее.');
        }
        if (!ModuleManager::isModuleInstalled('iblock')) {
            throw new SystemException('Для установки требуется модуль iblock.');
        }

        ModuleManager::registerModule($this->MODULE_ID);
        try {
            $this->InstallOptions();
            $this->InstallProperties();
            $this->InstallFiles();
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
        $destination = $_SERVER['DOCUMENT_ROOT'] . '/bitrix/tools/elixir.catalogsync';
        if (!is_dir($source)) {
            throw new SystemException('В дистрибутиве отсутствует API endpoint.');
        }
        CheckDirPath($destination . '/');
        CopyDirFiles($source, $destination, true, true);
        if (!is_file($destination . '/sync.php')) {
            throw new SystemException('Не удалось установить endpoint синхронизации каталога.');
        }
        return true;
    }

    public function UnInstallFiles()
    {
        DeleteDirFilesEx('/bitrix/tools/elixir.catalogsync');
        return true;
    }

    public function InstallProperties(): void
    {
        if (!Loader::includeModule('iblock')) {
            throw new SystemException('Модуль iblock недоступен.');
        }
        $iblockId = max(1, (int)Option::get($this->MODULE_ID, 'catalog_iblock_id', '21'));
        if (!\CIBlock::GetByID($iblockId)->Fetch()) {
            throw new SystemException('Инфоблок каталога не найден.');
        }

        $definitions = [
            self::SYSTEM_ID_PROPERTY => [
                'NAME' => 'ID товара приложения (служебное)',
                'SORT' => 890,
                'USER_TYPE' => '',
                'ROW_COUNT' => 1,
            ],
            self::DESCRIPTION_PROPERTY => [
                'NAME' => 'Описание для приложения',
                'SORT' => 900,
                'USER_TYPE' => 'HTML',
                'ROW_COUNT' => 12,
            ],
            self::USAGE_PROPERTY => [
                'NAME' => 'Применение для приложения',
                'SORT' => 910,
                'USER_TYPE' => 'HTML',
                'ROW_COUNT' => 12,
            ],
            self::STORAGE_PROPERTY => [
                'NAME' => 'Хранение для приложения',
                'SORT' => 920,
                'USER_TYPE' => 'HTML',
                'ROW_COUNT' => 12,
            ],
        ];
        foreach ($definitions as $code => $definition) {
            if (\CIBlockProperty::GetList([], ['IBLOCK_ID' => $iblockId, 'CODE' => $code])->Fetch()) {
                continue;
            }
            $property = new \CIBlockProperty();
            $propertyId = $property->Add([
                'IBLOCK_ID' => $iblockId,
                'ACTIVE' => 'Y',
                'SORT' => $definition['SORT'],
                'NAME' => $definition['NAME'],
                'CODE' => $code,
                'PROPERTY_TYPE' => 'S',
                'USER_TYPE' => $definition['USER_TYPE'],
                'MULTIPLE' => 'N',
                'ROW_COUNT' => $definition['ROW_COUNT'],
                'COL_COUNT' => 80,
            ]);
            if (!$propertyId) {
                throw new SystemException(
                    sprintf('Не удалось создать свойство %s: %s', $code, (string)$property->LAST_ERROR)
                );
            }
        }
    }

    private function InstallOptions(): void
    {
        $defaults = [
            'enabled' => 'N',
            'catalog_iblock_id' => '21',
            'allowed_ips' => '',
            'rate_limit' => '60',
            'rate_limit_window_seconds' => '60',
            'private_dir' => dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-catalogsync',
        ];
        foreach ($defaults as $name => $value) {
            if (Option::get($this->MODULE_ID, $name, '__ELIXIR_OPTION_NOT_SET__') === '__ELIXIR_OPTION_NOT_SET__') {
                Option::set($this->MODULE_ID, $name, $value);
            }
        }
    }
}
