<?php

use Bitrix\Main\Config\Option;
use Bitrix\Main\Context;
use Bitrix\Main\Loader;

defined('B_PROLOG_INCLUDED') || die();

$moduleId = 'elixir.promo';
if (!Loader::includeModule($moduleId) || !$USER->IsAdmin()) {
    return;
}

$request = Context::getCurrent()->getRequest();
$message = null;
$error = null;

if ($request->isPost() && check_bitrix_sessid()) {
    try {
        $enabled = $request->getPost('enabled') === 'Y' ? 'Y' : 'N';
        $autoCreateEnabled = $request->getPost('auto_create_enabled') === 'Y' ? 'Y' : 'N';
        $apiToken = trim((string)$request->getPost('api_token_new'));

        foreach (['api_token' => $apiToken] as $name => $token) {
            if ($token !== '' && strlen($token) < 32) {
                throw new RuntimeException('Секреты должны содержать не менее 32 символов.');
            }
            if ($token !== '') {
                Option::set($moduleId, $name, $token);
            }
        }

        Option::set($moduleId, 'enabled', $enabled);
        Option::set($moduleId, 'auto_create_enabled', $autoCreateEnabled);
        Option::set($moduleId, 'allowed_ips', trim((string)$request->getPost('allowed_ips')));
        Option::set($moduleId, 'discount_id', (string)max(1, (int)$request->getPost('discount_id')));
        Option::set($moduleId, 'catalog_iblock_id', (string)max(1, (int)$request->getPost('catalog_iblock_id')));
        Option::set($moduleId, 'offers_iblock_id', (string)max(1, (int)$request->getPost('offers_iblock_id')));
        Option::set($moduleId, 'site_id', trim((string)$request->getPost('site_id')) ?: 's1');
        Option::set($moduleId, 'person_type_id', (string)max(1, (int)$request->getPost('person_type_id')));
        Option::set($moduleId, 'currency', strtoupper(trim((string)$request->getPost('currency'))) ?: 'RUB');
        Option::set($moduleId, 'rate_limit', (string)max(1, (int)$request->getPost('rate_limit')));
        Option::set($moduleId, 'rate_limit_window_seconds', (string)max(1, (int)$request->getPost('rate_limit_window_seconds')));
        Option::set($moduleId, 'max_items', (string)max(1, min(500, (int)$request->getPost('max_items'))));
        Option::set($moduleId, 'private_dir', rtrim(trim((string)$request->getPost('private_dir')), '/'));
        $message = 'Настройки сохранены.';
    } catch (Throwable $exception) {
        $error = $exception->getMessage();
    }
}

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
        <tr class="heading"><td colspan="2">Основные настройки</td></tr>
        <tr>
            <td width="40%">Включить API проверки:</td>
            <td><input type="checkbox" name="enabled" value="Y" <?= Option::get($moduleId, 'enabled', 'N') === 'Y' ? 'checked' : '' ?>></td>
        </tr>
        <tr>
            <td>Автоматически создавать купон из UF_PROMO:</td>
            <td><input type="checkbox" name="auto_create_enabled" value="Y" <?= Option::get($moduleId, 'auto_create_enabled', 'N') === 'Y' ? 'checked' : '' ?>></td>
        </tr>
        <tr><td>Новый API token:</td><td><input type="password" name="api_token_new" size="60" autocomplete="new-password" placeholder="Пусто — оставить текущий"></td></tr>
        <tr><td>Разрешённые IP через запятую:</td><td><input type="text" name="allowed_ips" size="60" value="<?= $get('allowed_ips') ?>"></td></tr>
        <tr><td>ID правила скидки:</td><td><input type="number" name="discount_id" min="1" value="<?= $get('discount_id', '24') ?>"></td></tr>
        <tr><td>ID инфоблока товаров:</td><td><input type="number" name="catalog_iblock_id" min="1" value="<?= $get('catalog_iblock_id', '2') ?>"></td></tr>
        <tr><td>ID инфоблока предложений:</td><td><input type="number" name="offers_iblock_id" min="1" value="<?= $get('offers_iblock_id', '3') ?>"></td></tr>
        <tr><td>ID сайта:</td><td><input type="text" name="site_id" value="<?= $get('site_id', 's1') ?>"></td></tr>
        <tr><td>ID типа плательщика:</td><td><input type="number" name="person_type_id" min="1" value="<?= $get('person_type_id', '1') ?>"></td></tr>
        <tr><td>Валюта:</td><td><input type="text" name="currency" value="<?= $get('currency', 'RUB') ?>"></td></tr>
        <tr><td>Запросов за окно:</td><td><input type="number" name="rate_limit" min="1" value="<?= $get('rate_limit', '300') ?>"></td></tr>
        <tr><td>Окно rate limit, секунд:</td><td><input type="number" name="rate_limit_window_seconds" min="1" value="<?= $get('rate_limit_window_seconds', '60') ?>"></td></tr>
        <tr><td>Максимум позиций корзины:</td><td><input type="number" name="max_items" min="1" max="500" value="<?= $get('max_items', '100') ?>"></td></tr>
        <tr><td>Закрытый служебный каталог:</td><td><input type="text" name="private_dir" size="80" value="<?= $get('private_dir', dirname((string)$_SERVER['DOCUMENT_ROOT']) . '/private/elixir-promo') ?>"></td></tr>
    </table>
    <input type="submit" class="adm-btn-save" value="Сохранить">
</form>
