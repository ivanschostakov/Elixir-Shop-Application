<?php

use Bitrix\Main\Config\Option;
use Bitrix\Main\Application;
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
$appPromoSummary = [
    'orders' => 0,
    'promos' => 0,
    'buyers' => 0,
    'amount' => 0.0,
];
$appPromoStats = [];
$appPartnerSummary = [
    'accruals' => 0,
    'pending_amount' => 0.0,
    'approved_amount' => 0.0,
    'rejected_amount' => 0.0,
];
$networkMonthlySummary = [
    'participants' => 0,
    'turnover' => 0.0,
    'amount' => 0.0,
];
$connection = Application::getConnection();
if ($connection->isTableExists('b_elixir_referral_app_purchase')) {
    $summaryRow = $connection->query(
        "SELECT
            COUNT(*) AS ORDERS,
            COUNT(DISTINCT NULLIF(PROMO, '')) AS PROMOS,
            COUNT(DISTINCT USER_ID) AS BUYERS,
            COALESCE(SUM(AMOUNT), 0) AS AMOUNT
         FROM b_elixir_referral_app_purchase
         WHERE SOURCE='app'"
    )->fetch();
    if (is_array($summaryRow)) {
        $appPromoSummary = [
            'orders' => (int)$summaryRow['ORDERS'],
            'promos' => (int)$summaryRow['PROMOS'],
            'buyers' => (int)$summaryRow['BUYERS'],
            'amount' => (float)$summaryRow['AMOUNT'],
        ];
    }

    $statsRows = $connection->query(
        "SELECT
            purchases.PROMO,
            COUNT(*) AS ORDERS,
            COUNT(DISTINCT purchases.USER_ID) AS BUYERS,
            COALESCE(SUM(purchases.AMOUNT), 0) AS AMOUNT,
            MAX(purchases.PAID_AT) AS LAST_PAID_AT,
            MAX(coupons.USE_COUNT) AS TOTAL_USE_COUNT
         FROM b_elixir_referral_app_purchase purchases
         LEFT JOIN b_sale_discount_coupon coupons
            ON LOWER(TRIM(coupons.COUPON))=LOWER(TRIM(purchases.PROMO))
         WHERE purchases.SOURCE='app' AND TRIM(purchases.PROMO)<>''
         GROUP BY purchases.PROMO
         ORDER BY AMOUNT DESC, ORDERS DESC
         LIMIT 200"
    );
    while ($statsRow = $statsRows->fetch()) {
        $appPromoStats[] = $statsRow;
    }
}
if ($connection->isTableExists('b_elixir_referral_partner_accrual')) {
    $partnerRow = $connection->query(
        "SELECT
            COUNT(*) AS ACCRUALS,
            COALESCE(SUM(CASE WHEN STATUS='pending' THEN COMMISSION_AMOUNT ELSE 0 END), 0) AS PENDING_AMOUNT,
            COALESCE(SUM(CASE WHEN STATUS='approved' THEN COMMISSION_AMOUNT ELSE 0 END), 0) AS APPROVED_AMOUNT,
            COALESCE(SUM(CASE WHEN STATUS='rejected' THEN COMMISSION_AMOUNT ELSE 0 END), 0) AS REJECTED_AMOUNT
         FROM b_elixir_referral_partner_accrual
         WHERE SOURCE='app'"
    )->fetch();
    if (is_array($partnerRow)) {
        $appPartnerSummary = [
            'accruals' => (int)$partnerRow['ACCRUALS'],
            'pending_amount' => (float)$partnerRow['PENDING_AMOUNT'],
            'approved_amount' => (float)$partnerRow['APPROVED_AMOUNT'],
            'rejected_amount' => (float)$partnerRow['REJECTED_AMOUNT'],
        ];
    }
}
if ($connection->isTableExists('b_elixir_partner_network_monthly')) {
    $networkRow = $connection->query(
        "SELECT
            COUNT(*) AS PARTICIPANTS,
            COALESCE(SUM(NETWORK_TURNOVER), 0) AS TURNOVER,
            COALESCE(SUM(AMOUNT), 0) AS AMOUNT
         FROM b_elixir_partner_network_monthly
         WHERE PERIOD='" . $connection->getSqlHelper()->forSql(date('Y-m'), 7) . "'"
    )->fetch();
    if (is_array($networkRow)) {
        $networkMonthlySummary = [
            'participants' => (int)$networkRow['PARTICIPANTS'],
            'turnover' => (float)$networkRow['TURNOVER'],
            'amount' => (float)$networkRow['AMOUNT'],
        ];
    }
}
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

<div class="adm-detail-content-wrap" style="margin-top: 24px;">
    <div class="adm-detail-content">
        <div class="adm-detail-title">Партнёрская программа: покупки из приложения</div>
        <div class="adm-detail-content-item-block">
            <p>
                Оплаченных заказов: <strong><?= $appPromoSummary['orders'] ?></strong>
                · Покупателей: <strong><?= $appPromoSummary['buyers'] ?></strong>
                · Сумма товаров без доставки: <strong><?= number_format($appPromoSummary['amount'], 2, ',', ' ') ?> ₽</strong>
            </p>
            <p style="color: #666;">
                Здесь учитываются только пользователи, выбравшие партнёрскую программу.
                Бонусная программа хранится в приложении и в Bitrix не записывается.
            </p>
        </div>
    </div>
</div>

<div class="adm-detail-content-wrap" style="margin-top: 24px;">
    <div class="adm-detail-content">
        <div class="adm-detail-title">Партнёрская программа: результаты приложения</div>
        <div class="adm-detail-content-item-block">
            <p>
                Начислений: <strong><?= $appPartnerSummary['accruals'] ?></strong>
                · Ожидают проверки: <strong><?= number_format($appPartnerSummary['pending_amount'], 2, ',', ' ') ?> ₽</strong>
                · Подтверждено: <strong><?= number_format($appPartnerSummary['approved_amount'], 2, ',', ' ') ?> ₽</strong>
                · Отклонено: <strong><?= number_format($appPartnerSummary['rejected_amount'], 2, ',', ' ') ?> ₽</strong>
            </p>
            <p style="color: #666;">
                Это отдельный журнал партнёрских начислений первого и второго уровней.
                Он не изменяет личную скидку и не смешивается с бонусным балансом МойСклад.
            </p>
            <p>
                Дополнительные 3–5% за <?= htmlspecialcharsbx(date('m.Y')) ?>:
                участников — <strong><?= $networkMonthlySummary['participants'] ?></strong>
                · оборот сети — <strong><?= number_format($networkMonthlySummary['turnover'], 2, ',', ' ') ?> ₽</strong>
                · расчётное начисление — <strong><?= number_format($networkMonthlySummary['amount'], 2, ',', ' ') ?> ₽</strong>
            </p>
            <h3>Применения партнёрских промокодов</h3>
            <?php if ($appPromoStats === []): ?>
                <div class="adm-info-message">
                    Оплаченных заказов приложения с промокодом пока нет.
                </div>
            <?php else: ?>
                <table class="adm-list-table" style="width: 100%;">
                    <thead>
                    <tr class="adm-list-table-header">
                        <td class="adm-list-table-cell"><div class="adm-list-table-cell-inner">Промокод</div></td>
                        <td class="adm-list-table-cell"><div class="adm-list-table-cell-inner">Заказы приложения</div></td>
                        <td class="adm-list-table-cell"><div class="adm-list-table-cell-inner">Покупатели</div></td>
                        <td class="adm-list-table-cell"><div class="adm-list-table-cell-inner">Сумма заказов</div></td>
                        <td class="adm-list-table-cell"><div class="adm-list-table-cell-inner">Всего применений Bitrix</div></td>
                        <td class="adm-list-table-cell"><div class="adm-list-table-cell-inner">Последняя оплата</div></td>
                    </tr>
                    </thead>
                    <tbody>
                    <?php foreach ($appPromoStats as $stat): ?>
                        <tr class="adm-list-table-row">
                            <td class="adm-list-table-cell"><?= htmlspecialcharsbx((string)$stat['PROMO']) ?></td>
                            <td class="adm-list-table-cell"><?= (int)$stat['ORDERS'] ?></td>
                            <td class="adm-list-table-cell"><?= (int)$stat['BUYERS'] ?></td>
                            <td class="adm-list-table-cell"><?= number_format((float)$stat['AMOUNT'], 2, ',', ' ') ?> ₽</td>
                            <td class="adm-list-table-cell"><?= (int)($stat['TOTAL_USE_COUNT'] ?? 0) ?></td>
                            <td class="adm-list-table-cell"><?= htmlspecialcharsbx((string)$stat['LAST_PAID_AT']) ?></td>
                        </tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
                <p style="color: #666;">
                    «Всего применений Bitrix» объединяет штатный счётчик сайта и оплаченные применения из приложения.
                </p>
            <?php endif; ?>
        </div>
    </div>
</div>
