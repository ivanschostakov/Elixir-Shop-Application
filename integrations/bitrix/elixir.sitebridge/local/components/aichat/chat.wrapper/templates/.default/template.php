<?php if (!defined("B_PROLOG_INCLUDED") || B_PROLOG_INCLUDED !== true) die();
/** @var array $arParams */
/** @var array $arResult */

$rootId = 'ai-chat-wrapper-root';
$config = is_array($arResult['CHAT_CONFIG']) ? $arResult['CHAT_CONFIG'] : array();
$config['rootId'] = $rootId;
$config['signedParameters'] = isset($arResult['SIGNED_PARAMETERS']) ? (string)$arResult['SIGNED_PARAMETERS'] : '';
$styleVersion = file_exists($templateFolder . '/style.css') ? filemtime($templateFolder . '/style.css') : time();
$scriptVersion = file_exists($templateFolder . '/script.js') ? filemtime($templateFolder . '/script.js') : time();
?>
<link rel="stylesheet" href="<?= htmlspecialcharsbx($templateFolder) ?>/style.css?v=<?= (int)$styleVersion ?>">
<div id="<?= htmlspecialcharsbx($rootId) ?>" class="ai-chat-widget<?= !empty($config['isAuthorized']) ? '' : ' is-guest' ?>">
    <button type="button" class="ai-chat-widget__launcher" data-role="launcher" aria-expanded="false" aria-controls="<?= htmlspecialcharsbx($rootId) ?>-panel">
        <span class="ai-chat-widget__launcher-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
                <path d="M12 4C7.03 4 3 7.36 3 11.5c0 2.18 1.11 4.14 2.88 5.5V20l3.14-1.73c.63.15 1.29.23 1.98.23 4.97 0 9-3.36 9-7.5S16.97 4 12 4Zm-4 6h8v1.5H8Zm0 3h5v1.5H8Z" />
            </svg>
        </span>
        <span class="ai-chat-widget__launcher-badge" data-role="launcher-badge" hidden aria-hidden="true"></span>
        <span class="ai-chat-widget__launcher-label"><?= !empty($config['isAuthorized']) ? 'AI' : 'Вход' ?></span>
    </button>

    <button type="button" class="ai-chat-widget__backdrop" data-role="backdrop" hidden aria-label="Закрыть чат"></button>
    <section id="<?= htmlspecialcharsbx($rootId) ?>-panel" class="ai-chat-widget__panel" data-role="panel" hidden>
        <div class="ai-chat-widget__sheet-handle" aria-hidden="true"></div>
        <header class="ai-chat-widget__header">
            <div>
                <p class="ai-chat-widget__eyebrow">ElixirPeptide</p>
                <h3 class="ai-chat-widget__title">Персональный AI-чат</h3>
                <p class="ai-chat-widget__subtitle" data-role="subtitle">
                    <?= !empty($config['isAuthorized']) ? 'Чат учитывает ваш профиль, корзину и историю заказов.' : 'Авторизуйтесь, чтобы получить персональные рекомендации.' ?>
                </p>
            </div>
            <button type="button" class="ai-chat-widget__close" data-role="close" aria-label="Закрыть чат">&times;</button>
        </header>

        <div class="ai-chat-widget__history" data-role="history"></div>
        <div class="ai-chat-widget__empty" data-role="empty-state">
            <p>Спросите о текущей корзине, покупках, товарах или подборе следующего заказа.</p>
        </div>

        <footer class="ai-chat-widget__footer">
            <?php if (empty($config['isAuthorized'])): ?>
                <div class="ai-chat-widget__guest-note">Чат доступен только авторизованным пользователям сайта.</div>
            <?php else: ?>
                <label class="ai-chat-widget__input-wrap">
                    <textarea class="ai-chat-widget__textarea" data-role="textarea" rows="3" placeholder="Напишите ваш вопрос"></textarea>
                </label>
                <div class="ai-chat-widget__otp" data-role="otp" hidden>
                    <p class="ai-chat-widget__otp-text" data-role="otp-message">Введите код из SMS, чтобы отправить сообщение.</p>
                    <div class="ai-chat-widget__otp-row">
                        <input class="ai-chat-widget__otp-input" data-role="otp-input" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="000000">
                        <button type="button" class="ai-chat-widget__primary" data-role="otp-verify">Подтвердить</button>
                    </div>
                    <button type="button" class="ai-chat-widget__otp-resend" data-role="otp-resend">Отправить код повторно</button>
                </div>
                <div class="ai-chat-widget__actions">
                    <button type="button" class="ai-chat-widget__secondary" data-role="reset">Новый чат</button>
                    <button type="button" class="ai-chat-widget__primary" data-role="send">Отправить</button>
                </div>
            <?php endif; ?>
        </footer>
    </section>
</div>
<script src="<?= htmlspecialcharsbx($templateFolder) ?>/script.js?v=<?= (int)$scriptVersion ?>"></script>
<script>
BX.ready(function () {
    if (window.AIChatWrapper && typeof window.AIChatWrapper.init === 'function') {
        window.AIChatWrapper.init(<?= CUtil::PhpToJSObject($config) ?>);
    }
});
</script>
