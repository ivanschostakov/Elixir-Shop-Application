import "expo-dev-client"

import { useEffect } from "react"
import { Asset } from "expo-asset"
import { router } from "expo-router"
import { AppState, Platform, Text, View, useColorScheme, type AppStateStatus } from "react-native"
import { GestureHandlerRootView } from "react-native-gesture-handler"

import AppShell from "@/components/navigation/app-shell"
import { VersionGate } from "@/components/navigation/version-gate"
import { AuthProvider } from "@/providers/auth-provider"
import { ThemeProvider } from "@/providers/theme-provider"
import { logDeliveryFlow } from "@/services/diagnostics/delivery-flow-logger"
import { attachPushOpenListener } from "@/services/notifications/order-status-notifications"
import { rootLayoutStyles } from "@/components/navigation/root-layout.styles"

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
        <View style={rootLayoutStyles.webDisabledScreen}>
            <View style={rootLayoutStyles.webDisabledCard}>
                <Text style={rootLayoutStyles.webDisabledEyebrow}>Elixir Shop</Text>
                <Text style={rootLayoutStyles.webDisabledTitle}>Web version is temporarily disabled</Text>
                <Text style={rootLayoutStyles.webDisabledText}>
                    The app is currently being built mobile-first. Web will come back later when the product flow is finished.
                </Text>
            </View>
        </View>
    )
}

export default function RootLayout() {
    const colorScheme = useColorScheme()
    const rootThemeStyle = colorScheme === "dark" ? rootLayoutStyles.rootDark : rootLayoutStyles.rootLight

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
            <GestureHandlerRootView style={[rootLayoutStyles.root, rootThemeStyle]}>
                <ThemeProvider>
                    <WebTemporarilyDisabledScreen />
                </ThemeProvider>
            </GestureHandlerRootView>
        )
    }

    return (
        <GestureHandlerRootView style={[rootLayoutStyles.root, rootThemeStyle]}>
            <ThemeProvider>
                <VersionGate>
                    <AuthProvider>
                        <AppShell />
                    </AuthProvider>
                </VersionGate>
            </ThemeProvider>
        </GestureHandlerRootView>
    )
}
