import Constants from "expo-constants"
import * as Notifications from "expo-notifications"
import { Platform } from "react-native"

import { deleteMyPushToken, registerMyPushToken } from "@/services/api/users"

const DEFAULT_ANDROID_CHANNEL_ID = "default"

let notificationsConfigured = false
let registeredExpoPushToken: string | null = null
let syncRequest: Promise<string | null> | null = null

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

        if (registeredExpoPushToken === expoPushToken) {
            return expoPushToken
        }

        await registerMyPushToken({
            expo_push_token: expoPushToken,
            platform,
        })
        registeredExpoPushToken = expoPushToken
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
}
