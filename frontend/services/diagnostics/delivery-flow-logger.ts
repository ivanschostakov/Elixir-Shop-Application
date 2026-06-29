import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"

const DELIVERY_FLOW_LOG_PREFIX = "[delivery-flow]"
const DELIVERY_FLOW_STORAGE_KEY = "delivery-flow-breadcrumbs"
const MAX_DELIVERY_FLOW_EVENTS = 180
const MAX_PERSISTED_DELIVERY_FLOW_BYTES = 1800
const MAX_PERSISTED_EVENT_COUNT = 24

type DeliveryFlowEventDetails = Record<string, unknown>

type DeliveryFlowEvent = {
    at: string
    details?: DeliveryFlowEventDetails
    label: string
}

type DeliveryFlowListener = (event: DeliveryFlowEvent, events: DeliveryFlowEvent[]) => void

const listeners = new Set<DeliveryFlowListener>()
const events: DeliveryFlowEvent[] = []

let writeQueue = Promise.resolve()
let hasLoadedPersistedEvents = false

function getWebStorage() {
    if (Platform.OS !== "web" || typeof window === "undefined" || !window.localStorage) {
        return null
    }

    return window.localStorage
}

async function readPersistedEventsPayload() {
    if (Platform.OS === "web") {
        return getWebStorage()?.getItem(DELIVERY_FLOW_STORAGE_KEY) ?? null
    }

    return SecureStore.getItemAsync(DELIVERY_FLOW_STORAGE_KEY)
}

async function writePersistedEventsPayload(payload: string) {
    if (Platform.OS === "web") {
        getWebStorage()?.setItem(DELIVERY_FLOW_STORAGE_KEY, payload)
        return
    }

    await SecureStore.setItemAsync(DELIVERY_FLOW_STORAGE_KEY, payload)
}

const notifyListeners = (event: DeliveryFlowEvent) => {
    const snapshot = getDeliveryFlowEventsSnapshot()
    listeners.forEach((listener) => {
        listener(event, snapshot)
    })
}

const loadPersistedEvents = () => {
    if (hasLoadedPersistedEvents) {
        return
    }

    hasLoadedPersistedEvents = true
    void readPersistedEventsPayload()
        .then((storedEvents) => {
            if (!storedEvents || events.length > 0) {
                return
            }

            const parsedEvents = JSON.parse(storedEvents) as DeliveryFlowEvent[]
            events.push(...parsedEvents.slice(-MAX_DELIVERY_FLOW_EVENTS))
            const latestEvent = getLatestDeliveryFlowEvent()
            if (latestEvent) {
                notifyListeners(latestEvent)
            }
        })
        .catch((error) => {
            console.warn(`${DELIVERY_FLOW_LOG_PREFIX} failed to load breadcrumb log`, error)
        })
}

const truncateString = (value: string) => (
    value.length > 180 ? `${value.slice(0, 177)}...` : value
)

const sanitizeDetailsForPersistence = (details: DeliveryFlowEventDetails | undefined) => {
    if (!details) {
        return undefined
    }

    const sanitizedDetails: DeliveryFlowEventDetails = {}
    Object.entries(details).forEach(([key, value]) => {
        if (value === null || typeof value === "boolean" || typeof value === "number") {
            sanitizedDetails[key] = value
            return
        }

        if (typeof value === "string") {
            sanitizedDetails[key] = truncateString(value)
            return
        }

        if (Array.isArray(value)) {
            sanitizedDetails[key] = `[array:${value.length}]`
            return
        }

        if (typeof value === "object") {
            sanitizedDetails[key] = "[object]"
        }
    })

    return sanitizedDetails
}

const getPersistedEventsPayload = () => {
    let persistedEvents = events.slice(-MAX_PERSISTED_EVENT_COUNT).map((event) => ({
        ...event,
        details: sanitizeDetailsForPersistence(event.details),
    }))
    let payload = JSON.stringify(persistedEvents)

    while (payload.length > MAX_PERSISTED_DELIVERY_FLOW_BYTES && persistedEvents.length > 1) {
        persistedEvents = persistedEvents.slice(1)
        payload = JSON.stringify(persistedEvents)
    }

    return payload
}

const persistEvents = () => {
    const payload = getPersistedEventsPayload()

    writeQueue = writeQueue
        .catch(() => undefined)
        .then(() => writePersistedEventsPayload(payload))
        .catch((error) => {
            console.warn(`${DELIVERY_FLOW_LOG_PREFIX} failed to persist breadcrumb log`, error)
        })
}

loadPersistedEvents()

export const getLatestDeliveryFlowEvent = () => events[events.length - 1] ?? null

export const getDeliveryFlowEventsSnapshot = () => [...events]

export const subscribeDeliveryFlowEvents = (listener: DeliveryFlowListener) => {
    loadPersistedEvents()
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

export const logDeliveryFlow = (label: string, details?: DeliveryFlowEventDetails) => {
    const event: DeliveryFlowEvent = {
        at: new Date().toISOString(),
        details,
        label,
    }

    events.push(event)
    if (events.length > MAX_DELIVERY_FLOW_EVENTS) {
        events.splice(0, events.length - MAX_DELIVERY_FLOW_EVENTS)
    }

    console.info(`${DELIVERY_FLOW_LOG_PREFIX} ${label}`, details ?? {})
    persistEvents()
    notifyListeners(event)
}
