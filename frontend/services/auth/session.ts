import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"
import { AUTH_TOKENS_STORAGE_KEY } from "@/services/auth/session.constants"
import type { AuthTokens, RefreshHandler, SessionListener } from "@/services/auth/session.types"

export type { AuthTokens } from "@/services/auth/session.types"

function getWebStorage() {
    if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
        return null
    }

    return window.localStorage
}

function parseStoredAuthTokens(rawTokens: string | null): AuthTokens | null {
    if (!rawTokens) {
        return null
    }

    try {
        const parsedTokens = JSON.parse(rawTokens)

        if (
            typeof parsedTokens === "object" &&
            parsedTokens !== null &&
            typeof parsedTokens.accessToken === "string" &&
            typeof parsedTokens.refreshToken === "string" &&
            typeof parsedTokens.sessionId === "number"
        ) {
            return parsedTokens as AuthTokens
        }
    } catch {
        return null
    }

    return null
}

function readWebStoredAuthTokens(): AuthTokens | null {
    const storage = getWebStorage()

    if (!storage) {
        return null
    }

    return parseStoredAuthTokens(storage.getItem(AUTH_TOKENS_STORAGE_KEY))
}

async function readStoredAuthTokens(): Promise<AuthTokens | null> {
    if (Platform.OS === "web") {
        return readWebStoredAuthTokens()
    }

    try {
        return parseStoredAuthTokens(await SecureStore.getItemAsync(AUTH_TOKENS_STORAGE_KEY))
    } catch {
        return null
    }
}

function persistWebAuthTokens(tokens: AuthTokens | null) {
    const storage = getWebStorage()

    if (!storage) {
        return
    }

    try {
        if (!tokens) {
            storage.removeItem(AUTH_TOKENS_STORAGE_KEY)
            return
        }

        storage.setItem(AUTH_TOKENS_STORAGE_KEY, JSON.stringify(tokens))
    } catch {
        // Ignore storage issues and keep the in-memory session alive.
    }
}

async function persistAuthTokens(tokens: AuthTokens | null) {
    if (Platform.OS === "web") {
        persistWebAuthTokens(tokens)
        return
    }

    try {
        if (!tokens) {
            await SecureStore.deleteItemAsync(AUTH_TOKENS_STORAGE_KEY)
            return
        }

        await SecureStore.setItemAsync(AUTH_TOKENS_STORAGE_KEY, JSON.stringify(tokens))
    } catch {
        // Ignore storage issues and keep the in-memory session alive.
    }
}

let currentTokens: AuthTokens | null = null
let hasHydratedTokens = false
let refreshHandler: RefreshHandler | null = null
let refreshRequest: Promise<AuthTokens | null> | null = null

const listeners = new Set<SessionListener>()

function notifyListeners() {
    for (const listener of listeners) {
        listener(currentTokens)
    }
}

export function getAuthTokens() {
    return currentTokens
}

export async function hydrateAuthTokens() {
    if (hasHydratedTokens) {
        return currentTokens
    }

    currentTokens = await readStoredAuthTokens()
    hasHydratedTokens = true
    notifyListeners()
    return currentTokens
}

export function setAuthTokens(tokens: AuthTokens | null) {
    currentTokens = tokens
    hasHydratedTokens = true
    void persistAuthTokens(tokens)
    notifyListeners()
}

export function clearAuthTokens() {
    setAuthTokens(null)
}

export function subscribeAuthSession(listener: SessionListener) {
    listeners.add(listener)

    return () => {
        listeners.delete(listener)
    }
}

export function setRefreshHandler(handler: RefreshHandler | null) {
    refreshHandler = handler
}

export async function refreshAuthTokens() {
    if (!refreshHandler) {
        return null
    }

    if (!refreshRequest) {
        refreshRequest = refreshHandler().finally(() => {
            refreshRequest = null
        })
    }

    return refreshRequest
}
