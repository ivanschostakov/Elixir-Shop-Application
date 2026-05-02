import Constants from "expo-constants"
import * as Notifications from "expo-notifications"
import { type Href } from "expo-router"
import { Platform } from "react-native"

import { getProductRoute, ROUTES } from "@/constants/routes"
import { deleteMyPushToken, registerMyPushToken } from "@/services/api/users"

const DEFAULT_ANDROID_CHANNEL_ID = "default"

let notificationsConfigured = false
let registeredExpoPushToken: string | null = null
let registeredRoutePath: string | null = null
let currentRoutePath: string | null = null
let syncRequest: Promise<string | null> | null = null

type PushNotificationData = Record<string, unknown>
type PushNotificationNavigate = (target: Href) => void

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
        name: "Order updates",
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: "#2383E2",
    })
}

async function requestPushPermissions() {
    const existingPermissions = await Notifications.getPermissionsAsync()
    if (existingPermissions.granted) {
        return true
    }

    const requestedPermissions = await Notifications.requestPermissionsAsync()
    return requestedPermissions.granted
}

async function getExpoPushToken() {
    ensureNotificationsConfigured()
    await ensureAndroidChannel()

    const isGranted = await requestPushPermissions()
    if (!isGranted) {
        return null
    }

    const projectId = getProjectId()
    const token = await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined)
    return token.data
}

async function performPushTokenSync() {
    const platform = Platform.OS
    if (platform !== "ios" && platform !== "android") {
        return null
    }

    try {
        const expoPushToken = await getExpoPushToken()
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

export async function syncOrderStatusNotifications() {
    if (!syncRequest) {
        syncRequest = performPushTokenSync().finally(() => {
            syncRequest = null
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
        case "ai_reply":
            return ROUTES.chat
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

        navigate(target)
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
