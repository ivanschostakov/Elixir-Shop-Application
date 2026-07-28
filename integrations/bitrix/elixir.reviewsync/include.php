<?php

defined('B_PROLOG_INCLUDED') || die();

\Bitrix\Main\Loader::registerAutoLoadClasses(
    'elixir.reviewsync',
    [
        \Elixir\ReviewSync\Service\ReviewSyncService::class => 'lib/Service/ReviewSyncService.php',
    ]
);
