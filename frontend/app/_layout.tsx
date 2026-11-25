import { ActionSheetProvider } from "@expo/react-native-action-sheet"
import { useEffect } from "react"
import { Asset } from "expo-asset"
import { AppState, Platform, type AppStateStatus } from "react-native"
import { GestureHandlerRootView } from "react-native-gesture-handler"
import { SafeAreaProvider } from "react-native-safe-area-context"
import { AppKeyboardProvider } from "@/components/platform/app-keyboard-provider"
import { PlayUpdateGate } from "@/components/navigation/play-update-gate"

import AppShell from "@/components/navigation/app-shell"
import { VersionGate } from "@/components/navigation/version-gate"
import { TelegramWebAppGate } from "@/components/telegram/telegram-web-app-gate"
import { AuthProvider } from "@/providers/auth-provider"
import { AiConsentProvider } from "@/providers/ai-consent-provider"
import { LanguageProvider } from "@/providers/language-provider"
import { ThemeProvider, useTheme } from "@/providers/theme-provider"
import { logDeliveryFlow } from "@/services/diagnostics/delivery-flow-logger"
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

function RootLayoutContent() {
    const { themeName } = useTheme()
    const rootThemeStyle = themeName === "dark" ? rootLayoutStyles.rootDark : rootLayoutStyles.rootLight

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

    return (
        <GestureHandlerRootView style={[rootLayoutStyles.root, rootThemeStyle]}>
            <SafeAreaProvider>
                <AppKeyboardProvider>
                    <LanguageProvider>
                        <PlayUpdateGate>
                            <ActionSheetProvider>
                                <VersionGate>
                                    <AuthProvider>
                                        <TelegramWebAppGate>
                                            <AiConsentProvider><AppShell /></AiConsentProvider>
                                        </TelegramWebAppGate>
                                    </AuthProvider>
                                </VersionGate>
                            </ActionSheetProvider>
                        </PlayUpdateGate>
                    </LanguageProvider>
                </AppKeyboardProvider>
            </SafeAreaProvider>
        </GestureHandlerRootView>
    )
}

export default function RootLayout() {
    return (
        <ThemeProvider>
            <RootLayoutContent />
        </ThemeProvider>
    )
}
