<?php
if (!defined("B_PROLOG_INCLUDED") || B_PROLOG_INCLUDED !== true) die();

use Bitrix\Main\Engine\Contract\Controllerable;
use Bitrix\Main\Engine\ActionFilter;
use Bitrix\Main\SystemException;
use Bitrix\Main\Web\HttpClient;
use Bitrix\Sale;

class ChatWrapperComponent extends CBitrixComponent implements Controllerable
{
    const FIXED_MODE = 'professor';
    const DEFAULT_MODE = self::FIXED_MODE;
    const COMPONENT_NAME = 'aichat:chat.wrapper';
    const CART_ITEMS_LIMIT = 10;
    const ORDER_ITEMS_LIMIT = 10;
    const RECENT_ORDERS_LIMIT = 5;

    protected $componentConfig = array();

    public function onPrepareComponentParams($arParams)
    {
        $this->componentConfig = $this->loadComponentConfig();
        return is_array($arParams) ? $arParams : array();
    }

    public function configureActions()
    {
        return array(
            'sendMessage' => $this->protectedActionConfig(),
            'requestOtp' => $this->protectedActionConfig(),
            'verifyOtp' => $this->protectedActionConfig(),
            'loadHistory' => $this->protectedActionConfig(),
            'performAction' => $this->protectedActionConfig(),
            'resetConversation' => $this->protectedActionConfig(),
            'setMode' => $this->protectedActionConfig(),
        );
    }

    protected function protectedActionConfig()
    {
        return array(
            'prefilters' => array(
                new ActionFilter\Authentication(),
                new ActionFilter\HttpMethod(array(ActionFilter\HttpMethod::METHOD_POST)),
                new ActionFilter\Csrf(),
                new ActionFilter\CloseSession(),
            ),
        );
    }

    public function executeComponent()
    {
        global $USER;

        try {
            $this->bootstrapModules();
            $userId = ($USER instanceof CUser && $USER->IsAuthorized()) ? (int)$USER->GetID() : 0;
            $this->arResult['CHAT_CONFIG'] = $this->buildInitialState($userId);
            $this->arResult['SIGNED_PARAMETERS'] = method_exists($this, 'getSignedParameters') ? $this->getSignedParameters() : '';
            $this->includeComponentTemplate();
        } catch (\Throwable $exception) {
            ShowError($exception->getMessage());
        }
    }

    public function sendMessageAction($message, $clientContext = array())
    {
        $this->bootstrapModules();
        $userId = $this->assertAuthorizedUser();
        $text = trim((string)$message);
        if ($text === '') {
            throw new SystemException('Message cannot be empty');
        }
        if (!is_array($clientContext)) {
            $clientContext = array();
        }

        $payload = $this->buildRequestPayload($userId, $text, $clientContext);
        $response = $this->callFastApi('/webchat/message', $payload, 'POST');

        return array(
            'ok' => !empty($response['ok']),
            'accepted' => !empty($response['accepted']),
            'session_id' => isset($response['session_id']) ? (string)$response['session_id'] : '',
            'mode' => isset($response['mode']) ? (string)$response['mode'] : $this->getMode($userId),
            'messages' => isset($response['messages']) && is_array($response['messages']) ? $response['messages'] : array(),
            'active_job' => isset($response['active_job']) && is_array($response['active_job']) ? $response['active_job'] : null,
        );
    }

    public function requestOtpAction()
    {
        $this->bootstrapModules();
        $userId = $this->assertAuthorizedUser();
        return $this->callFastApi('/webchat/otp/request', $this->buildOtpPayload($userId), 'POST');
    }

    public function verifyOtpAction($code)
    {
        $this->bootstrapModules();
        $userId = $this->assertAuthorizedUser();
        $code = preg_replace('/\D+/', '', (string)$code);
        if (strlen($code) !== 6) {
            throw new SystemException('Введите шестизначный код из SMS');
        }
        $payload = $this->buildOtpPayload($userId);
        $payload['code'] = $code;
        return $this->callFastApi('/webchat/otp/verify', $payload, 'POST');
    }

    public function loadHistoryAction()
    {
        $this->bootstrapModules();
        $userId = $this->assertAuthorizedUser();
        $response = $this->callFastApi('/webchat/history/' . $userId, array(), 'GET');
        if (!empty($response['mode']) && (string)$response['mode'] !== self::FIXED_MODE) {
            $this->callFastApi('/webchat/reset', array('bitrix_user_id' => $userId), 'POST');
            return array(
                'ok' => true,
                'session_id' => null,
                'mode' => self::FIXED_MODE,
                'messages' => array(),
                'active_job' => null,
            );
        }
        $response['mode'] = self::FIXED_MODE;
        return $response;
    }

    public function resetConversationAction()
    {
        $this->bootstrapModules();
        $userId = $this->assertAuthorizedUser();
        return $this->callFastApi('/webchat/reset', array('bitrix_user_id' => $userId), 'POST');
    }

    public function performActionAction($sessionId, $messageId, $actionId, $actionToken)
    {
        $this->bootstrapModules();
        $userId = $this->assertAuthorizedUser();

        $sessionId = (int)$sessionId;
        $messageId = (int)$messageId;
        $actionId = $this->limitString((string)$actionId, 120);
        $actionToken = $this->limitString((string)$actionToken, 4000);

        if ($sessionId <= 0 || $messageId <= 0 || $actionId === '' || $actionToken === '') {
            throw new SystemException('Invalid interactive action payload');
        }

        return $this->callFastApi(
            '/webchat/action',
            array(
                'bitrix_user_id' => $userId,
                'phone_number' => $this->buildOtpPayload($userId)['phone_number'],
                'session_id' => $sessionId,
                'message_id' => $messageId,
                'action_id' => $actionId,
                'action_token' => $actionToken,
            ),
            'POST'
        );
    }

    public function setModeAction($mode)
    {
        $this->bootstrapModules();
        $this->assertAuthorizedUser();

        return array(
            'ok' => true,
            'mode' => self::FIXED_MODE,
        );
    }

    protected function bootstrapModules()
    {
        return;
    }

    protected function assertAuthorizedUser()
    {
        global $USER;

        if (!($USER instanceof CUser) || !$USER->IsAuthorized()) {
            throw new SystemException('Authorization required');
        }

        return (int)$USER->GetID();
    }

    protected function buildInitialState($userId)
    {
        $userContext = $userId > 0 ? $this->buildUserContext($userId) : array();

        return array(
            'isAuthorized' => $userId > 0,
            'userId' => $userId > 0 ? $userId : null,
            'userName' => !empty($userContext['name']) ? $userContext['name'] : 'Гость',
            'mode' => self::FIXED_MODE,
            'componentName' => self::COMPONENT_NAME,
            'page' => $this->buildPageContext(array()),
        );
    }

    protected function buildRequestPayload($userId, $message, array $clientContext)
    {
        $userContext = $this->buildUserContext($userId);
        return array(
            'bitrix_user_id' => $userId,
            'phone_number' => isset($userContext['phone']) ? $userContext['phone'] : '',
            'message' => $this->limitString($message, 20000),
            'page' => $this->buildPageContext($clientContext),
        );
    }

    protected function buildOtpPayload($userId)
    {
        $userContext = $this->buildUserContext($userId);
        $phone = isset($userContext['phone']) ? trim((string)$userContext['phone']) : '';
        if ($phone === '') {
            throw new SystemException('Добавьте номер телефона в профиль, чтобы пользоваться AI-чатом');
        }
        return array('bitrix_user_id' => $userId, 'phone_number' => $phone);
    }

    protected function buildUserContext($userId)
    {
        $user = $this->loadUser($userId);
        $groupIds = array();
        foreach ((array)CUser::GetUserGroup($userId) as $groupId) {
            $groupIds[] = (int)$groupId;
        }

        return array(
            'id' => $userId,
            'name' => $this->limitString(isset($user['NAME']) ? (string)$user['NAME'] : '', 120),
            'last_name' => $this->limitString(isset($user['LAST_NAME']) ? (string)$user['LAST_NAME'] : '', 120),
            'email' => $this->limitString(isset($user['EMAIL']) ? (string)$user['EMAIL'] : '', 190),
            'phone' => $this->limitString(
                !empty($user['PERSONAL_PHONE'])
                    ? (string)$user['PERSONAL_PHONE']
                    : (isset($user['PERSONAL_MOBILE']) ? (string)$user['PERSONAL_MOBILE'] : ''),
                60
            ),
            'group_ids' => $groupIds,
        );
    }

    protected function buildCartContext()
    {
        $items = array();
        $linesCount = 0;
        $unitsCount = 0.0;
        $totalPrice = 0.0;
        $currency = '';

        $basket = Sale\Basket::loadItemsForFUser(Sale\Fuser::getId(), SITE_ID)->getOrderableItems();
        foreach ($basket as $basketItem) {
            if (count($items) >= self::CART_ITEMS_LIMIT) {
                break;
            }
            if ($basketItem->getField('DELAY') === 'Y' || $basketItem->getField('CAN_BUY') !== 'Y') {
                continue;
            }

            $mappedItem = $this->mapBasketItem($basketItem);
            $items[] = $mappedItem;
            $linesCount++;
            $unitsCount += (float)$mappedItem['quantity'];
            $totalPrice += ((float)$mappedItem['quantity'] * (float)$mappedItem['price']);
            if ($currency === '' && !empty($mappedItem['currency'])) {
                $currency = (string)$mappedItem['currency'];
            }
        }

        return array(
            'cart_summary' => array(
                'lines_count' => $linesCount,
                'units_count' => round($unitsCount, 2),
                'total_price' => round($totalPrice, 2),
                'currency' => $currency,
            ),
            'cart_items' => $items,
        );
    }

    protected function buildOrdersContext($userId)
    {
        $summary = array(
            'total_orders' => 0,
            'canceled_orders' => 0,
            'last_order_at' => null,
            'total_spent' => 0.0,
            'currency' => '',
        );
        $recentOrders = array();

        $summaryResult = Sale\Order::getList(array(
            'filter' => array('=USER_ID' => $userId),
            'select' => array('ID', 'CANCELED', 'DATE_INSERT', 'PRICE', 'CURRENCY'),
            'order' => array('DATE_INSERT' => 'DESC'),
        ));

        while ($row = $summaryResult->fetch()) {
            $summary['total_orders']++;
            if ((string)$row['CANCELED'] === 'Y') {
                $summary['canceled_orders']++;
            }
            $summary['total_spent'] += (float)$row['PRICE'];
            if ($summary['last_order_at'] === null) {
                $summary['last_order_at'] = $this->formatDateTime($row['DATE_INSERT']);
            }
            if ($summary['currency'] === '' && !empty($row['CURRENCY'])) {
                $summary['currency'] = (string)$row['CURRENCY'];
            }
        }
        $summary['total_spent'] = round($summary['total_spent'], 2);

        $recentResult = Sale\Order::getList(array(
            'filter' => array('=USER_ID' => $userId),
            'select' => array('ID', 'ACCOUNT_NUMBER', 'STATUS_ID', 'CANCELED', 'DATE_INSERT', 'PRICE', 'CURRENCY'),
            'order' => array('DATE_INSERT' => 'DESC'),
            'limit' => self::RECENT_ORDERS_LIMIT,
        ));

        while ($row = $recentResult->fetch()) {
            $recentOrders[] = $this->loadOrderPayload((int)$row['ID'], $row);
        }

        return array(
            'orders_summary' => $summary,
            'recent_orders' => $recentOrders,
        );
    }

    protected function buildPageContext(array $clientContext)
    {
        $requestUri = isset($_SERVER['REQUEST_URI']) ? (string)$_SERVER['REQUEST_URI'] : '/';
        $path = parse_url($requestUri, PHP_URL_PATH);
        if (!is_string($path) || $path === '') {
            $path = '/';
        }

        $scheme = (!empty($_SERVER['HTTPS']) && strtolower((string)$_SERVER['HTTPS']) !== 'off') || (isset($_SERVER['SERVER_PORT']) && (int)$_SERVER['SERVER_PORT'] === 443)
            ? 'https'
            : 'http';
        $host = isset($_SERVER['HTTP_HOST']) ? (string)$_SERVER['HTTP_HOST'] : '';
        $serverUrl = $host !== '' ? $scheme . '://' . $host . $requestUri : $requestUri;

        return array(
            'url' => $this->limitString(!empty($clientContext['url']) ? (string)$clientContext['url'] : $serverUrl, 1000),
            'path' => $this->limitString(!empty($clientContext['path']) ? (string)$clientContext['path'] : $path, 500),
            'title' => $this->limitString(!empty($clientContext['title']) ? (string)$clientContext['title'] : '', 255),
            'referrer' => $this->limitString(!empty($clientContext['referrer']) ? (string)$clientContext['referrer'] : '', 1000),
        );
    }

    protected function loadOrderPayload($orderId, array $row = array())
    {
        $payload = array(
            'order_id' => $orderId,
            'account_number' => isset($row['ACCOUNT_NUMBER']) ? (string)$row['ACCOUNT_NUMBER'] : '',
            'status_id' => isset($row['STATUS_ID']) ? (string)$row['STATUS_ID'] : '',
            'canceled' => isset($row['CANCELED']) && (string)$row['CANCELED'] === 'Y',
            'date_insert' => isset($row['DATE_INSERT']) ? $this->formatDateTime($row['DATE_INSERT']) : null,
            'price' => isset($row['PRICE']) ? round((float)$row['PRICE'], 2) : 0.0,
            'currency' => isset($row['CURRENCY']) ? (string)$row['CURRENCY'] : '',
            'items_count' => 0,
            'items' => array(),
        );

        $order = Sale\Order::load($orderId);
        if (!$order) {
            return $payload;
        }

        $count = 0;
        foreach ($order->getBasket() as $basketItem) {
            $count++;
            if (count($payload['items']) < self::ORDER_ITEMS_LIMIT) {
                $payload['items'][] = $this->mapBasketItem($basketItem);
            }
        }
        $payload['items_count'] = $count;

        if ($payload['date_insert'] === null) {
            $payload['date_insert'] = $this->formatDateTime($order->getField('DATE_INSERT'));
        }

        return $payload;
    }

    protected function mapBasketItem($basketItem)
    {
        return array(
            'basket_id' => (int)$basketItem->getId(),
            'product_id' => (int)$basketItem->getProductId(),
            'name' => $this->limitString((string)$basketItem->getField('NAME'), 500),
            'detail_page_url' => $this->limitString((string)$basketItem->getField('DETAIL_PAGE_URL'), 1000),
            'quantity' => round((float)$basketItem->getQuantity(), 3),
            'price' => round((float)$basketItem->getPrice(), 2),
            'currency' => (string)$basketItem->getCurrency(),
        );
    }

    protected function getMode($userId)
    {
        return self::FIXED_MODE;
    }

    protected function saveMode($userId, $mode)
    {
        return;
    }

    protected function callFastApi($path, array $payload = array(), $method = 'POST')
    {
        $config = $this->getComponentConfig();
        $baseUrl = rtrim((string)$config['fastapi_base_url'], '/');
        $sharedSecret = (string)$config['shared_secret'];
        $timeout = !empty($config['timeout']) ? (int)$config['timeout'] : 20;

        if ($baseUrl === '') {
            throw new SystemException('FastAPI base URL is not configured in chat.wrapper/config.php');
        }
        if ($sharedSecret === '') {
            throw new SystemException('FastAPI shared secret is not configured in chat.wrapper/config.php');
        }

        $method = strtoupper((string)$method);
        $body = $method === 'GET' ? '' : json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if ($body === false) {
            throw new SystemException('Failed to encode FastAPI payload');
        }

        $timestamp = (string)time();
        $nonce = bin2hex(random_bytes(16));
        $signature = $this->signInternalPayload($timestamp, $nonce, $method, $path, $body, $sharedSecret);

        $client = new HttpClient(array(
            'socketTimeout' => $timeout,
            'streamTimeout' => $timeout,
        ));
        $client->setHeader('Accept', 'application/json', true);
        $client->setHeader('X-Webchat-Timestamp', $timestamp, true);
        $client->setHeader('X-Webchat-Nonce', $nonce, true);
        $client->setHeader('X-Webchat-Signature', $signature, true);
        if ($method !== 'GET') {
            $client->setHeader('Content-Type', 'application/json', true);
        }

        if ($method === 'GET') {
            $rawResponse = $client->get($baseUrl . $path);
        } else {
            $rawResponse = $client->post($baseUrl . $path, $body);
        }

        if ($rawResponse === false) {
            throw new SystemException('FastAPI request failed');
        }

        $status = (int)$client->getStatus();
        if ($status >= 400) {
            $errorPayload = json_decode($rawResponse, true);
            $detail = is_array($errorPayload) && isset($errorPayload['detail']) ? $errorPayload['detail'] : null;
            if (is_array($detail) && !empty($detail['message'])) {
                $detail = $detail['message'];
            }
            if (is_string($detail) && trim($detail) !== '') {
                throw new SystemException(trim($detail));
            }
            throw new SystemException('FastAPI returned HTTP ' . $status);
        }

        $decoded = json_decode($rawResponse, true);
        if (!is_array($decoded)) {
            throw new SystemException('FastAPI returned invalid JSON');
        }

        return $decoded;
    }

    protected function signInternalPayload($timestamp, $nonce, $method, $path, $body, $secret)
    {
        $payload = implode(':', array(
            (string)$timestamp,
            (string)$nonce,
            strtoupper((string)$method),
            (string)$path,
            hash('sha256', (string)$body),
        ));

        return hash_hmac('sha256', $payload, (string)$secret);
    }

    protected function getComponentConfig()
    {
        if (empty($this->componentConfig)) {
            $this->componentConfig = $this->loadComponentConfig();
        }
        return $this->componentConfig;
    }

    protected function loadComponentConfig()
    {
        $configPath = __DIR__ . '/config.php';
        $defaults = array(
            'fastapi_base_url' => '',
            'shared_secret' => '',
            'timeout' => 20,
            'component_name' => self::COMPONENT_NAME,
        );

        if (!file_exists($configPath)) {
            return $defaults;
        }

        $loaded = include $configPath;
        if (!is_array($loaded)) {
            return $defaults;
        }

        return array_merge($defaults, $loaded);
    }

    protected function loadUser($userId)
    {
        $result = CUser::GetByID($userId);
        $user = $result ? $result->Fetch() : array();
        return is_array($user) ? $user : array();
    }

    protected function formatDateTime($value)
    {
        if ($value instanceof \Bitrix\Main\Type\DateTime || $value instanceof \DateTimeInterface) {
            return $value->format(DATE_ATOM);
        }
        if (is_string($value) && $value !== '') {
            $timestamp = strtotime($value);
            if ($timestamp !== false) {
                return date(DATE_ATOM, $timestamp);
            }
            return $value;
        }

        return null;
    }

    protected function limitString($value, $maxLength)
    {
        $value = trim((string)$value);
        if ($value === '' || $maxLength <= 0) {
            return $value;
        }

        if (function_exists('mb_strlen') && function_exists('mb_substr')) {
            if (mb_strlen($value, 'UTF-8') > $maxLength) {
                return mb_substr($value, 0, $maxLength, 'UTF-8');
            }
            return $value;
        }

        if (strlen($value) > $maxLength) {
            return substr($value, 0, $maxLength);
        }

        return $value;
    }
}
