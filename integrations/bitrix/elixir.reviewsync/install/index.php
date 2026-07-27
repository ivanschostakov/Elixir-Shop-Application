<?php

use Bitrix\Main\Localization\Loc;
use Bitrix\Main\ModuleManager;
use Bitrix\Main\SystemException;

Loc::loadMessages(__FILE__);

class elixir_reviewsync extends CModule
{
    public $MODULE_ID = 'elixir.reviewsync';
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
        $this->MODULE_VERSION_DATE = (string)($arModuleVersion['VERSION_DATE'] ?? '2026-07-27 00:00:00');
        $this->MODULE_NAME = Loc::getMessage('ELIXIR_REVIEWSYNC_MODULE_NAME');
        $this->MODULE_DESCRIPTION = Loc::getMessage('ELIXIR_REVIEWSYNC_MODULE_DESCRIPTION');
    }

    public function DoInstall()
    {
        if (!ModuleManager::isModuleInstalled('sotbit.reviews')) {
            throw new SystemException('Для установки требуется модуль sotbit.reviews.');
        }
        $this->InstallFiles();
        ModuleManager::registerModule($this->MODULE_ID);
    }

    public function DoUninstall()
    {
        ModuleManager::unRegisterModule($this->MODULE_ID);
        $this->UnInstallFiles();
    }

    public function InstallFiles()
    {
        $source = __DIR__ . '/tools';
        $destination = $_SERVER['DOCUMENT_ROOT'] . '/bitrix/tools/elixir.reviewsync';
        if (!is_dir($source)) {
            throw new SystemException('В дистрибутиве отсутствует API endpoint.');
        }
        CheckDirPath($destination . '/');
        CopyDirFiles($source, $destination, true, true);
        if (!is_file($destination . '/sync.php')) {
            throw new SystemException('Не удалось установить API endpoint синхронизации.');
        }
        return true;
    }

    public function UnInstallFiles()
    {
        DeleteDirFilesEx('/bitrix/tools/elixir.reviewsync');
        return true;
    }
}
