import { Stack, usePathname } from "expo-router"
import { View } from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"

import StickyFooter from "@/components/footer/sticky-footer"
import AppHeader from "@/components/header/app-header"
import { appShellStyles } from "@/components/navigation/app-shell.styles"
import {
    getDefaultScreenChromeTemplate,
    mergeScreenChromeTemplate,
} from "@/components/navigation/screen-template-registry"
import { ScreenChromeTemplateProvider, useScreenChromeTemplate } from "@/providers/screen-chrome-template-provider"
import { useAuth } from "@/providers/auth-provider"
import { ScreenTemplateProvider } from "@/providers/screen-template-provider"

function AppShellContent() {
    const pathname = usePathname()
    const { isAuthenticated, isReady } = useAuth()
    const { screenChromeTemplate } = useScreenChromeTemplate()

    const chromeTemplate = mergeScreenChromeTemplate(
        getDefaultScreenChromeTemplate(pathname, isReady && isAuthenticated),
        screenChromeTemplate,
    )

    const shellEdges: ("top" | "bottom" | "left" | "right")[] =
        chromeTemplate.mode === "fullscreen" ? [] : ["top"]

    return (
        <SafeAreaView style={appShellStyles.container} edges={shellEdges}>
            {chromeTemplate.header !== "none" ? <AppHeader template={chromeTemplate} /> : null}

            <View style={appShellStyles.content}>
                <Stack screenOptions={{ headerShown: false }} />
            </View>

            {chromeTemplate.footer !== "none" ? <StickyFooter template={chromeTemplate} /> : null}
        </SafeAreaView>
    )
}

export default function AppShell() {
    return (
        <ScreenTemplateProvider>
            <ScreenChromeTemplateProvider>
                <AppShellContent />
            </ScreenChromeTemplateProvider>
        </ScreenTemplateProvider>
    )
}
