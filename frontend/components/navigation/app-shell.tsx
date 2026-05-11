import { useMemo, useState } from "react"
import { Stack, usePathname, useRouter } from "expo-router"
import { DarkTheme, DefaultTheme, ThemeProvider as NavigationThemeProvider } from "@react-navigation/native"
import { LinearGradient } from "expo-linear-gradient"
import { Image, Platform, Text, View } from "react-native"
import {
    PanGestureHandler,
    State,
    type PanGestureHandlerStateChangeEvent,
} from "react-native-gesture-handler"
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context"

import StickyFooter from "@/components/footer/sticky-footer"
import AppHeader from "@/components/header/app-header"
import { appShellStyles } from "@/components/navigation/app-shell.styles"
import {
    getDefaultScreenChromeTemplate,
    mergeScreenChromeTemplate,
} from "@/components/navigation/screen-template-registry"
import { PRIMARY_APP_ROUTES, ROUTES } from "@/constants/routes"
import { ScreenChromeTemplateProvider, useScreenChromeTemplate } from "@/providers/screen-chrome-template-provider"
import { useTheme } from "@/providers/theme-provider"
import { useAuth } from "@/providers/auth-provider"
import { ScreenTemplateProvider } from "@/providers/screen-template-provider"
import { darkColors, lightColors } from "@/theme/colors"
import { motion } from "@/theme/motion"

function AppShellContent() {
    const pathname = usePathname()
    const router = useRouter()
    const { top: topInset } = useSafeAreaInsets()
    const { isDark } = useTheme()
    const { isAuthenticated, isReady } = useAuth()
    const { screenChromeTemplate } = useScreenChromeTemplate()
    const [routeAnimation, setRouteAnimation] = useState<"slide_from_left" | "slide_from_right">("slide_from_right")
    const palette = isDark ? darkColors : lightColors
    const navigationTheme = useMemo(
        () => ({
            ...(isDark ? DarkTheme : DefaultTheme),
            colors: {
                ...(isDark ? DarkTheme.colors : DefaultTheme.colors),
                background: palette.pageBackground,
                border: palette.border,
                card: palette.surface,
                notification: palette.favorite,
                primary: palette.primary,
                text: palette.text,
            },
        }),
        [isDark, palette],
    )

    const chromeTemplate = mergeScreenChromeTemplate(
        getDefaultScreenChromeTemplate(pathname, isReady && isAuthenticated),
        screenChromeTemplate,
    )
    const isDiscoverRoute = pathname === ROUTES.discover

    const shellEdges: ("top" | "bottom" | "left" | "right")[] =
        chromeTemplate.mode === "fullscreen"
            ? []
            : pathname === ROUTES.home
              ? []
              : ["top"]
    const hasDynamicIsland = Platform.OS === "ios" && topInset >= 51
    const brandLabelTop = Math.max(2, topInset - 44)
    const currentPrimaryRouteIndex = PRIMARY_APP_ROUTES.findIndex((route) => route === pathname)
    const canSwipePrimaryRoutes = currentPrimaryRouteIndex >= 0

    const handlePrimaryRouteSwipe = (event: PanGestureHandlerStateChangeEvent) => {
        if (!canSwipePrimaryRoutes || event.nativeEvent.state !== State.END) {
            return
        }

        const { translationX, velocityX } = event.nativeEvent
        const isSwipeLeft = translationX < -70 || velocityX < -650
        const isSwipeRight = translationX > 70 || velocityX > 650

        if (!isSwipeLeft && !isSwipeRight) {
            return
        }

        const nextRouteIndex = isSwipeLeft
            ? Math.min(currentPrimaryRouteIndex + 1, PRIMARY_APP_ROUTES.length - 1)
            : Math.max(currentPrimaryRouteIndex - 1, 0)

        if (nextRouteIndex === currentPrimaryRouteIndex) {
            return
        }

        setRouteAnimation(isSwipeLeft ? "slide_from_right" : "slide_from_left")
        requestAnimationFrame(() => {
            router.replace(PRIMARY_APP_ROUTES[nextRouteIndex])
        })
    }

    return (
        <View style={appShellStyles.container}>
            {isDiscoverRoute ? (
                <LinearGradient
                    colors={["#FF6F93", "#FF88B0", "#FFC96B"]}
                    end={{ x: 1, y: 0 }}
                    start={{ x: 0, y: 0 }}
                    pointerEvents="none"
                    style={[appShellStyles.discoverTopGradient, { height: topInset + 1 }]}
                />
            ) : null}
            {hasDynamicIsland ? (
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
            ) : null}

            <SafeAreaView style={appShellStyles.safeArea} edges={shellEdges}>
                {chromeTemplate.header !== "none" ? <AppHeader template={chromeTemplate} /> : null}

                <PanGestureHandler
                    activeOffsetX={[-40, 40]}
                    enabled={canSwipePrimaryRoutes}
                    failOffsetY={[-24, 24]}
                    onHandlerStateChange={handlePrimaryRouteSwipe}
                >
                    <View style={appShellStyles.content}>
                        <NavigationThemeProvider value={navigationTheme}>
                            <Stack
                                screenOptions={{
                                    animation: routeAnimation,
                                    animationDuration: motion.duration.route,
                                    contentStyle: { backgroundColor: palette.pageBackground },
                                    gestureEnabled: true,
                                    headerShown: false,
                                }}
                            />
                        </NavigationThemeProvider>
                    </View>
                </PanGestureHandler>

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
