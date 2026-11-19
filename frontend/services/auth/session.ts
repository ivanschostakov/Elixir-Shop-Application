import * as SecureStore from "expo-secure-store"
import { Platform } from "react-native"
import { AUTH_TOKENS_STORAGE_KEY, AUTH_USER_STORAGE_KEY } from "@/services/auth/session.constants"
import type { AuthTokens, RefreshHandler, SessionListener } from "@/services/auth/session.types"
import type { AuthUser } from "@/services/auth/auth.types"

export type { AuthTokens } from "@/services/auth/session.types"

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
    if (typeof window === "undefined" || !window.localStorage) {
        return null
    }

    return parseStoredAuthTokens(window.localStorage.getItem(AUTH_TOKENS_STORAGE_KEY))
}

function parseStoredAuthUser(rawUser: string | null): AuthUser | null {
    if (!rawUser) return null
    try {
        const user = JSON.parse(rawUser)
        return typeof user === "object" && user !== null && typeof user.id === "number"
            ? user as AuthUser
            : null
    } catch {
        return null
    }
}

export async function readCachedAuthUser(): Promise<AuthUser | null> {
    try {
        if (Platform.OS === "web") {
            return typeof window !== "undefined" && window.localStorage
                ? parseStoredAuthUser(window.localStorage.getItem(AUTH_USER_STORAGE_KEY))
                : null
        }
        return parseStoredAuthUser(await SecureStore.getItemAsync(AUTH_USER_STORAGE_KEY))
    } catch {
        return null
    }
}

async function persistNativeAuthUser(user: AuthUser | null) {
    try {
        if (user) await SecureStore.setItemAsync(AUTH_USER_STORAGE_KEY, JSON.stringify(user))
        else await SecureStore.deleteItemAsync(AUTH_USER_STORAGE_KEY)
    } catch {
        // The live session remains usable even if the display cache is unavailable.
    }
}

export function cacheAuthUser(user: AuthUser | null) {
    if (Platform.OS === "web") {
        try {
            if (typeof window === "undefined" || !window.localStorage) return
            if (user) window.localStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(user))
            else window.localStorage.removeItem(AUTH_USER_STORAGE_KEY)
        } catch {
            // The live session remains usable even if the display cache is unavailable.
        }
        return
    }
    void persistNativeAuthUser(user)
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
    if (typeof window === "undefined" || !window.localStorage) {
        return
    }

    if (!tokens) {
        window.localStorage.removeItem(AUTH_TOKENS_STORAGE_KEY)
        return
    }

    window.localStorage.setItem(AUTH_TOKENS_STORAGE_KEY, JSON.stringify(tokens))
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
    cacheAuthUser(null)
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
