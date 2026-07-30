<?php

defined('B_PROLOG_INCLUDED') || die();

\Bitrix\Main\Loader::registerAutoLoadClasses(
    'elixir.catalogsync',
    [
        \Elixir\CatalogSync\Service\CatalogContentService::class => 'lib/Service/CatalogContentService.php',
    ]
);
