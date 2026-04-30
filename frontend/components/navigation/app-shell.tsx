import { Stack, usePathname } from "expo-router"
import { Image, Text, View } from "react-native"
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context"

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
    const { top: topInset } = useSafeAreaInsets()
    const { isAuthenticated, isReady } = useAuth()
    const { screenChromeTemplate } = useScreenChromeTemplate()

    const chromeTemplate = mergeScreenChromeTemplate(
        getDefaultScreenChromeTemplate(pathname, isReady && isAuthenticated),
        screenChromeTemplate,
    )

    const shellEdges: ("top" | "bottom" | "left" | "right")[] =
        chromeTemplate.mode === "fullscreen" ? [] : ["top"]
    const brandLabelTop = Math.max(2, topInset - 44)

    return (
        <View style={appShellStyles.container}>
            <View
                pointerEvents="none"
                style={[appShellStyles.brandLabelOverlay, { top: brandLabelTop }]}
            >
                <View style={appShellStyles.brandLabelPill}>
                    <Image
                        source={require("@/assets/icons/dynamic-island.png")}
                        resizeMode="contain"
                        style={appShellStyles.brandLabelImage}
                    />
                    <Text numberOfLines={1} style={appShellStyles.brandLabelText}>
                        ElixirPeptide
                    </Text>
                </View>
            </View>

            <SafeAreaView style={appShellStyles.safeArea} edges={shellEdges}>
                {chromeTemplate.header !== "none" ? <AppHeader template={chromeTemplate} /> : null}

                <View style={appShellStyles.content}>
                    <Stack screenOptions={{ headerShown: false }} />
                </View>

                {chromeTemplate.footer !== "none" ? <StickyFooter template={chromeTemplate} /> : null}
            </SafeAreaView>
        </View>
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
