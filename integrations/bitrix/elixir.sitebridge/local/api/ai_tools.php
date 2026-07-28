<?php

require $_SERVER["DOCUMENT_ROOT"] . "/bitrix/modules/main/include/prolog_before.php";

header("Content-Type: application/json; charset=utf-8");
header("Cache-Control: no-store, max-age=0");

$aiToolsConfig = array();
$aiToolsConfigPath = __DIR__ . "/ai_tools.config.php";
if (file_exists($aiToolsConfigPath)) {
    $loadedConfig = include $aiToolsConfigPath;
    if (is_array($loadedConfig)) {
        $aiToolsConfig = $loadedConfig;
    }
}

if (!(bool)ai_tools_config("enabled", false)) {
    ai_tools_fail(503, "service_disabled", "AI tools gateway is disabled");
}

define("AI_TOOLS_CATALOG_IBLOCK_ID", (int)ai_tools_config("catalog_iblock_id", 2));
define("AI_TOOLS_OFFERS_IBLOCK_ID", (int)ai_tools_config("offers_iblock_id", 3));
define("AI_TOOLS_PRICE_GROUP_ID", (int)ai_tools_config("price_group_id", 1));
define("AI_TOOLS_DEFAULT_ORDERS_LIMIT", (int)ai_tools_config("default_orders_limit", 5));
define("AI_TOOLS_MAX_ORDERS_LIMIT", (int)ai_tools_config("max_orders_limit", 10));
define("AI_TOOLS_DEFAULT_SEARCH_LIMIT", (int)ai_tools_config("default_search_limit", 10));
define("AI_TOOLS_DEFAULT_CONTENT_LIMIT", (int)ai_tools_config("default_content_limit", 5));
define("AI_TOOLS_MAX_CONTENT_LIMIT", (int)ai_tools_config("max_content_limit", 10));
define("AI_TOOLS_MIN_AI_ORDER_TOTAL_RUB", (float)ai_tools_config("min_ai_order_total_rub", 9000.0));

if ($_SERVER["REQUEST_METHOD"] !== "POST") {
    ai_tools_fail(405, "method_not_allowed", "Only POST requests are allowed");
}

$maxBodyBytes = max(1024, min(2097152, (int)ai_tools_config("max_body_bytes", 1048576)));
$contentLength = isset($_SERVER["CONTENT_LENGTH"]) ? (int)$_SERVER["CONTENT_LENGTH"] : 0;
if ($contentLength > $maxBodyBytes) {
    ai_tools_fail(413, "payload_too_large", "Request body is too large");
}
$rawPayload = file_get_contents("php://input");
if (!is_string($rawPayload) || strlen($rawPayload) > $maxBodyBytes) {
    ai_tools_fail(413, "payload_too_large", "Request body is too large");
}
$payload = json_decode($rawPayload, true);

if (!is_array($payload)) {
    ai_tools_fail(400, "bad_json", "Request body must be valid JSON");
}

$token = isset($_SERVER["HTTP_X_AI_TOOLS_TOKEN"])
    ? trim((string)$_SERVER["HTTP_X_AI_TOOLS_TOKEN"])
    : "";
$allowLegacyBodyToken = (bool)ai_tools_config("allow_legacy_body_token", false);
if ($token === "" && $allowLegacyBodyToken) {
    $token = trim((string)($payload["token"] ?? ""));
}
$configuredToken = trim((string)ai_tools_config("token", ""));
$cmd = (string)($payload["cmd"] ?? "");
$args = $payload["args"] ?? array();

if (!is_array($args)) {
    $args = array();
}

if (strlen($configuredToken) < 32) {
    ai_tools_fail(503, "service_not_configured", "AI tools gateway is not configured");
}
if ($token === "" || !hash_equals($configuredToken, $token)) {
    ai_tools_fail(401, "unauthorized", "Invalid API token");
}

$remoteAddress = trim((string)($_SERVER["REMOTE_ADDR"] ?? ""));
$allowedIps = ai_tools_config("allowed_ips", array());
if (is_array($allowedIps) && $allowedIps !== array() && !in_array($remoteAddress, $allowedIps, true)) {
    ai_tools_fail(403, "forbidden", "Source address is not allowed");
}

global $DB;
$GLOBALS["AI_TOOLS_CONN"] = \Bitrix\Main\Application::getConnection();
$GLOBALS["AI_TOOLS_SQLH"] = $GLOBALS["AI_TOOLS_CONN"]->getSqlHelper();

try {
    switch ($cmd) {
        case "context.bootstrap":
            ai_tools_respond(ai_tools_context_bootstrap($args));
            break;

        case "user.profile":
            ai_tools_respond(ai_tools_get_user_profile(ai_tools_require_user_id($args)));
            break;

        case "cart.current":
            ai_tools_respond(ai_tools_get_current_cart(ai_tools_require_user_id($args)));
            break;

        case "cart.add":
            ai_tools_respond(
                ai_tools_add_to_cart(
                    ai_tools_require_user_id($args),
                    ai_tools_require_positive_int($args["offer_id"] ?? null, "offer_id"),
                    ai_tools_require_positive_int($args["quantity"] ?? 1, "quantity")
                )
            );
            break;

        case "orders.recent":
            ai_tools_respond(
                ai_tools_get_recent_orders(
                    ai_tools_require_user_id($args),
                    ai_tools_normalize_limit($args["limit"] ?? AI_TOOLS_DEFAULT_ORDERS_LIMIT, AI_TOOLS_DEFAULT_ORDERS_LIMIT, AI_TOOLS_MAX_ORDERS_LIMIT)
                )
            );
            break;

        case "orders.detail":
            ai_tools_respond(
                ai_tools_get_order_detail(
                    ai_tools_require_user_id($args),
                    ai_tools_require_positive_int($args["order_id"] ?? null, "order_id")
                )
            );
            break;

        case "catalog.current_product":
            ai_tools_respond(
                ai_tools_get_current_page_product(
                    ai_tools_require_user_id($args),
                    ai_tools_string($args["page_path"] ?? "")
                )
            );
            break;

        case "catalog.product":
            ai_tools_respond(
                ai_tools_get_product_details(
                    ai_tools_require_user_id($args),
                    isset($args["product_id"]) ? ai_tools_nullable_positive_int($args["product_id"]) : null,
                    isset($args["offer_id"]) ? ai_tools_nullable_positive_int($args["offer_id"]) : null
                )
            );
            break;

        case "catalog.search":
            ai_tools_respond(
                ai_tools_search_products(
                    ai_tools_require_user_id($args),
                    ai_tools_require_string($args["query"] ?? "", "query"),
                    ai_tools_normalize_limit($args["limit"] ?? AI_TOOLS_DEFAULT_SEARCH_LIMIT, AI_TOOLS_DEFAULT_SEARCH_LIMIT, AI_TOOLS_DEFAULT_SEARCH_LIMIT)
                )
            );
            break;

        case "catalog.list_all_products":
            ai_tools_respond(ai_tools_list_all_products(ai_tools_require_user_id($args)));
            break;

        case "catalog.list_all_offers":
            ai_tools_respond(ai_tools_list_all_offers(ai_tools_require_user_id($args)));
            break;

        case "content.search":
            ai_tools_respond(
                ai_tools_search_site_content(
                    ai_tools_require_user_id($args),
                    ai_tools_require_string($args["query"] ?? "", "query"),
                    ai_tools_normalize_limit($args["limit"] ?? AI_TOOLS_DEFAULT_CONTENT_LIMIT, AI_TOOLS_DEFAULT_CONTENT_LIMIT, AI_TOOLS_MAX_CONTENT_LIMIT)
                )
            );
            break;

        case "content.page":
            ai_tools_respond(
                ai_tools_get_site_page(
                    ai_tools_require_user_id($args),
                    ai_tools_require_string($args["path"] ?? "", "path")
                )
            );
            break;

        case "blog.search":
            ai_tools_respond(
                ai_tools_search_blog_articles(
                    ai_tools_require_user_id($args),
                    ai_tools_require_string($args["query"] ?? "", "query"),
                    ai_tools_normalize_limit($args["limit"] ?? AI_TOOLS_DEFAULT_CONTENT_LIMIT, AI_TOOLS_DEFAULT_CONTENT_LIMIT, AI_TOOLS_MAX_CONTENT_LIMIT)
                )
            );
            break;

        case "blog.article":
            ai_tools_respond(
                ai_tools_get_blog_article(
                    ai_tools_require_user_id($args),
                    isset($args["article_id"]) ? ai_tools_nullable_positive_int($args["article_id"]) : null,
                    ai_tools_string($args["code"] ?? "", 255)
                )
            );
            break;

        case "contacts.info":
            ai_tools_respond(ai_tools_get_contacts_info(ai_tools_require_user_id($args)));
            break;

        default:
            ai_tools_fail(422, "bad_cmd", "Unsupported command");
    }
} catch (\Throwable $exception) {
    AddMessage2Log(
        "AI tools gateway error: " . get_class($exception) . ": " . $exception->getMessage(),
        "elixir.ai"
    );
    ai_tools_fail(500, "internal_error", "Unable to process gateway request");
}

function ai_tools_respond($data, $status = 200)
{
    http_response_code($status);
    echo json_encode(array("ok" => true, "data" => $data), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function ai_tools_config($key, $default = null)
{
    global $aiToolsConfig;

    if (!is_array($aiToolsConfig) || !array_key_exists($key, $aiToolsConfig)) {
        return $default;
    }

    $value = $aiToolsConfig[$key];
    if ($value === null || $value === "") {
        return $default;
    }

    return $value;
}

function ai_tools_fail($status, $error, $message = "")
{
    $messagesRu = array(
        "service_disabled" => "AI-шлюз выключен.",
        "service_not_configured" => "AI-шлюз не настроен.",
        "method_not_allowed" => "Разрешены только POST-запросы.",
        "payload_too_large" => "Тело запроса слишком большое.",
        "bad_json" => "Тело запроса должно содержать корректный JSON.",
        "unauthorized" => "Неверный API-токен.",
        "forbidden" => "IP-адрес источника не разрешён.",
        "bad_cmd" => "Неизвестная команда.",
        "internal_error" => "Не удалось обработать запрос AI-шлюза.",
    );
    $messageRu = isset($messagesRu[$error]) ? $messagesRu[$error] : "Не удалось выполнить запрос.";
    http_response_code((int)$status);
    echo json_encode(
        array(
            "ok" => false,
            "error" => (string)$error,
            "message" => (string)$message,
            "message_ru" => $messageRu,
            "message_en" => (string)$message,
        ),
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
    );
    exit;
}

function ai_tools_conn()
{
    return $GLOBALS["AI_TOOLS_CONN"];
}

function ai_tools_sqlh()
{
    return $GLOBALS["AI_TOOLS_SQLH"];
}

function ai_tools_query_row($sql)
{
    $row = ai_tools_conn()->query($sql)->fetch();
    if (!is_array($row)) {
        return null;
    }
    return ai_tools_normalize_row($row);
}

function ai_tools_query_all($sql)
{
    $result = ai_tools_conn()->query($sql);
    $rows = array();
    while ($row = $result->fetch()) {
        $rows[] = ai_tools_normalize_row($row);
    }
    return $rows;
}

function ai_tools_normalize_row(array $row)
{
    foreach ($row as $key => $value) {
        if ($value instanceof \Bitrix\Main\Type\DateTime || $value instanceof \DateTimeInterface) {
            $row[$key] = $value->format(DATE_ATOM);
        } elseif (is_object($value) && method_exists($value, "__toString")) {
            $row[$key] = (string)$value;
        }
    }
    return $row;
}

function ai_tools_string($value, $maxLength = 1000)
{
    $value = trim((string)$value);
    if ($value === "") {
        return "";
    }

    if (function_exists("mb_substr") && function_exists("mb_strlen")) {
        if (mb_strlen($value, "UTF-8") > $maxLength) {
            return mb_substr($value, 0, $maxLength, "UTF-8");
        }
        return $value;
    }

    if (strlen($value) > $maxLength) {
        return substr($value, 0, $maxLength);
    }
    return $value;
}

function ai_tools_require_string($value, $fieldName)
{
    $value = ai_tools_string($value, 200);
    if ($value === "") {
        ai_tools_fail(422, "bad_" . $fieldName, "Field `" . $fieldName . "` is required");
    }
    return $value;
}

function ai_tools_require_positive_int($value, $fieldName)
{
    if (!is_numeric($value) || (int)$value <= 0) {
        ai_tools_fail(422, "bad_" . $fieldName, "Field `" . $fieldName . "` must be a positive integer");
    }
    return (int)$value;
}

function ai_tools_nullable_positive_int($value)
{
    if ($value === null || $value === "") {
        return null;
    }
    if (!is_numeric($value) || (int)$value <= 0) {
        return null;
    }
    return (int)$value;
}

function ai_tools_normalize_limit($value, $defaultValue, $maxValue)
{
    if (!is_numeric($value) || (int)$value <= 0) {
        return (int)$defaultValue;
    }
    $value = (int)$value;
    if ($value > $maxValue) {
        return (int)$maxValue;
    }
    return $value;
}

function ai_tools_require_user_id(array $args)
{
    return ai_tools_require_positive_int(isset($args["bitrix_user_id"]) ? $args["bitrix_user_id"] : null, "bitrix_user_id");
}

function ai_tools_escape($value)
{
    return ai_tools_sqlh()->forSql((string)$value);
}

function ai_tools_get_property_id($iblockId, $code)
{
    static $cache = array();
    $cacheKey = $iblockId . ":" . $code;
    if (isset($cache[$cacheKey])) {
        return $cache[$cacheKey];
    }

    $codeSql = ai_tools_escape($code);
    $row = ai_tools_query_row(
        "SELECT ID FROM b_iblock_property WHERE IBLOCK_ID=" . (int)$iblockId . " AND CODE='" . $codeSql . "' LIMIT 1"
    );
    $cache[$cacheKey] = $row ? (int)$row["ID"] : 0;
    return $cache[$cacheKey];
}

function ai_tools_load_user_row($userId)
{
    return ai_tools_query_row("SELECT * FROM b_user WHERE ID=" . (int)$userId . " LIMIT 1");
}

function ai_tools_load_user_custom_fields($userId)
{
    $row = ai_tools_query_row("SELECT * FROM b_uts_user WHERE VALUE_ID=" . (int)$userId . " LIMIT 1");
    if (!$row) {
        return array();
    }

    $customFields = array();
    foreach ($row as $key => $value) {
        if (strpos($key, "UF_") !== 0) {
            continue;
        }
        $value = ai_tools_string($value, 2000);
        if ($value === "") {
            continue;
        }
        $customFields[$key] = $value;
    }
    return $customFields;
}

function ai_tools_load_user_groups($userId)
{
    $rows = ai_tools_query_all(
        "SELECT g.ID, g.NAME
         FROM b_user_group ug
         INNER JOIN b_group g ON g.ID = ug.GROUP_ID
         WHERE ug.USER_ID=" . (int)$userId . "
         ORDER BY g.ID ASC"
    );

    $groupIds = array();
    $groupNames = array();
    foreach ($rows as $row) {
        $groupIds[] = (int)$row["ID"];
        $groupNames[] = ai_tools_string($row["NAME"], 255);
    }

    return array(
        "group_ids" => $groupIds,
        "group_names" => $groupNames,
    );
}

function ai_tools_get_user_profile($userId)
{
    $user = ai_tools_load_user_row($userId);
    if (!$user) {
        ai_tools_fail(404, "user_not_found", "User not found");
    }

    $groups = ai_tools_load_user_groups($userId);
    return array(
        "id" => $userId,
        "login" => ai_tools_string($user["LOGIN"], 120),
        "name" => ai_tools_string($user["NAME"], 120),
        "last_name" => ai_tools_string($user["LAST_NAME"], 120),
        "second_name" => ai_tools_string(isset($user["SECOND_NAME"]) ? $user["SECOND_NAME"] : "", 120),
        "email" => ai_tools_string($user["EMAIL"], 190),
        "personal_phone" => ai_tools_string(isset($user["PERSONAL_PHONE"]) ? $user["PERSONAL_PHONE"] : "", 80),
        "personal_mobile" => ai_tools_string(isset($user["PERSONAL_MOBILE"]) ? $user["PERSONAL_MOBILE"] : "", 80),
        "personal_city" => ai_tools_string(isset($user["PERSONAL_CITY"]) ? $user["PERSONAL_CITY"] : "", 120),
        "date_register" => isset($user["DATE_REGISTER"]) ? $user["DATE_REGISTER"] : null,
        "last_login" => isset($user["LAST_LOGIN"]) ? $user["LAST_LOGIN"] : null,
        "group_ids" => $groups["group_ids"],
        "group_names" => $groups["group_names"],
        "custom_fields" => ai_tools_load_user_custom_fields($userId),
    );
}

function ai_tools_get_latest_fuser_id($userId)
{
    $row = ai_tools_query_row(
        "SELECT ID
         FROM b_sale_fuser
         WHERE USER_ID=" . (int)$userId . "
         ORDER BY DATE_UPDATE DESC, ID DESC
         LIMIT 1"
    );
    return $row ? (int)$row["ID"] : 0;
}

function ai_tools_resolve_fuser_id($userId)
{
    $userId = (int)$userId;
    if ($userId <= 0) {
        return 0;
    }

    if (\Bitrix\Main\Loader::includeModule("sale")) {
        $fuserId = (int)\Bitrix\Sale\Fuser::getIdByUserId($userId);
        if ($fuserId > 0) {
            return $fuserId;
        }
    }

    return ai_tools_get_latest_fuser_id($userId);
}

function ai_tools_get_current_cart($userId)
{
    $fuserId = ai_tools_resolve_fuser_id($userId);
    if ($fuserId <= 0) {
        return array(
            "fuser_id" => null,
            "summary" => array("lines_count" => 0, "units_count" => 0.0, "total_price" => 0.0, "currency" => ""),
            "items" => array(),
        );
    }

    $rows = ai_tools_query_all(
        "SELECT
            ID AS basket_id,
            PRODUCT_ID AS product_id,
            NAME,
            DETAIL_PAGE_URL,
            QUANTITY,
            PRICE,
            CURRENCY
         FROM b_sale_basket
         WHERE FUSER_ID=" . $fuserId . "
           AND ORDER_ID IS NULL
           AND CAN_BUY='Y'
           AND DELAY='N'
         ORDER BY DATE_UPDATE DESC, ID DESC"
    );

    $items = array();
    $unitsCount = 0.0;
    $totalPrice = 0.0;
    $currency = "";

    foreach ($rows as $row) {
        $quantity = round((float)$row["QUANTITY"], 3);
        $price = round((float)$row["PRICE"], 2);
        $items[] = array(
            "basket_id" => (int)$row["basket_id"],
            "product_id" => (int)$row["product_id"],
            "name" => ai_tools_string($row["NAME"], 500),
            "detail_page_url" => ai_tools_string($row["DETAIL_PAGE_URL"], 1000),
            "quantity" => $quantity,
            "price" => $price,
            "currency" => ai_tools_string($row["CURRENCY"], 16),
        );
        $unitsCount += $quantity;
        $totalPrice += $quantity * $price;
        if ($currency === "" && ai_tools_string($row["CURRENCY"], 16) !== "") {
            $currency = ai_tools_string($row["CURRENCY"], 16);
        }
    }

    return array(
        "fuser_id" => $fuserId,
        "summary" => array(
            "lines_count" => count($items),
            "units_count" => round($unitsCount, 2),
            "total_price" => round($totalPrice, 2),
            "currency" => $currency,
        ),
        "items" => $items,
    );
}

function ai_tools_add_to_cart($userId, $offerId, $quantity)
{
    if (!\Bitrix\Main\Loader::includeModule("sale") || !\Bitrix\Main\Loader::includeModule("catalog")) {
        ai_tools_fail(500, "missing_modules", "Bitrix sale/catalog modules are not available");
    }

    $offerId = (int)$offerId;
    $quantity = max(1, (int)$quantity);
    $offer = ai_tools_load_element_row($offerId, AI_TOOLS_OFFERS_IBLOCK_ID);
    if (!$offer) {
        ai_tools_fail(404, "offer_not_found", "Offer not found");
    }

    $fuserId = ai_tools_resolve_fuser_id($userId);
    if ($fuserId <= 0) {
        ai_tools_fail(404, "fuser_not_found", "Could not resolve basket owner");
    }

    $siteId = defined("SITE_ID") && (string)SITE_ID !== "" ? (string)SITE_ID : "s1";
    $registry = \Bitrix\Sale\Registry::getInstance(\Bitrix\Sale\Registry::REGISTRY_TYPE_ORDER);
    $basketClassName = $registry->getBasketClassName();
    $basket = $basketClassName::loadItemsForFUser($fuserId, $siteId);

    $product = array(
        "PRODUCT_ID" => $offerId,
        "QUANTITY" => $quantity,
        "MODULE" => "catalog",
        "PRODUCT_PROVIDER_CLASS" => \Bitrix\Catalog\Product\Basket::getDefaultProviderName(),
    );

    $addResult = \Bitrix\Catalog\Product\Basket::addProductToBasket($basket, $product, array("SITE_ID" => $siteId), array("USE_MERGE" => "Y"));
    if (!$addResult->isSuccess()) {
        $messages = array();
        foreach ($addResult->getErrors() as $error) {
            $messages[] = trim((string)$error->getMessage());
        }
        ai_tools_fail(409, "cart_add_failed", implode("; ", array_filter($messages)));
    }

    $saveResult = $basket->save();
    if (!$saveResult->isSuccess()) {
        $messages = array();
        foreach ($saveResult->getErrors() as $error) {
            $messages[] = trim((string)$error->getMessage());
        }
        ai_tools_fail(409, "cart_save_failed", implode("; ", array_filter($messages)));
    }

    $basketItem = null;
    $addData = $addResult->getData();
    if (is_array($addData) && !empty($addData["BASKET_ITEM"]) && $addData["BASKET_ITEM"] instanceof \Bitrix\Sale\BasketItemBase) {
        $basketItem = $addData["BASKET_ITEM"];
    }

    return array(
        "added" => true,
        "offer_id" => $offerId,
        "product_id" => ai_tools_get_parent_product_id_for_offer($offerId) ?: null,
        "quantity_added" => $quantity,
        "basket_id" => $basketItem ? (int)$basketItem->getId() : null,
        "current_quantity" => $basketItem ? round((float)$basketItem->getQuantity(), 3) : null,
        "cart" => ai_tools_get_current_cart($userId),
    );
}

function ai_tools_get_orders_summary($userId)
{
    $row = ai_tools_query_row(
        "SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN CANCELED='Y' THEN 1 ELSE 0 END) AS canceled_orders,
            MAX(DATE_INSERT) AS last_order_at,
            COALESCE(SUM(PRICE), 0) AS total_spent,
            MAX(CURRENCY) AS currency
         FROM b_sale_order
         WHERE USER_ID=" . (int)$userId
    );

    if (!$row) {
        return array(
            "total_orders" => 0,
            "canceled_orders" => 0,
            "last_order_at" => null,
            "total_spent" => 0.0,
            "currency" => "",
        );
    }

    return array(
        "total_orders" => (int)$row["total_orders"],
        "canceled_orders" => (int)$row["canceled_orders"],
        "last_order_at" => isset($row["last_order_at"]) ? $row["last_order_at"] : null,
        "total_spent" => round((float)$row["total_spent"], 2),
        "currency" => ai_tools_string(isset($row["currency"]) ? $row["currency"] : "", 16),
    );
}

function ai_tools_get_recent_orders($userId, $limit)
{
    $orders = ai_tools_query_all(
        "SELECT
            o.ID,
            o.ACCOUNT_NUMBER,
            o.STATUS_ID,
            o.CANCELED,
            o.DATE_INSERT,
            o.PRICE,
            o.CURRENCY,
            o.PERSON_TYPE_ID,
            sl.NAME AS STATUS_NAME,
            pt.NAME AS PERSON_TYPE_NAME
         FROM b_sale_order o
         LEFT JOIN b_sale_status_lang sl ON sl.STATUS_ID = o.STATUS_ID AND sl.LID='ru'
         LEFT JOIN b_sale_person_type pt ON pt.ID = o.PERSON_TYPE_ID
         WHERE o.USER_ID=" . (int)$userId . "
         ORDER BY o.DATE_INSERT DESC, o.ID DESC
         LIMIT " . (int)$limit
    );

    $orderIds = array();
    foreach ($orders as $order) {
        $orderIds[] = (int)$order["ID"];
    }

    $itemsByOrder = ai_tools_load_order_items_map($orderIds);
    $normalizedOrders = array();

    foreach ($orders as $order) {
        $orderId = (int)$order["ID"];
        $items = isset($itemsByOrder[$orderId]) ? $itemsByOrder[$orderId] : array();
        $normalizedOrders[] = array(
            "order_id" => $orderId,
            "account_number" => ai_tools_string($order["ACCOUNT_NUMBER"], 64),
            "status_id" => ai_tools_string($order["STATUS_ID"], 16),
            "status_name" => ai_tools_string(isset($order["STATUS_NAME"]) ? $order["STATUS_NAME"] : "", 255),
            "person_type_name" => ai_tools_string(isset($order["PERSON_TYPE_NAME"]) ? $order["PERSON_TYPE_NAME"] : "", 255),
            "canceled" => isset($order["CANCELED"]) && $order["CANCELED"] === "Y",
            "date_insert" => isset($order["DATE_INSERT"]) ? $order["DATE_INSERT"] : null,
            "price" => round((float)$order["PRICE"], 2),
            "currency" => ai_tools_string($order["CURRENCY"], 16),
            "items_count" => count($items),
            "items" => $items,
        );
    }

    return array(
        "summary" => ai_tools_get_orders_summary($userId),
        "orders" => $normalizedOrders,
    );
}

function ai_tools_load_order_items_map(array $orderIds)
{
    $map = array();
    if (empty($orderIds)) {
        return $map;
    }

    $idsSql = implode(",", array_map("intval", $orderIds));
    $rows = ai_tools_query_all(
        "SELECT
            ORDER_ID,
            ID AS basket_id,
            PRODUCT_ID AS product_id,
            NAME,
            DETAIL_PAGE_URL,
            QUANTITY,
            PRICE,
            CURRENCY
         FROM b_sale_basket
         WHERE ORDER_ID IN (" . $idsSql . ")
         ORDER BY ORDER_ID DESC, ID ASC"
    );

    foreach ($rows as $row) {
        $orderId = (int)$row["ORDER_ID"];
        if (!isset($map[$orderId])) {
            $map[$orderId] = array();
        }
        $map[$orderId][] = array(
            "basket_id" => (int)$row["basket_id"],
            "product_id" => (int)$row["product_id"],
            "name" => ai_tools_string($row["NAME"], 500),
            "detail_page_url" => ai_tools_string($row["DETAIL_PAGE_URL"], 1000),
            "quantity" => round((float)$row["QUANTITY"], 3),
            "price" => round((float)$row["PRICE"], 2),
            "currency" => ai_tools_string($row["CURRENCY"], 16),
        );
    }

    return $map;
}

function ai_tools_get_order_detail($userId, $orderId)
{
    $order = ai_tools_query_row(
        "SELECT
            o.ID,
            o.USER_ID,
            o.ACCOUNT_NUMBER,
            o.STATUS_ID,
            o.CANCELED,
            o.DATE_INSERT,
            o.PRICE,
            o.CURRENCY,
            o.PERSON_TYPE_ID,
            sl.NAME AS STATUS_NAME,
            pt.NAME AS PERSON_TYPE_NAME
         FROM b_sale_order o
         LEFT JOIN b_sale_status_lang sl ON sl.STATUS_ID = o.STATUS_ID AND sl.LID='ru'
         LEFT JOIN b_sale_person_type pt ON pt.ID = o.PERSON_TYPE_ID
         WHERE o.ID=" . (int)$orderId . "
         LIMIT 1"
    );

    if (!$order) {
        ai_tools_fail(404, "order_not_found", "Order not found");
    }
    if ((int)$order["USER_ID"] !== (int)$userId) {
        ai_tools_fail(403, "order_forbidden", "Order does not belong to the user");
    }

    $itemsMap = ai_tools_load_order_items_map(array((int)$orderId));
    $props = ai_tools_query_all(
        "SELECT NAME, CODE, VALUE
         FROM b_sale_order_props_value
         WHERE ORDER_ID=" . (int)$orderId . "
         ORDER BY ID ASC"
    );

    $normalizedProps = array();
    foreach ($props as $prop) {
        $value = ai_tools_string(isset($prop["VALUE"]) ? $prop["VALUE"] : "", 1000);
        if ($value === "") {
            continue;
        }
        $normalizedProps[] = array(
            "name" => ai_tools_string($prop["NAME"], 255),
            "code" => ai_tools_string(isset($prop["CODE"]) ? $prop["CODE"] : "", 64),
            "value" => $value,
        );
    }

    return array(
        "order_id" => (int)$order["ID"],
        "account_number" => ai_tools_string($order["ACCOUNT_NUMBER"], 64),
        "status_id" => ai_tools_string($order["STATUS_ID"], 16),
        "status_name" => ai_tools_string(isset($order["STATUS_NAME"]) ? $order["STATUS_NAME"] : "", 255),
        "person_type_name" => ai_tools_string(isset($order["PERSON_TYPE_NAME"]) ? $order["PERSON_TYPE_NAME"] : "", 255),
        "canceled" => isset($order["CANCELED"]) && $order["CANCELED"] === "Y",
        "date_insert" => isset($order["DATE_INSERT"]) ? $order["DATE_INSERT"] : null,
        "price" => round((float)$order["PRICE"], 2),
        "currency" => ai_tools_string($order["CURRENCY"], 16),
        "items" => isset($itemsMap[(int)$orderId]) ? $itemsMap[(int)$orderId] : array(),
        "props" => $normalizedProps,
    );
}

function ai_tools_load_section_row($sectionId)
{
    static $cache = array();
    $sectionId = (int)$sectionId;
    if ($sectionId <= 0) {
        return null;
    }
    if (array_key_exists($sectionId, $cache)) {
        return $cache[$sectionId];
    }

    $cache[$sectionId] = ai_tools_query_row(
        "SELECT ID, IBLOCK_SECTION_ID, NAME, CODE
         FROM b_iblock_section
         WHERE ID=" . $sectionId . "
         LIMIT 1"
    );

    return $cache[$sectionId];
}

function ai_tools_build_section_code_path($sectionId)
{
    $codes = array();
    $visited = array();
    $currentId = (int)$sectionId;

    while ($currentId > 0 && !isset($visited[$currentId])) {
        $visited[$currentId] = true;
        $section = ai_tools_load_section_row($currentId);
        if (!$section) {
            break;
        }
        $code = ai_tools_string(isset($section["CODE"]) ? $section["CODE"] : "", 255);
        if ($code !== "") {
            array_unshift($codes, $code);
        }
        $currentId = isset($section["IBLOCK_SECTION_ID"]) ? (int)$section["IBLOCK_SECTION_ID"] : 0;
    }

    return implode("/", $codes);
}

function ai_tools_load_element_row($elementId, $iblockId = 0)
{
    static $cache = array();
    $cacheKey = ((int)$iblockId) . ":" . ((int)$elementId);
    if (array_key_exists($cacheKey, $cache)) {
        return $cache[$cacheKey];
    }

    $where = "ID=" . (int)$elementId;
    if ((int)$iblockId > 0) {
        $where .= " AND IBLOCK_ID=" . (int)$iblockId;
    }

    $cache[$cacheKey] = ai_tools_query_row(
        "SELECT ID, IBLOCK_ID, IBLOCK_SECTION_ID, NAME, CODE, PREVIEW_TEXT, DETAIL_TEXT, ACTIVE
         FROM b_iblock_element
         WHERE " . $where . "
         LIMIT 1"
    );

    return $cache[$cacheKey];
}

function ai_tools_get_parent_product_id_for_offer($offerId)
{
    static $cache = array();
    $offerId = (int)$offerId;
    if (isset($cache[$offerId])) {
        return $cache[$offerId];
    }

    $propertyId = ai_tools_get_property_id(AI_TOOLS_OFFERS_IBLOCK_ID, "CML2_LINK");
    if ($propertyId <= 0) {
        $cache[$offerId] = 0;
        return 0;
    }

    $row = ai_tools_query_row(
        "SELECT VALUE
         FROM b_iblock_element_property
         WHERE IBLOCK_ELEMENT_ID=" . $offerId . "
           AND IBLOCK_PROPERTY_ID=" . $propertyId . "
         LIMIT 1"
    );

    $cache[$offerId] = $row ? (int)$row["VALUE"] : 0;
    return $cache[$offerId];
}

function ai_tools_get_offer_ids_for_product($productId)
{
    static $cache = array();
    $productId = (int)$productId;
    if (isset($cache[$productId])) {
        return $cache[$productId];
    }

    $propertyId = ai_tools_get_property_id(AI_TOOLS_OFFERS_IBLOCK_ID, "CML2_LINK");
    if ($propertyId <= 0) {
        $cache[$productId] = array();
        return array();
    }

    $rows = ai_tools_query_all(
        "SELECT IBLOCK_ELEMENT_ID
         FROM b_iblock_element_property
         WHERE IBLOCK_PROPERTY_ID=" . $propertyId . "
           AND VALUE=" . $productId
    );

    $ids = array();
    foreach ($rows as $row) {
        $ids[] = (int)$row["IBLOCK_ELEMENT_ID"];
    }

    $cache[$productId] = $ids;
    return $ids;
}

function ai_tools_get_price_for_product_id($productId)
{
    $row = ai_tools_query_row(
        "SELECT PRICE, CURRENCY
         FROM b_catalog_price
         WHERE PRODUCT_ID=" . (int)$productId . "
           AND CATALOG_GROUP_ID=" . AI_TOOLS_PRICE_GROUP_ID . "
         ORDER BY ID ASC
         LIMIT 1"
    );
    if (!$row) {
        return null;
    }

    return array(
        "price" => round((float)$row["PRICE"], 2),
        "currency" => ai_tools_string($row["CURRENCY"], 16),
    );
}

function ai_tools_get_base_price_for_product($productId)
{
    $directPrice = ai_tools_get_price_for_product_id($productId);
    if ($directPrice) {
        return $directPrice;
    }

    $offerIds = ai_tools_get_offer_ids_for_product($productId);
    $best = null;
    foreach ($offerIds as $offerId) {
        $price = ai_tools_get_price_for_product_id($offerId);
        if (!$price) {
            continue;
        }
        if ($best === null || (float)$price["price"] < (float)$best["price"]) {
            $best = $price;
        }
    }

    return $best;
}

function ai_tools_get_catalog_availability($productId)
{
    $row = ai_tools_query_row(
        "SELECT AVAILABLE, QUANTITY
         FROM b_catalog_product
         WHERE ID=" . (int)$productId . "
         LIMIT 1"
    );
    if (!$row) {
        return array("available" => null, "quantity" => null);
    }

    return array(
        "available" => isset($row["AVAILABLE"]) ? $row["AVAILABLE"] === "Y" : null,
        "quantity" => isset($row["QUANTITY"]) ? round((float)$row["QUANTITY"], 3) : null,
    );
}

function ai_tools_build_product_url(array $productRow)
{
    $sectionCodePath = ai_tools_build_section_code_path(isset($productRow["IBLOCK_SECTION_ID"]) ? (int)$productRow["IBLOCK_SECTION_ID"] : 0);
    $productCode = ai_tools_string(isset($productRow["CODE"]) ? $productRow["CODE"] : "", 255);

    if ($productCode === "") {
        return null;
    }

    if ($sectionCodePath === "") {
        return "/catalog/" . $productCode . "/";
    }

    return "/catalog/" . $sectionCodePath . "/" . $productCode . "/";
}

function ai_tools_build_offer_url(array $offerRow, array $productRow)
{
    $productUrl = ai_tools_build_product_url($productRow);
    if (!$productUrl) {
        return null;
    }
    return rtrim($productUrl, "/") . "/" . (int)$offerRow["ID"] . "/";
}

function ai_tools_decode_html_property_value($value)
{
    if (!is_string($value) || $value === "") {
        return "";
    }

    $decoded = @unserialize($value);
    if (is_array($decoded) && isset($decoded["TEXT"])) {
        return (string)$decoded["TEXT"];
    }

    return $value;
}

function ai_tools_normalize_html_text($value)
{
    $value = ai_tools_decode_html_property_value((string)$value);
    if ($value === "") {
        return "";
    }

    $value = preg_replace("~<style\\b[^>]*>.*?</style>~is", " ", $value);
    $value = preg_replace("~<script\\b[^>]*>.*?</script>~is", " ", $value);
    $value = preg_replace("~<br\\s*/?>~i", "\n", $value);
    $value = preg_replace("~</p>~i", "\n\n", $value);
    $value = preg_replace("~</li>~i", "\n", $value);
    $value = strip_tags($value);
    $value = html_entity_decode($value, ENT_QUOTES | ENT_HTML5, "UTF-8");
    $value = preg_replace("/[ \t]+/", " ", $value);
    $value = preg_replace("/\n{3,}/", "\n\n", $value);

    return trim($value);
}

function ai_tools_load_element_properties($elementId, $iblockId)
{
    $rows = ai_tools_query_all(
        "SELECT
            ep.ID,
            p.CODE,
            p.NAME,
            p.PROPERTY_TYPE,
            p.MULTIPLE,
            p.USER_TYPE,
            p.LINK_IBLOCK_ID,
            ep.VALUE,
            ep.VALUE_ENUM,
            ep.DESCRIPTION,
            pe.VALUE AS ENUM_VALUE
         FROM b_iblock_property p
         LEFT JOIN b_iblock_element_property ep
           ON ep.IBLOCK_PROPERTY_ID = p.ID
          AND ep.IBLOCK_ELEMENT_ID = " . (int)$elementId . "
         LEFT JOIN b_iblock_property_enum pe
           ON pe.ID = ep.VALUE_ENUM
         WHERE p.IBLOCK_ID = " . (int)$iblockId . "
         ORDER BY p.SORT ASC, p.ID ASC, ep.ID ASC"
    );

    return $rows;
}

function ai_tools_should_skip_property($code)
{
    static $skip = null;
    if ($skip === null) {
        $skip = array_flip(
            array(
                "MORE_PHOTO",
                "FILES",
                "BLOG_POST_ID",
                "BLOG_COMMENTS_CNT",
                "vote_count",
                "vote_sum",
                "rating",
                "CML2_LINK",
                "CML2_ATTRIBUTES",
                "CML2_TRAITS",
                "CML2_TAXES",
                "CML2_BASE_UNIT",
                "CML2_BAR_CODE",
                "associated",
                "SOTBIT_MARKETPLACE_REVIEWS_RATING",
                "SOTBIT_REVIEWS_RATING",
            )
        );
    }
    return isset($skip[$code]);
}

function ai_tools_collect_characteristics($elementId, $iblockId)
{
    $rows = ai_tools_load_element_properties($elementId, $iblockId);
    $characteristics = array();
    $relatedIds = array();
    $article = "";
    $seen = array();

    foreach ($rows as $row) {
        $code = ai_tools_string(isset($row["CODE"]) ? $row["CODE"] : "", 100);
        if ($code === "") {
            continue;
        }

        $value = "";
        if (isset($row["PROPERTY_TYPE"]) && $row["PROPERTY_TYPE"] === "L") {
            $value = ai_tools_string(isset($row["ENUM_VALUE"]) ? $row["ENUM_VALUE"] : "", 1000);
        } else {
            $value = ai_tools_string(ai_tools_normalize_html_text(isset($row["VALUE"]) ? $row["VALUE"] : ""), 5000);
        }

        if ($code === "CML2_ARTICLE") {
            if ($value !== "") {
                $article = $value;
            }
            continue;
        }

        if ($code === "associated" && isset($row["VALUE"]) && is_numeric($row["VALUE"])) {
            $relatedIds[] = (int)$row["VALUE"];
            continue;
        }

        if (ai_tools_should_skip_property($code) || $value === "") {
            continue;
        }

        $fingerprint = $code . ":" . $value;
        if (isset($seen[$fingerprint])) {
            continue;
        }
        $seen[$fingerprint] = true;

        $characteristics[] = array(
            "code" => $code,
            "name" => ai_tools_string(isset($row["NAME"]) ? $row["NAME"] : $code, 255),
            "value" => $value,
        );
    }

    return array(
        "article" => $article,
        "characteristics" => $characteristics,
        "related_ids" => array_values(array_unique($relatedIds)),
    );
}

function ai_tools_load_related_products(array $productIds, $limit = 10)
{
    $items = array();
    foreach ($productIds as $productId) {
        if (count($items) >= $limit) {
            break;
        }
        $row = ai_tools_load_element_row((int)$productId, AI_TOOLS_CATALOG_IBLOCK_ID);
        if (!$row || (isset($row["ACTIVE"]) && $row["ACTIVE"] !== "Y")) {
            continue;
        }
        $items[] = ai_tools_build_product_compact($row);
    }
    return $items;
}

function ai_tools_build_product_compact(array $productRow)
{
    $sectionId = isset($productRow["IBLOCK_SECTION_ID"]) ? (int)$productRow["IBLOCK_SECTION_ID"] : 0;
    $section = ai_tools_load_section_row($sectionId);
    $properties = ai_tools_collect_characteristics((int)$productRow["ID"], AI_TOOLS_CATALOG_IBLOCK_ID);
    $price = ai_tools_get_base_price_for_product((int)$productRow["ID"]);

    return array(
        "product_id" => (int)$productRow["ID"],
        "name" => ai_tools_string($productRow["NAME"], 255),
        "code" => ai_tools_string(isset($productRow["CODE"]) ? $productRow["CODE"] : "", 255),
        "section_id" => $sectionId > 0 ? $sectionId : null,
        "section_name" => $section ? ai_tools_string($section["NAME"], 255) : null,
        "detail_page_url" => ai_tools_build_product_url($productRow),
        "article" => $properties["article"],
        "base_price" => $price ? $price["price"] : null,
        "currency" => $price ? $price["currency"] : null,
    );
}

function ai_tools_build_offer_compact(array $offerRow)
{
    $parentProductId = ai_tools_get_parent_product_id_for_offer((int)$offerRow["ID"]);
    $parentProduct = $parentProductId > 0 ? ai_tools_load_element_row($parentProductId, AI_TOOLS_CATALOG_IBLOCK_ID) : null;
    $offerProperties = ai_tools_collect_characteristics((int)$offerRow["ID"], AI_TOOLS_OFFERS_IBLOCK_ID);
    $price = ai_tools_get_price_for_product_id((int)$offerRow["ID"]);

    $characteristics = array();
    foreach ($offerProperties["characteristics"] as $characteristic) {
        if (in_array($characteristic["code"], array("OBEM", "OBYEM", "CML2_OBEM", "NALICHIE_KARTRIDZHA"), true)) {
            $characteristics[] = $characteristic;
        }
    }

    return array(
        "offer_id" => (int)$offerRow["ID"],
        "offer_name" => ai_tools_string($offerRow["NAME"], 255),
        "offer_code" => ai_tools_string(isset($offerRow["CODE"]) ? $offerRow["CODE"] : "", 255),
        "parent_product_id" => $parentProductId > 0 ? $parentProductId : null,
        "parent_product_name" => $parentProduct ? ai_tools_string($parentProduct["NAME"], 255) : null,
        "detail_page_url" => $parentProduct ? ai_tools_build_offer_url($offerRow, $parentProduct) : null,
        "offer_characteristics" => $characteristics,
        "base_price" => $price ? $price["price"] : null,
        "currency" => $price ? $price["currency"] : null,
    );
}

function ai_tools_get_product_details($userId, $productId = null, $offerId = null)
{
    $productId = $productId ? (int)$productId : 0;
    $offerId = $offerId ? (int)$offerId : 0;

    if ($offerId <= 0 && $productId <= 0) {
        ai_tools_fail(422, "missing_product_reference", "Either product_id or offer_id is required");
    }

    if ($offerId > 0 && $productId <= 0) {
        $productId = ai_tools_get_parent_product_id_for_offer($offerId);
    }

    $product = ai_tools_load_element_row($productId, AI_TOOLS_CATALOG_IBLOCK_ID);
    if (!$product) {
        ai_tools_fail(404, "product_not_found", "Product not found");
    }

    $offer = $offerId > 0 ? ai_tools_load_element_row($offerId, AI_TOOLS_OFFERS_IBLOCK_ID) : null;
    $productProperties = ai_tools_collect_characteristics($productId, AI_TOOLS_CATALOG_IBLOCK_ID);
    $offerProperties = $offer ? ai_tools_collect_characteristics($offerId, AI_TOOLS_OFFERS_IBLOCK_ID) : array(
        "article" => "",
        "characteristics" => array(),
        "related_ids" => array(),
    );

    $sectionId = isset($product["IBLOCK_SECTION_ID"]) ? (int)$product["IBLOCK_SECTION_ID"] : 0;
    $section = ai_tools_load_section_row($sectionId);
    $resolvedPrice = $offer ? ai_tools_get_price_for_product_id($offerId) : ai_tools_get_base_price_for_product($productId);
    if (!$resolvedPrice) {
        $resolvedPrice = ai_tools_get_base_price_for_product($productId);
    }

    $availabilityTargetId = $offer ? $offerId : $productId;
    $availability = ai_tools_get_catalog_availability($availabilityTargetId);

    return array(
        "product_id" => $productId,
        "offer_id" => $offer ? $offerId : null,
        "display_name" => $offer ? ai_tools_string($offer["NAME"], 255) : ai_tools_string($product["NAME"], 255),
        "parent_product_name" => ai_tools_string($product["NAME"], 255),
        "offer_name" => $offer ? ai_tools_string($offer["NAME"], 255) : null,
        "product_code" => ai_tools_string(isset($product["CODE"]) ? $product["CODE"] : "", 255),
        "offer_code" => $offer ? ai_tools_string(isset($offer["CODE"]) ? $offer["CODE"] : "", 255) : null,
        "article" => $offerProperties["article"] !== "" ? $offerProperties["article"] : $productProperties["article"],
        "detail_page_url" => $offer ? ai_tools_build_offer_url($offer, $product) : ai_tools_build_product_url($product),
        "section" => array(
            "id" => $sectionId > 0 ? $sectionId : null,
            "name" => $section ? ai_tools_string($section["NAME"], 255) : null,
            "code_path" => $sectionId > 0 ? ai_tools_build_section_code_path($sectionId) : null,
        ),
        "base_price" => $resolvedPrice ? $resolvedPrice["price"] : null,
        "currency" => $resolvedPrice ? $resolvedPrice["currency"] : null,
        "available" => $availability["available"],
        "available_quantity" => $availability["quantity"],
        "preview_text" => ai_tools_string(ai_tools_normalize_html_text(isset($product["PREVIEW_TEXT"]) ? $product["PREVIEW_TEXT"] : ""), 6000),
        "detail_text" => ai_tools_string(ai_tools_normalize_html_text(isset($product["DETAIL_TEXT"]) ? $product["DETAIL_TEXT"] : ""), 20000),
        "characteristics" => array_merge($offerProperties["characteristics"], $productProperties["characteristics"]),
        "related_products" => ai_tools_load_related_products($productProperties["related_ids"], 10),
    );
}

function ai_tools_resolve_page_product($pagePath)
{
    $pagePath = trim((string)$pagePath);
    if ($pagePath === "") {
        return array("product_id" => null, "offer_id" => null);
    }

    $path = trim(parse_url($pagePath, PHP_URL_PATH), "/");
    if ($path === "") {
        return array("product_id" => null, "offer_id" => null);
    }

    $segments = array_values(array_filter(explode("/", $path), "strlen"));
    if (empty($segments) || $segments[0] !== "catalog") {
        return array("product_id" => null, "offer_id" => null);
    }

    $lastSegment = $segments[count($segments) - 1];
    if (ctype_digit($lastSegment)) {
        $offerId = (int)$lastSegment;
        $offer = ai_tools_load_element_row($offerId, AI_TOOLS_OFFERS_IBLOCK_ID);
        if ($offer && (!isset($offer["ACTIVE"]) || $offer["ACTIVE"] === "Y")) {
            return array(
                "offer_id" => $offerId,
                "product_id" => ai_tools_get_parent_product_id_for_offer($offerId),
            );
        }
    }

    $productCode = ai_tools_escape($lastSegment);
    $product = ai_tools_query_row(
        "SELECT ID
         FROM b_iblock_element
         WHERE IBLOCK_ID=" . AI_TOOLS_CATALOG_IBLOCK_ID . "
           AND ACTIVE='Y'
           AND CODE='" . $productCode . "'
         LIMIT 1"
    );

    return array(
        "product_id" => $product ? (int)$product["ID"] : null,
        "offer_id" => null,
    );
}

function ai_tools_get_current_page_product($userId, $pagePath)
{
    $resolved = ai_tools_resolve_page_product($pagePath);
    if (empty($resolved["product_id"]) && empty($resolved["offer_id"])) {
        return array(
            "resolved" => false,
            "page_path" => ai_tools_string($pagePath, 500),
            "product" => null,
        );
    }

    return array(
        "resolved" => true,
        "page_path" => ai_tools_string($pagePath, 500),
        "product" => ai_tools_get_product_details($userId, isset($resolved["product_id"]) ? (int)$resolved["product_id"] : null, isset($resolved["offer_id"]) ? (int)$resolved["offer_id"] : null),
    );
}

function ai_tools_get_active_products_rows()
{
    return ai_tools_query_all(
        "SELECT ID, IBLOCK_SECTION_ID, NAME, CODE, PREVIEW_TEXT, DETAIL_TEXT, ACTIVE
         FROM b_iblock_element
         WHERE IBLOCK_ID=" . AI_TOOLS_CATALOG_IBLOCK_ID . "
           AND ACTIVE='Y'
         ORDER BY NAME ASC, ID ASC"
    );
}

function ai_tools_get_active_offers_rows()
{
    return ai_tools_query_all(
        "SELECT ID, NAME, CODE, ACTIVE
         FROM b_iblock_element
         WHERE IBLOCK_ID=" . AI_TOOLS_OFFERS_IBLOCK_ID . "
           AND ACTIVE='Y'
         ORDER BY NAME ASC, ID ASC"
    );
}

function ai_tools_list_all_products($userId)
{
    $rows = ai_tools_get_active_products_rows();
    $items = array();
    foreach ($rows as $row) {
        $items[] = ai_tools_build_product_compact($row);
    }

    return array(
        "count" => count($items),
        "items" => $items,
    );
}

function ai_tools_list_all_offers($userId)
{
    $rows = ai_tools_get_active_offers_rows();
    $items = array();
    foreach ($rows as $row) {
        $items[] = ai_tools_build_offer_compact($row);
    }

    return array(
        "count" => count($items),
        "items" => $items,
    );
}

function ai_tools_search_products($userId, $query, $limit)
{
    $needle = function_exists("mb_strtolower") ? mb_strtolower($query, "UTF-8") : strtolower($query);
    $items = array();

    foreach (ai_tools_get_active_products_rows() as $row) {
        if (count($items) >= $limit) {
            break;
        }
        $compact = ai_tools_build_product_compact($row);
        $haystack = implode(
            " ",
            array(
                function_exists("mb_strtolower") ? mb_strtolower($compact["name"], "UTF-8") : strtolower($compact["name"]),
                function_exists("mb_strtolower") ? mb_strtolower($compact["code"], "UTF-8") : strtolower($compact["code"]),
                function_exists("mb_strtolower") ? mb_strtolower((string)$compact["article"], "UTF-8") : strtolower((string)$compact["article"]),
            )
        );
        if (strpos($haystack, $needle) !== false) {
            $compact["entity_type"] = "product";
            $items[] = $compact;
        }
    }

    foreach (ai_tools_get_active_offers_rows() as $row) {
        if (count($items) >= $limit) {
            break;
        }
        $compact = ai_tools_build_offer_compact($row);
        $offerCharacteristicText = "";
        foreach ($compact["offer_characteristics"] as $characteristic) {
            $offerCharacteristicText .= " " . (string)$characteristic["value"];
        }
        $haystack = implode(
            " ",
            array(
                function_exists("mb_strtolower") ? mb_strtolower($compact["offer_name"], "UTF-8") : strtolower($compact["offer_name"]),
                function_exists("mb_strtolower") ? mb_strtolower($compact["offer_code"], "UTF-8") : strtolower($compact["offer_code"]),
                function_exists("mb_strtolower") ? mb_strtolower((string)$compact["parent_product_name"], "UTF-8") : strtolower((string)$compact["parent_product_name"]),
                function_exists("mb_strtolower") ? mb_strtolower($offerCharacteristicText, "UTF-8") : strtolower($offerCharacteristicText),
            )
        );
        if (strpos($haystack, $needle) !== false) {
            $compact["entity_type"] = "offer";
            $items[] = $compact;
        }
    }

    return array(
        "query" => $query,
        "count" => count($items),
        "items" => $items,
    );
}

function ai_tools_mb_lower($value)
{
    $value = (string)$value;
    return function_exists("mb_strtolower") ? mb_strtolower($value, "UTF-8") : strtolower($value);
}

function ai_tools_dedupe_paragraphs($text)
{
    $paragraphs = preg_split("/\n{2,}/", (string)$text);
    $result = array();
    $seen = array();

    foreach ((array)$paragraphs as $paragraph) {
        $paragraph = trim((string)$paragraph);
        if ($paragraph === "") {
            continue;
        }

        $fingerprint = ai_tools_mb_lower(preg_replace("/\s+/u", " ", $paragraph));
        if (isset($seen[$fingerprint])) {
            continue;
        }
        $seen[$fingerprint] = true;
        $result[] = $paragraph;
    }

    return implode("\n\n", $result);
}

function ai_tools_build_snippet($text, $query, $limit = 280)
{
    $text = trim((string)$text);
    if ($text === "") {
        return "";
    }

    $needle = ai_tools_mb_lower($query);
    $haystack = ai_tools_mb_lower($text);
    $position = $needle !== "" ? strpos($haystack, $needle) : false;

    if ($position === false || strlen($text) <= $limit) {
        return ai_tools_string($text, $limit);
    }

    $start = max(0, $position - (int)($limit / 3));
    $snippet = trim(substr($text, $start, $limit));
    if ($start > 0) {
        $snippet = "…" . ltrim($snippet);
    }
    if (($start + $limit) < strlen($text)) {
        $snippet = rtrim($snippet) . "…";
    }

    return ai_tools_string($snippet, $limit + 2);
}

function ai_tools_search_score($query, $title, $text, $path = "", $code = "")
{
    $query = trim((string)$query);
    if ($query === "") {
        return 0;
    }

    $queryLower = ai_tools_mb_lower($query);
    $titleLower = ai_tools_mb_lower($title);
    $textLower = ai_tools_mb_lower($text);
    $pathLower = ai_tools_mb_lower($path);
    $codeLower = ai_tools_mb_lower($code);
    $score = 0;

    if ($titleLower !== "" && strpos($titleLower, $queryLower) !== false) {
        $score += 120;
    }
    if ($codeLower !== "" && strpos($codeLower, $queryLower) !== false) {
        $score += 90;
    }
    if ($pathLower !== "" && strpos($pathLower, $queryLower) !== false) {
        $score += 70;
    }
    if ($textLower !== "" && strpos($textLower, $queryLower) !== false) {
        $score += 40;
    }

    $terms = preg_split("/\s+/u", $queryLower, -1, PREG_SPLIT_NO_EMPTY);
    foreach ((array)$terms as $term) {
        if (strlen($term) < 2) {
            continue;
        }
        if ($titleLower !== "" && strpos($titleLower, $term) !== false) {
            $score += 20;
        } elseif ($pathLower !== "" && strpos($pathLower, $term) !== false) {
            $score += 12;
        } elseif ($textLower !== "" && strpos($textLower, $term) !== false) {
            $score += 8;
        }
    }

    return $score;
}

function ai_tools_get_blog_iblock_id()
{
    static $blogIblockId = null;
    if ($blogIblockId !== null) {
        return $blogIblockId;
    }

    $blogIblockId = 0;
    if (\Bitrix\Main\Loader::includeModule("sotbit.b2c") && class_exists("\\Sotbit\\B2C\\Helper\\Config")) {
        $configured = (int)\Sotbit\B2C\Helper\Config::get("BLOG_IBLOCK_ID");
        if ($configured > 0) {
            $blogIblockId = $configured;
        }
    }

    if ($blogIblockId <= 0) {
        $row = ai_tools_query_row(
            "SELECT ID
             FROM b_iblock
             WHERE CODE='sotbit_b2c_blog'
             ORDER BY ID ASC
             LIMIT 1"
        );
        if ($row) {
            $blogIblockId = (int)$row["ID"];
        }
    }

    if ($blogIblockId <= 0) {
        $blogIblockId = 6;
    }

    return $blogIblockId;
}

function ai_tools_get_blog_articles_rows()
{
    static $cache = null;
    if ($cache !== null) {
        return $cache;
    }

    $cache = ai_tools_query_all(
        "SELECT ID, IBLOCK_SECTION_ID, NAME, CODE, PREVIEW_TEXT, DETAIL_TEXT, ACTIVE_FROM, TIMESTAMP_X, ACTIVE
         FROM b_iblock_element
         WHERE IBLOCK_ID=" . ai_tools_get_blog_iblock_id() . "
           AND ACTIVE='Y'
         ORDER BY COALESCE(ACTIVE_FROM, TIMESTAMP_X) DESC, ID DESC"
    );

    return $cache;
}

function ai_tools_build_blog_article_url(array $row)
{
    $code = ai_tools_string(isset($row["CODE"]) ? $row["CODE"] : "", 255);
    if ($code === "") {
        return null;
    }

    $sectionPath = ai_tools_build_section_code_path(isset($row["IBLOCK_SECTION_ID"]) ? (int)$row["IBLOCK_SECTION_ID"] : 0);
    return "/articles/" . ($sectionPath !== "" ? $sectionPath . "/" : "") . $code . "/";
}

function ai_tools_build_blog_article_compact(array $row, $query = "")
{
    $previewText = ai_tools_string(ai_tools_normalize_html_text(isset($row["PREVIEW_TEXT"]) ? $row["PREVIEW_TEXT"] : ""), 2000);
    $detailText = ai_tools_string(ai_tools_normalize_html_text(isset($row["DETAIL_TEXT"]) ? $row["DETAIL_TEXT"] : ""), 4000);
    $baseText = $previewText !== "" ? $previewText : $detailText;

    return array(
        "content_type" => "blog_article",
        "article_id" => (int)$row["ID"],
        "title" => ai_tools_string(isset($row["NAME"]) ? $row["NAME"] : "", 255),
        "code" => ai_tools_string(isset($row["CODE"]) ? $row["CODE"] : "", 255),
        "path" => ai_tools_build_blog_article_url($row),
        "preview_text" => $previewText,
        "snippet" => ai_tools_build_snippet($baseText, $query, 280),
        "published_at" => isset($row["ACTIVE_FROM"]) && $row["ACTIVE_FROM"] ? $row["ACTIVE_FROM"] : (isset($row["TIMESTAMP_X"]) ? $row["TIMESTAMP_X"] : null),
    );
}

function ai_tools_collect_blog_article_properties($articleId, $iblockId)
{
    $rows = ai_tools_load_element_properties($articleId, $iblockId);
    $author = "";
    $sources = array();
    $seenSources = array();

    foreach ($rows as $row) {
        $code = ai_tools_string(isset($row["CODE"]) ? $row["CODE"] : "", 100);
        if ($code === "") {
            continue;
        }

        if ($code === "AUTHOR") {
            if (isset($row["VALUE"]) && is_numeric($row["VALUE"])) {
                $authorElement = ai_tools_load_element_row((int)$row["VALUE"], isset($row["LINK_IBLOCK_ID"]) ? (int)$row["LINK_IBLOCK_ID"] : 0);
                if ($authorElement && $author === "") {
                    $author = ai_tools_string(isset($authorElement["NAME"]) ? $authorElement["NAME"] : "", 255);
                }
            }

            if ($author === "") {
                $value = ai_tools_string(ai_tools_normalize_html_text(isset($row["VALUE"]) ? $row["VALUE"] : ""), 255);
                if ($value !== "") {
                    $author = $value;
                }
            }
            continue;
        }

        if ($code === "SOURCES") {
            $value = ai_tools_string(ai_tools_normalize_html_text(isset($row["VALUE"]) ? $row["VALUE"] : ""), 1000);
            if ($value === "") {
                continue;
            }

            $fingerprint = ai_tools_mb_lower($value);
            if (isset($seenSources[$fingerprint])) {
                continue;
            }
            $seenSources[$fingerprint] = true;
            $sources[] = $value;
        }
    }

    return array(
        "author" => $author !== "" ? $author : null,
        "sources" => $sources,
    );
}

function ai_tools_find_blog_article_row($articleId = null, $code = "")
{
    $iblockId = ai_tools_get_blog_iblock_id();

    if ($articleId !== null && (int)$articleId > 0) {
        return ai_tools_query_row(
            "SELECT ID, IBLOCK_SECTION_ID, NAME, CODE, PREVIEW_TEXT, DETAIL_TEXT, ACTIVE_FROM, TIMESTAMP_X, ACTIVE
             FROM b_iblock_element
             WHERE IBLOCK_ID=" . $iblockId . "
               AND ID=" . (int)$articleId . "
               AND ACTIVE='Y'
             LIMIT 1"
        );
    }

    $code = ai_tools_string($code, 255);
    if ($code === "") {
        return null;
    }

    return ai_tools_query_row(
        "SELECT ID, IBLOCK_SECTION_ID, NAME, CODE, PREVIEW_TEXT, DETAIL_TEXT, ACTIVE_FROM, TIMESTAMP_X, ACTIVE
         FROM b_iblock_element
         WHERE IBLOCK_ID=" . $iblockId . "
           AND CODE='" . ai_tools_escape($code) . "'
           AND ACTIVE='Y'
         LIMIT 1"
    );
}

function ai_tools_search_blog_articles($userId, $query, $limit)
{
    $matches = array();

    foreach (ai_tools_get_blog_articles_rows() as $row) {
        $compact = ai_tools_build_blog_article_compact($row, $query);
        $score = ai_tools_search_score($query, $compact["title"], $compact["preview_text"], isset($compact["path"]) ? $compact["path"] : "", isset($compact["code"]) ? $compact["code"] : "");
        if ($score <= 0) {
            continue;
        }

        $compact["_score"] = $score;
        $matches[] = $compact;
    }

    usort(
        $matches,
        function ($left, $right) {
            if ((int)$left["_score"] === (int)$right["_score"]) {
                return (int)$right["article_id"] - (int)$left["article_id"];
            }
            return (int)$right["_score"] - (int)$left["_score"];
        }
    );

    $total = count($matches);
    $matches = array_slice($matches, 0, $limit);
    foreach ($matches as &$match) {
        unset($match["_score"]);
    }
    unset($match);

    return array(
        "query" => $query,
        "count" => $total,
        "items" => $matches,
    );
}

function ai_tools_get_blog_article($userId, $articleId = null, $code = "")
{
    if (($articleId === null || (int)$articleId <= 0) && ai_tools_string($code, 255) === "") {
        ai_tools_fail(422, "missing_article_reference", "Either article_id or code is required");
    }

    $row = ai_tools_find_blog_article_row($articleId, $code);
    if (!$row) {
        ai_tools_fail(404, "article_not_found", "Blog article not found");
    }

    $properties = ai_tools_collect_blog_article_properties((int)$row["ID"], ai_tools_get_blog_iblock_id());
    $sectionId = isset($row["IBLOCK_SECTION_ID"]) ? (int)$row["IBLOCK_SECTION_ID"] : 0;
    $section = ai_tools_load_section_row($sectionId);

    return array(
        "content_type" => "blog_article",
        "article_id" => (int)$row["ID"],
        "title" => ai_tools_string(isset($row["NAME"]) ? $row["NAME"] : "", 255),
        "code" => ai_tools_string(isset($row["CODE"]) ? $row["CODE"] : "", 255),
        "path" => ai_tools_build_blog_article_url($row),
        "published_at" => isset($row["ACTIVE_FROM"]) && $row["ACTIVE_FROM"] ? $row["ACTIVE_FROM"] : (isset($row["TIMESTAMP_X"]) ? $row["TIMESTAMP_X"] : null),
        "section" => array(
            "id" => $sectionId > 0 ? $sectionId : null,
            "name" => $section ? ai_tools_string(isset($section["NAME"]) ? $section["NAME"] : "", 255) : null,
            "code_path" => $sectionId > 0 ? ai_tools_build_section_code_path($sectionId) : null,
        ),
        "author" => $properties["author"],
        "sources" => $properties["sources"],
        "preview_text" => ai_tools_string(ai_tools_normalize_html_text(isset($row["PREVIEW_TEXT"]) ? $row["PREVIEW_TEXT"] : ""), 6000),
        "detail_text" => ai_tools_string(ai_tools_normalize_html_text(isset($row["DETAIL_TEXT"]) ? $row["DETAIL_TEXT"] : ""), 20000),
    );
}

function ai_tools_normalize_site_path($path)
{
    $path = trim((string)$path);
    $parsed = parse_url($path, PHP_URL_PATH);
    if (is_string($parsed) && $parsed !== "") {
        $path = $parsed;
    }

    if ($path === "") {
        return "/";
    }

    $path = preg_replace("~/{2,}~", "/", $path);
    if (substr($path, -10) === "/index.php") {
        $path = substr($path, 0, -9);
    }
    if ($path === "" || $path === false) {
        $path = "/";
    }
    if ($path[0] !== "/") {
        $path = "/" . $path;
    }
    if (substr($path, -1) !== "/") {
        $path .= "/";
    }

    return $path;
}

function ai_tools_get_site_page_registry()
{
    static $registry = null;
    if ($registry !== null) {
        return $registry;
    }

    $docRoot = rtrim((string)$_SERVER["DOCUMENT_ROOT"], "/");
    $registry = array(
        "/about/" => array(
            "page_type" => "about",
            "title" => "О компании ElixirPeptide",
            "file_path" => $docRoot . "/about/index.php",
        ),
        "/about/contacts/" => array(
            "page_type" => "contacts",
            "title" => "Контакты",
            "file_path" => $docRoot . "/about/contacts/index.php",
        ),
        "/about/requisites/" => array(
            "page_type" => "requisites",
            "title" => "Реквизиты",
            "file_path" => $docRoot . "/about/requisites/index.php",
        ),
        "/bonusnaya-i-partnerskaya-programma/" => array(
            "page_type" => "bonus_program",
            "title" => "Бонусная и партнерская программа",
            "file_path" => $docRoot . "/bonusnaya-i-partnerskaya-programma/index.php",
        ),
    );

    return $registry;
}

function ai_tools_parse_php_page_metadata($source)
{
    $metadata = array(
        "title" => "",
        "description" => "",
    );

    if (preg_match("/SetPageProperty\\(\\s*['\\\"]description['\\\"]\\s*,\\s*['\\\"](.+?)['\\\"]\\s*\\)/su", $source, $matches)) {
        $metadata["description"] = ai_tools_string(html_entity_decode($matches[1], ENT_QUOTES | ENT_HTML5, "UTF-8"), 1000);
    }
    if (preg_match("/SetPageProperty\\(\\s*['\\\"]title['\\\"]\\s*,\\s*['\\\"](.+?)['\\\"]\\s*\\)/su", $source, $matches)) {
        $metadata["title"] = ai_tools_string(html_entity_decode($matches[1], ENT_QUOTES | ENT_HTML5, "UTF-8"), 500);
    }
    if (preg_match("/SetTitle\\(\\s*['\\\"](.+?)['\\\"]\\s*\\)/su", $source, $matches)) {
        $metadata["title"] = ai_tools_string(html_entity_decode($matches[1], ENT_QUOTES | ENT_HTML5, "UTF-8"), 500);
    }

    return $metadata;
}

function ai_tools_extract_static_page_text($source)
{
    $source = preg_replace("~<\\?(?:php)?[\\s\\S]*?\\?>~i", " ", (string)$source);
    return ai_tools_dedupe_paragraphs(ai_tools_normalize_html_text($source));
}

function ai_tools_load_contacts_data()
{
    $phones = array();
    $email = "";
    $workingHours = "";
    $address = "";

    if (\Bitrix\Main\Loader::includeModule("sotbit.b2c") && class_exists("\\Sotbit\\B2C\\Helper\\Config")) {
        $contactsData = \Sotbit\B2C\Helper\Config::getContactsData();
        if (is_array($contactsData)) {
            foreach ((array)(isset($contactsData["PHONE"]) ? $contactsData["PHONE"] : array()) as $phoneItem) {
                if (!is_array($phoneItem)) {
                    continue;
                }
                $phone = ai_tools_string(isset($phoneItem["PHONE"]) ? $phoneItem["PHONE"] : "", 80);
                $description = ai_tools_string(isset($phoneItem["DESCRIPTION"]) ? $phoneItem["DESCRIPTION"] : "", 255);
                if ($phone === "") {
                    continue;
                }
                $phones[] = array(
                    "phone" => $phone,
                    "description" => $description !== "" ? $description : null,
                );
            }

            $email = ai_tools_string(isset($contactsData["EMAIL"]) ? $contactsData["EMAIL"] : "", 190);
            $workingHours = ai_tools_string(isset($contactsData["WORKING_HOURS"]) ? $contactsData["WORKING_HOURS"] : "", 255);
            $address = ai_tools_string(isset($contactsData["ADDRESS"]) ? $contactsData["ADDRESS"] : "", 500);
        }
    }

    return array(
        "phones" => $phones,
        "email" => $email !== "" ? $email : null,
        "working_hours" => $workingHours !== "" ? $workingHours : null,
        "address" => $address !== "" ? $address : null,
    );
}

function ai_tools_build_contacts_text(array $contacts)
{
    $parts = array();

    foreach ((array)(isset($contacts["phones"]) ? $contacts["phones"] : array()) as $phoneItem) {
        $line = ai_tools_string(isset($phoneItem["phone"]) ? $phoneItem["phone"] : "", 80);
        if ($line === "") {
            continue;
        }
        $description = ai_tools_string(isset($phoneItem["description"]) ? $phoneItem["description"] : "", 255);
        $parts[] = $description !== "" ? $line . " — " . $description : $line;
    }

    if (!empty($contacts["email"])) {
        $parts[] = "E-mail: " . $contacts["email"];
    }
    if (!empty($contacts["working_hours"])) {
        $parts[] = "Режим работы: " . $contacts["working_hours"];
    }
    if (!empty($contacts["address"])) {
        $parts[] = "Адрес: " . $contacts["address"];
    }

    return implode("\n", $parts);
}

function ai_tools_get_site_page($userId, $path)
{
    $path = ai_tools_normalize_site_path($path);
    $registry = ai_tools_get_site_page_registry();

    if (!isset($registry[$path])) {
        ai_tools_fail(404, "page_not_found", "Supported site page not found");
    }

    $page = $registry[$path];
    $filePath = isset($page["file_path"]) ? (string)$page["file_path"] : "";
    if ($filePath === "" || !is_file($filePath)) {
        ai_tools_fail(404, "page_source_not_found", "Site page source file not found");
    }

    $source = file_get_contents($filePath);
    if (!is_string($source) || $source === "") {
        ai_tools_fail(500, "page_source_read_failed", "Could not read site page source");
    }

    $metadata = ai_tools_parse_php_page_metadata($source);
    $text = ai_tools_extract_static_page_text($source);
    $contacts = null;

    if (isset($page["page_type"]) && $page["page_type"] === "contacts") {
        $contacts = ai_tools_load_contacts_data();
        $contactsText = ai_tools_build_contacts_text($contacts);
        if ($contactsText !== "") {
            $text = ai_tools_dedupe_paragraphs(trim($text . "\n\n" . $contactsText));
        }
    }

    $title = ai_tools_string(isset($metadata["title"]) ? $metadata["title"] : "", 500);
    if ($title === "") {
        $title = ai_tools_string(isset($page["title"]) ? $page["title"] : "", 500);
    }

    return array(
        "content_type" => "site_page",
        "page_type" => isset($page["page_type"]) ? $page["page_type"] : "page",
        "path" => $path,
        "title" => $title,
        "description" => ai_tools_string(isset($metadata["description"]) ? $metadata["description"] : "", 1000),
        "text" => ai_tools_string($text, 20000),
        "contacts" => $contacts,
    );
}

function ai_tools_search_site_content($userId, $query, $limit)
{
    $matches = array();

    foreach (ai_tools_get_site_page_registry() as $path => $pageMeta) {
        $page = ai_tools_get_site_page($userId, $path);
        $score = ai_tools_search_score($query, isset($page["title"]) ? $page["title"] : "", isset($page["text"]) ? $page["text"] : "", $path);
        if ($score <= 0) {
            continue;
        }

        $matches[] = array(
            "content_type" => "site_page",
            "page_type" => isset($page["page_type"]) ? $page["page_type"] : "page",
            "title" => isset($page["title"]) ? $page["title"] : "",
            "path" => $path,
            "snippet" => ai_tools_build_snippet(isset($page["text"]) ? $page["text"] : "", $query, 280),
            "_score" => $score,
        );
    }

    foreach (ai_tools_get_blog_articles_rows() as $row) {
        $compact = ai_tools_build_blog_article_compact($row, $query);
        $bodyText = $compact["preview_text"] !== "" ? $compact["preview_text"] : ai_tools_string(ai_tools_normalize_html_text(isset($row["DETAIL_TEXT"]) ? $row["DETAIL_TEXT"] : ""), 4000);
        $score = ai_tools_search_score($query, $compact["title"], $bodyText, isset($compact["path"]) ? $compact["path"] : "", isset($compact["code"]) ? $compact["code"] : "");
        if ($score <= 0) {
            continue;
        }

        $compact["_score"] = $score;
        $matches[] = $compact;
    }

    usort(
        $matches,
        function ($left, $right) {
            if ((int)$left["_score"] === (int)$right["_score"]) {
                $leftTitle = isset($left["title"]) ? (string)$left["title"] : "";
                $rightTitle = isset($right["title"]) ? (string)$right["title"] : "";
                return strcmp($leftTitle, $rightTitle);
            }
            return (int)$right["_score"] - (int)$left["_score"];
        }
    );

    $total = count($matches);
    $matches = array_slice($matches, 0, $limit);
    foreach ($matches as &$match) {
        unset($match["_score"]);
    }
    unset($match);

    return array(
        "query" => $query,
        "count" => $total,
        "items" => $matches,
    );
}

function ai_tools_get_contacts_info($userId)
{
    $page = ai_tools_get_site_page($userId, "/about/contacts/");
    return array(
        "content_type" => "contacts",
        "path" => "/about/contacts/",
        "title" => isset($page["title"]) ? $page["title"] : "Контакты",
        "text" => isset($page["text"]) ? $page["text"] : "",
        "phones" => isset($page["contacts"]["phones"]) ? $page["contacts"]["phones"] : array(),
        "email" => isset($page["contacts"]["email"]) ? $page["contacts"]["email"] : null,
        "working_hours" => isset($page["contacts"]["working_hours"]) ? $page["contacts"]["working_hours"] : null,
        "address" => isset($page["contacts"]["address"]) ? $page["contacts"]["address"] : null,
    );
}

function ai_tools_get_ai_access($userId)
{
    $userId = (int)$userId;
    $thresholdAmount = (float)AI_TOOLS_MIN_AI_ORDER_TOTAL_RUB;
    $thresholdSql = number_format($thresholdAmount, 4, ".", "");
    $sqlHelper = ai_tools_sqlh();
    $monthStart = date("Y-m-01 00:00:00");
    $nextMonthStart = date("Y-m-01 00:00:00", strtotime("+1 month"));
    $monthStartSql = "'" . $sqlHelper->forSql($monthStart) . "'";
    $nextMonthStartSql = "'" . $sqlHelper->forSql($nextMonthStart) . "'";
    $qualifyingOrder = ai_tools_query_row(
        "SELECT ID, ACCOUNT_NUMBER, PRICE, CURRENCY, DATE_INSERT, STATUS_ID, PAYED, CANCELED
        FROM b_sale_order
        WHERE USER_ID = " . $userId . "
          AND CANCELED = 'N'
          AND PAYED = 'Y'
          AND PRICE > " . $thresholdSql . "
          AND DATE_INSERT >= " . $monthStartSql . "
          AND DATE_INSERT < " . $nextMonthStartSql . "
        ORDER BY DATE_INSERT DESC, ID DESC
        LIMIT 1"
    );

    if (!is_array($qualifyingOrder)) {
        return array(
            "allowed" => false,
            "rule" => "current_month_single_paid_order_total_gt",
            "threshold_amount" => $thresholdAmount,
            "threshold_currency" => "RUB",
            "month_start" => $monthStart,
            "next_month_start" => $nextMonthStart,
            "message" => "Бесплатный лимит из 5 сообщений исчерпан. Дальше AI-консультант доступен только пользователям, у которых есть хотя бы один оплаченный заказ текущего месяца на сумму больше 9000 ₽.",
            "qualifying_order" => null,
        );
    }

    return array(
        "allowed" => true,
        "rule" => "current_month_single_paid_order_total_gt",
        "threshold_amount" => $thresholdAmount,
        "threshold_currency" => "RUB",
        "month_start" => $monthStart,
        "next_month_start" => $nextMonthStart,
        "qualifying_order" => array(
            "order_id" => isset($qualifyingOrder["ID"]) ? (int)$qualifyingOrder["ID"] : 0,
            "account_number" => isset($qualifyingOrder["ACCOUNT_NUMBER"]) ? (string)$qualifyingOrder["ACCOUNT_NUMBER"] : null,
            "price" => isset($qualifyingOrder["PRICE"]) ? (float)$qualifyingOrder["PRICE"] : 0.0,
            "currency" => isset($qualifyingOrder["CURRENCY"]) ? (string)$qualifyingOrder["CURRENCY"] : "RUB",
            "date_insert" => isset($qualifyingOrder["DATE_INSERT"]) ? $qualifyingOrder["DATE_INSERT"] : null,
            "status_id" => isset($qualifyingOrder["STATUS_ID"]) ? (string)$qualifyingOrder["STATUS_ID"] : null,
            "payed" => isset($qualifyingOrder["PAYED"]) ? ((string)$qualifyingOrder["PAYED"] === "Y") : false,
            "canceled" => isset($qualifyingOrder["CANCELED"]) ? ((string)$qualifyingOrder["CANCELED"] === "Y") : false,
        ),
    );
}

function ai_tools_context_bootstrap(array $args)
{
    $userId = ai_tools_require_user_id($args);
    $pagePath = ai_tools_string(isset($args["page_path"]) ? $args["page_path"] : "", 500);
    $pageUrl = ai_tools_string(isset($args["page_url"]) ? $args["page_url"] : "", 1000);
    $pageTitle = ai_tools_string(isset($args["page_title"]) ? $args["page_title"] : "", 255);

    $profile = ai_tools_get_user_profile($userId);
    $cart = ai_tools_get_current_cart($userId);
    $orders = ai_tools_get_recent_orders($userId, AI_TOOLS_DEFAULT_ORDERS_LIMIT);
    $currentProductPayload = ai_tools_get_current_page_product($userId, $pagePath);

    $cartPreview = array_slice($cart["items"], 0, 5);
    $ordersPreview = array_slice($orders["orders"], 0, 3);

    return array(
        "page" => array(
            "path" => $pagePath,
            "url" => $pageUrl,
            "title" => $pageTitle,
        ),
        "ai_access" => ai_tools_get_ai_access($userId),
        "user" => $profile,
        "cart_summary" => $cart["summary"],
        "cart_items_preview" => $cartPreview,
        "orders_summary" => $orders["summary"],
        "recent_orders_preview" => $ordersPreview,
        "current_product" => $currentProductPayload["resolved"] ? $currentProductPayload["product"] : null,
    );
}
