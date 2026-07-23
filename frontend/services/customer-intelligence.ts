import * as Application from "expo-application"
import Constants from "expo-constants"
import * as Notifications from "expo-notifications"
import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"

import { syncMyCustomerIntelligence } from "@/services/api/users"
import type {
    CustomerAttributionPayload,
    CustomerEventName,
    CustomerIntelligenceSyncPayload,
} from "@/services/api/users.types"

const INSTALLATION_ID_KEY = "elixir_customer_intelligence_installation_id"
const SESSION_ID = createId()
let installationIdPromise: Promise<string> | null = null

function createId() {
    if (typeof globalThis.crypto?.randomUUID === "function") {
        return globalThis.crypto.randomUUID()
    }
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
}

async function getInstallationId() {
    if (!installationIdPromise) {
        installationIdPromise = SecureStore.getItemAsync(INSTALLATION_ID_KEY).then(async (stored) => {
            if (stored && stored.length >= 8) {
                return stored
            }
            const generated = createId()
            await SecureStore.setItemAsync(INSTALLATION_ID_KEY, generated)
            return generated
        })
    }
    return installationIdPromise
}

function getDeviceModel() {
    const platformConstants = Platform.constants as unknown as Record<string, unknown>
    const model = platformConstants.Model ?? platformConstants.model ?? Constants.deviceName
    return typeof model === "string" && model.trim() ? model.trim() : null
}

function getLanguage() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().locale || null
    } catch {
        return null
    }
}

function getTimezone() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || null
    } catch {
        return null
    }
}

async function getPushPermission(): Promise<"granted" | "denied" | "undetermined" | "provisional" | "unknown"> {
    if (Platform.OS === "web") {
        return "unknown"
    }
    try {
        const permission = await Notifications.getPermissionsAsync()
        if (permission.ios?.status === Notifications.IosAuthorizationStatus.PROVISIONAL) {
            return "provisional"
        }
        if (permission.granted || permission.status === "granted") {
            return "granted"
        }
        if (permission.status === "denied") {
            return "denied"
        }
        return "undetermined"
    } catch {
        return "unknown"
    }
}

async function getInstallSource() {
    if (Platform.OS !== "android") {
        return null
    }
    try {
        const value = await Application.getInstallReferrerAsync()
        return value?.trim() || null
    } catch {
        return null
    }
}

async function devicePayload(): Promise<NonNullable<CustomerIntelligenceSyncPayload["device"]>> {
    return {
        installation_id: await getInstallationId(),
        platform: Platform.OS === "ios" || Platform.OS === "android" ? Platform.OS : "web",
        app_version: Application.nativeApplicationVersion ?? Constants.expoConfig?.version ?? null,
        app_build: Application.nativeBuildVersion ?? null,
        os_version: String(Platform.Version),
        device_model: getDeviceModel(),
        language: getLanguage(),
        timezone: getTimezone(),
        push_permission: await getPushPermission(),
        install_source: await getInstallSource(),
        metadata: {
            execution_environment: Constants.executionEnvironment,
        },
    }
}

type TrackEventOptions = {
    properties?: Record<string, unknown>
    attribution?: CustomerAttributionPayload
    entityType?: string
    entityId?: number
}

function eventPayload(
    name: CustomerEventName,
    options: TrackEventOptions = {},
): NonNullable<CustomerIntelligenceSyncPayload["events"]>[number] {
    return {
        event_id: createId(),
        name,
        occurred_at: new Date().toISOString(),
        session_id: SESSION_ID,
        source: "app",
        entity_type: options.entityType,
        entity_id: options.entityId,
        properties: options.properties ?? {},
        attribution: options.attribution,
    }
}

export async function syncCustomerIntelligenceSession(properties: Record<string, unknown> = {}) {
    return syncMyCustomerIntelligence({
        device: await devicePayload(),
        events: [eventPayload("app_opened", { properties })],
    })
}

export async function trackCustomerEvent(name: CustomerEventName, options: TrackEventOptions = {}) {
    return syncMyCustomerIntelligence({
        device: await devicePayload(),
        events: [eventPayload(name, options)],
    })
}

function pushAttribution(data: Record<string, unknown>): CustomerAttributionPayload {
    const rawUtm = data.utm
    const utm = rawUtm && typeof rawUtm === "object" && !Array.isArray(rawUtm)
        ? rawUtm as Record<string, unknown>
        : {}
    const stringValue = (value: unknown) => typeof value === "string" && value.trim() ? value.trim() : undefined
    const campaignId = data.campaign_id === null || data.campaign_id === undefined
        ? undefined
        : String(data.campaign_id)
    return {
        source: stringValue(utm.source) ?? "push",
        medium: stringValue(utm.medium) ?? "notification",
        campaign: stringValue(utm.campaign) ?? stringValue(campaignId),
        content: stringValue(utm.content),
        term: stringValue(utm.term),
    }
}

export async function trackPushEngagement(data: Record<string, unknown>) {
    const attribution = pushAttribution(data)
    return syncMyCustomerIntelligence({
        device: await devicePayload(),
        events: [
            eventPayload("push_opened", { properties: data, attribution }),
            eventPayload("push_clicked", { properties: data, attribution }),
        ],
    })
}
