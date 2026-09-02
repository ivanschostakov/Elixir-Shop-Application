import Constants from "expo-constants"
import * as Notifications from "expo-notifications"
import { type Href } from "expo-router"
import { Platform } from "react-native"

import { getProductRoute, ROUTES } from "@/constants/routes"
import { deleteMyPushToken, registerMyPushToken } from "@/services/api/users"

const DEFAULT_ANDROID_CHANNEL_ID = "default"
const COMMUNITY_ANDROID_CHANNEL_ID = "community_messages"
const SUPPORT_ANDROID_CHANNEL_ID = "support_messages"

let notificationsConfigured = false
let registeredExpoPushToken: string | null = null
let registeredRoutePath: string | null = null
let currentRoutePath: string | null = null
let syncRequest: Promise<string | null> | null = null
let syncRequestAllowsPermissionPrompt = false

type PushNotificationData = Record<string, unknown>
type PushNotificationNavigate = (target: Href, data: PushNotificationData) => void
type OrderStatusNotificationSyncOptions = {
    requestPermissions?: boolean
}

const ORDER_STATUS_PAYMENT_CODES = new Set(["created", "invoice_sent"])

function normalizeRoutePath(pathname: string | null | undefined) {
    if (!pathname) {
        return null
    }
    const normalized = pathname.trim()
    if (!normalized) {
        return null
    }
    if (normalized === "/") {
        return "/"
    }
    const normalizedWithoutQuery = normalized.split("?")[0].split("#")[0]
    const normalizedPath = normalizedWithoutQuery.endsWith("/") ? normalizedWithoutQuery.slice(0, -1) : normalizedWithoutQuery
    return normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`
}

export function setOrderStatusNotificationCurrentPath(pathname: string | null) {
    currentRoutePath = normalizeRoutePath(pathname)
}

function getProjectId() {
    return Constants.easConfig?.projectId ?? Constants.expoConfig?.extra?.eas?.projectId ?? undefined
}

function ensureNotificationsConfigured() {
    if (notificationsConfigured || Platform.OS === "web") {
        return
    }

    Notifications.setNotificationHandler({
        handleNotification: async () => ({
            shouldShowBanner: true,
            shouldShowList: true,
            shouldPlaySound: true,
            shouldSetBadge: false,
        }),
    })

    notificationsConfigured = true
}

async function ensureAndroidChannel() {
    if (Platform.OS !== "android") {
        return
    }

    await Notifications.setNotificationChannelAsync(DEFAULT_ANDROID_CHANNEL_ID, {
        name: "App updates",
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: "#2383E2",
    })
    await Notifications.setNotificationChannelAsync(COMMUNITY_ANDROID_CHANNEL_ID, {
        name: "Community messages",
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: "#2383E2",
        sound: "default",
    })
    await Notifications.setNotificationChannelAsync(SUPPORT_ANDROID_CHANNEL_ID, {
        name: "Support messages",
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: "#2383E2",
        sound: "default",
    })
}

async function hasPushPermissions(options: OrderStatusNotificationSyncOptions) {
    const existingPermissions = await Notifications.getPermissionsAsync()
    if (existingPermissions.granted) {
        return true
    }

    if (!options.requestPermissions) {
        return false
    }

    const requestedPermissions = await Notifications.requestPermissionsAsync()
    return requestedPermissions.granted
}

async function getExpoPushToken(options: OrderStatusNotificationSyncOptions) {
    ensureNotificationsConfigured()
    await ensureAndroidChannel()

    const isGranted = await hasPushPermissions(options)
    if (!isGranted) {
        return null
    }

    const projectId = getProjectId()
    const token = await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined)
    return token.data
}

async function performPushTokenSync(options: OrderStatusNotificationSyncOptions) {
    const platform = Platform.OS
    if (platform !== "ios" && platform !== "android") {
        return null
    }

    try {
        const expoPushToken = await getExpoPushToken(options)
        if (!expoPushToken) {
            return null
        }

        const normalizedRoutePath = normalizeRoutePath(currentRoutePath)
        if (registeredExpoPushToken === expoPushToken && registeredRoutePath === normalizedRoutePath) {
            return expoPushToken
        }

        await registerMyPushToken({
            expo_push_token: expoPushToken,
            platform,
            current_path: normalizedRoutePath,
        })
        registeredExpoPushToken = expoPushToken
        registeredRoutePath = normalizedRoutePath
        return expoPushToken
    } catch (error) {
        if (__DEV__) {
            console.log("Push notification registration skipped", error)
        }
        return null
    }
}

export async function syncOrderStatusNotifications(options: OrderStatusNotificationSyncOptions = {}) {
    if (syncRequest) {
        if (!options.requestPermissions || syncRequestAllowsPermissionPrompt) {
            return syncRequest
        }

        await syncRequest.catch(() => null)
    }

    if (!syncRequest) {
        syncRequestAllowsPermissionPrompt = Boolean(options.requestPermissions)
        syncRequest = performPushTokenSync(options).finally(() => {
            syncRequest = null
            syncRequestAllowsPermissionPrompt = false
        })
    }

    return syncRequest
}

export async function unregisterOrderStatusNotifications() {
    const platform = Platform.OS
    if (platform !== "ios" && platform !== "android") {
        return
    }

    if (!registeredExpoPushToken) {
        return
    }

    const expoPushToken = registeredExpoPushToken
    registeredExpoPushToken = null
    registeredRoutePath = null

    try {
        await deleteMyPushToken({ expo_push_token: expoPushToken })
    } catch (error) {
        if (__DEV__) {
            console.log("Push notification unregister skipped", error)
        }
    }
}

export function resetOrderStatusNotifications() {
    registeredExpoPushToken = null
    registeredRoutePath = null
}

function asString(value: unknown): string | null {
    return typeof value === "string" ? value : null
}

function asPositiveInt(value: unknown): number | null {
    const parsedNumber = typeof value === "number" ? value : typeof value === "string" ? Number(value) : Number.NaN

    if (!Number.isInteger(parsedNumber) || parsedNumber <= 0) {
        return null
    }

    return parsedNumber
}

function resolvePushTarget(data: PushNotificationData): Href | null {
    const type = asString(data.type)
    if (!type) {
        return null
    }

    switch (type) {
        case "order_status_changed": {
            const statusCode = asString(data.status_code)
            const orderId = asPositiveInt(data.order_id)

            if (orderId && statusCode && ORDER_STATUS_PAYMENT_CODES.has(statusCode)) {
                return {
                    pathname: ROUTES.payment,
                    params: { orderId: String(orderId) },
                }
            }

            return ROUTES.profileHistory
        }
        case "restock":
        case "review_reminder": {
            const productId = asPositiveInt(data.product_id)
            if (!productId) {
                return ROUTES.discover
            }

            if (type === "restock") {
                const variantId = asPositiveInt(data.variant_id)
                if (variantId) {
                    return {
                        pathname: `/products/${productId}`,
                        params: { variantId: String(variantId) },
                    }
                }
            }

            return getProductRoute(productId)
        }
        case "inactive_customer":
            return ROUTES.discover
        case "abandoned_cart":
            return ROUTES.basket
        case "admin_campaign": {
            const deepLink = asString(data.deep_link)?.trim()
            if (!deepLink || !deepLink.startsWith("/") || deepLink.startsWith("//")) {
                return ROUTES.discover
            }
            return deepLink as Href
        }
        case "ai_reply":
            return ROUTES.chat
        case "support_reply": {
            const conversationId = asPositiveInt(data.conversation_id)
            return {
                pathname: ROUTES.chat,
                params: {
                    mode: "support",
                    ...(conversationId ? { conversationId: String(conversationId) } : {}),
                },
            }
        }
        case "community_message": {
            const topicId = asPositiveInt(data.topic_id)
            if (!topicId) return ROUTES.chat
            return {
                pathname: ROUTES.chat,
                params: { mode: "community", topicId: String(topicId) },
            }
        }
        default:
            return null
    }
}

function extractNotificationData(response: Notifications.NotificationResponse): PushNotificationData | null {
    const data = response.notification.request.content.data
    if (!data || typeof data !== "object" || Array.isArray(data)) {
        return null
    }

    return data as PushNotificationData
}

export function attachPushOpenListener(navigate: PushNotificationNavigate) {
    if (Platform.OS === "web") {
        return () => undefined
    }

    let isDisposed = false
    const handledNotificationIds = new Set<string>()

    const handleResponse = (response: Notifications.NotificationResponse) => {
        if (isDisposed) {
            return
        }

        const notificationId = response.notification.request.identifier
        if (handledNotificationIds.has(notificationId)) {
            return
        }
        handledNotificationIds.add(notificationId)

        const data = extractNotificationData(response)
        if (!data) {
            return
        }

        const target = resolvePushTarget(data)
        if (!target) {
            return
        }

        navigate(target, data)
    }

    const responseSubscription = Notifications.addNotificationResponseReceivedListener(handleResponse)
    void Notifications.getLastNotificationResponseAsync()
        .then((lastResponse) => {
            if (!lastResponse) {
                return
            }
            handleResponse(lastResponse)
            void Notifications.clearLastNotificationResponseAsync().catch(() => undefined)
        })
        .catch(() => undefined)

    return () => {
        isDisposed = true
        handledNotificationIds.clear()
        responseSubscription.remove()
    }
}

// Generic names for call sites that subscribe to more than order updates.
// Keep the original exports for OTA compatibility with existing screens.
export const setPushNotificationCurrentPath = setOrderStatusNotificationCurrentPath
export const syncPushNotifications = syncOrderStatusNotifications
export const unregisterPushNotifications = unregisterOrderStatusNotifications
export const resetPushNotifications = resetOrderStatusNotifications
