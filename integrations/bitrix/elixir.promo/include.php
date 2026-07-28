<?php

defined('B_PROLOG_INCLUDED') || die();

\Bitrix\Main\Loader::registerAutoLoadClasses(
    'elixir.promo',
    [
        \Elixir\Promo\Service\PromoService::class => 'lib/Service/PromoService.php',
        \Elixir\Promo\Service\SiteDiscountContext::class => 'lib/Service/SiteDiscountContext.php',
        \Elixir\Promo\Service\ReferralAccrualService::class => 'lib/Service/ReferralAccrualService.php',
        \Elixir\Promo\Event\UserPromoHandler::class => 'lib/Event/UserPromoHandler.php',
    ]
);
