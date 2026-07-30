<?php

use Bitrix\Main\Config\Option;
use Bitrix\Main\Context;
use Bitrix\Main\Loader;

defined('B_PROLOG_INCLUDED') || die();

$moduleId = 'elixir.catalogsync';
if (!Loader::includeModule($moduleId) || !$USER->IsAdmin()) {
    return;
}

$request = Context::getCurrent()->getRequest();
$message = null;
$error = null;

if ($request->isPost() && check_bitrix_sessid()) {
    try {
        $newSecret = trim((string)$request->getPost('shared_secret_new'));
        if ($newSecret !== '' && strlen($newSecret) < 32) {
            throw new RuntimeException('Секрет должен содержать не менее 32 символов.');
        }
        if ($newSecret !== '') {
            Option::set($moduleId, 'shared_secret', $newSecret);
        }
        Option::set($moduleId, 'enabled', $request->getPost('enabled') === 'Y' ? 'Y' : 'N');
        Option::set($moduleId, 'allowed_ips', trim((string)$request->getPost('allowed_ips')));
        Option::set($moduleId, 'rate_limit', (string)max(1, (int)$request->getPost('rate_limit')));
        Option::set(
            $moduleId,
            'rate_limit_window_seconds',
            (string)max(1, (int)$request->getPost('rate_limit_window_seconds'))
        );
        Option::set($moduleId, 'private_dir', rtrim(trim((string)$request->getPost('private_dir')), '/'));
        $message = 'Настройки синхронизации каталога сохранены.';
    } catch (Throwable $exception) {
        $error = $exception->getMessage();
    }
}

$isConfigured = strlen(trim(Option::get($moduleId, 'shared_secret', ''))) >= 32;
$get = static fn(string $name, string $default = ''): string => htmlspecialcharsbx(
    Option::get($moduleId, $name, $default)
);
?>
<?php if ($message !== null): ?>
    <div class="adm-info-message-wrap"><div class="adm-info-message"><?= htmlspecialcharsbx($message) ?></div></div>
<?php endif; ?>
<?php if ($error !== null): ?>
    <div class="adm-info-message-wrap"><div class="adm-info-message adm-info-message-red"><?= htmlspecialcharsbx($error) ?></div></div>
<?php endif; ?>

<form method="post" action="<?= $APPLICATION->GetCurPage() ?>?mid=<?= urlencode($moduleId) ?>&lang=<?= LANGUAGE_ID ?>">
    <?= bitrix_sessid_post() ?>
    <table class="adm-detail-content-table edit-table">
        <tr class="heading"><td colspan="2">Контент каталога Bitrix → приложение</td></tr>
        <tr><td width="40%">Синхронизация включена:</td><td><input type="checkbox" name="enabled" value="Y" <?= $get('enabled', 'N') === 'Y' ? 'checked' : '' ?>></td></tr>
        <tr><td>Состояние секрета:</td><td><?= $isConfigured ? 'Настроен' : 'Не настроен' ?></td></tr>
        <tr><td>Новый shared secret:</td><td><input type="password" name="shared_secret_new" size="60" autocomplete="new-password" placeholder="Пусто — оставить текущий"></td></tr>
        <tr><td>Инфоблок каталога:</td><td><?= $get('catalog_iblock_id', '21') ?></td></tr>
        <tr><td>Описание:</td><td><code>ELIXIR_APP_DESCRIPTION</code></td></tr>
        <tr><td>Применение:</td><td><code>ELIXIR_APP_USAGE</code></td></tr>
        <tr><td>Хранение:</td><td><code>ELIXIR_APP_STORAGE</code></td></tr>
        <tr><td>Разрешённые IP через запятую:</td><td><input type="text" name="allowed_ips" size="60" value="<?= $get('allowed_ips') ?>"></td></tr>
        <tr><td>Запросов за окно:</td><td><input type="number" name="rate_limit" min="1" value="<?= $get('rate_limit', '60') ?>"></td></tr>
        <tr><td>Окно ограничения, секунд:</td><td><input type="number" name="rate_limit_window_seconds" min="1" value="<?= $get('rate_limit_window_seconds', '60') ?>"></td></tr>
        <tr><td>Закрытый служебный каталог:</td><td><input type="text" name="private_dir" size="80" value="<?= $get('private_dir', dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-catalogsync') ?>"></td></tr>
    </table>
    <input type="submit" class="adm-btn-save" value="Сохранить">
</form>
