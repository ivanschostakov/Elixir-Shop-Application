import "expo-dev-client"

import { useEffect } from "react"
import { Asset } from "expo-asset"
import { router } from "expo-router"
import { AppState, Platform, StyleSheet, Text, View, type AppStateStatus } from "react-native"
import { GestureHandlerRootView } from "react-native-gesture-handler"

import AppShell from "@/components/navigation/app-shell"
import { AuthProvider } from "@/providers/auth-provider"
import { ThemeProvider } from "@/providers/theme-provider"
import { logDeliveryFlow } from "@/services/diagnostics/delivery-flow-logger"
import { attachPushOpenListener } from "@/services/notifications/order-status-notifications"

type GlobalErrorHandler = (error: unknown, isFatal?: boolean) => void

type ErrorUtilsLike = {
    getGlobalHandler?: () => GlobalErrorHandler
    setGlobalHandler?: (handler: GlobalErrorHandler) => void
}

const CHAT_BACKGROUND_ASSETS = [
    require("../assets/images/chat/chat-background-light.png"),
    require("../assets/images/chat/chat-background-dark.png"),
]

const getRootLogErrorMessage = (error: unknown) =>
    error instanceof Error ? error.message : String(error)

function WebTemporarilyDisabledScreen() {
    return (
        <View style={styles.webDisabledScreen}>
            <View style={styles.webDisabledCard}>
                <Text style={styles.webDisabledEyebrow}>Elixir Shop</Text>
                <Text style={styles.webDisabledTitle}>Web version is temporarily disabled</Text>
                <Text style={styles.webDisabledText}>
                    The app is currently being built mobile-first. Web will come back later when the product flow is finished.
                </Text>
            </View>
        </View>
    )
}

export default function RootLayout() {
    useEffect(() => {
        const errorUtils = (globalThis as typeof globalThis & { ErrorUtils?: ErrorUtilsLike }).ErrorUtils
        const previousGlobalErrorHandler = errorUtils?.getGlobalHandler?.()
        let previousAppState: AppStateStatus = AppState.currentState

        logDeliveryFlow("root mounted", {
            appState: previousAppState,
            platform: Platform.OS,
        })

        if (errorUtils?.setGlobalHandler) {
            errorUtils.setGlobalHandler((error, isFatal) => {
                logDeliveryFlow("global js error", {
                    error: getRootLogErrorMessage(error),
                    isFatal: Boolean(isFatal),
                })
                previousGlobalErrorHandler?.(error, isFatal)
            })
        }

        const appStateSubscription = AppState.addEventListener("change", (nextAppState) => {
            logDeliveryFlow("root app state changed", {
                from: previousAppState,
                to: nextAppState,
            })
            previousAppState = nextAppState
        })

        return () => {
            logDeliveryFlow("root unmounted", {
                appState: previousAppState,
                platform: Platform.OS,
            })
            appStateSubscription.remove()

            if (previousGlobalErrorHandler && errorUtils?.setGlobalHandler) {
                errorUtils.setGlobalHandler(previousGlobalErrorHandler)
            }
        }
    }, [])

    useEffect(() => {
        if (Platform.OS === "web") {
            return
        }

        void Asset.loadAsync(CHAT_BACKGROUND_ASSETS).catch(() => undefined)
    }, [])

    useEffect(() => {
        if (Platform.OS === "web") {
            return
        }

        return attachPushOpenListener((target) => {
            router.push(target)
        })
    }, [])

    if (Platform.OS === "web") {
        return (
            <GestureHandlerRootView style={styles.root}>
                <ThemeProvider>
                    <WebTemporarilyDisabledScreen />
                </ThemeProvider>
            </GestureHandlerRootView>
        )
    }

    return (
        <GestureHandlerRootView style={styles.root}>
            <ThemeProvider>
                <AuthProvider>
                    <AppShell />
                </AuthProvider>
            </ThemeProvider>
        </GestureHandlerRootView>
    )
}

const styles = StyleSheet.create({
    root: {
        flex: 1,
    },
    webDisabledScreen: {
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#f8fafc",
        paddingHorizontal: 24,
    },
    webDisabledCard: {
        width: "100%",
        maxWidth: 520,
        borderRadius: 28,
        paddingHorizontal: 28,
        paddingVertical: 32,
        backgroundColor: "#ffffff",
        borderWidth: 1,
        borderColor: "rgba(17, 24, 39, 0.08)",
    },
    webDisabledEyebrow: {
        color: "#6b7280",
        fontSize: 12,
        fontWeight: "700",
        letterSpacing: 0.4,
        textTransform: "uppercase",
        marginBottom: 10,
    },
    webDisabledTitle: {
        color: "#111827",
        fontSize: 28,
        fontWeight: "800",
        lineHeight: 34,
        marginBottom: 12,
    },
    webDisabledText: {
        color: "#4b5563",
        fontSize: 16,
        lineHeight: 24,
    },
})
