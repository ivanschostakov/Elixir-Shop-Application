<?php

defined('B_PROLOG_INCLUDED') || die();

\Bitrix\Main\Loader::registerAutoLoadClasses(
    'elixir.delivery',
    [
        \Elixir\Delivery\Service\DeliveryQuoteService::class => 'lib/Service/DeliveryQuoteService.php',
    ]
);
