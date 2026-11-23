import { useEffect, useMemo, useState } from "react"
import { usePathname } from "expo-router"
import { DarkTheme, DefaultTheme, ThemeProvider as NavigationThemeProvider } from "@react-navigation/native"
import { Image, Platform, Text, View } from "react-native"
import { AppStack } from "@/components/navigation/app-stack"
import { createAppShellStyles } from "@/components/navigation/app-shell.styles"
import { RouteTransitionContext, type RouteAnimation } from "@/components/navigation/route-transition-context"
import { ROUTES } from "@/constants/routes"
import { useTheme } from "@/providers/theme-provider"
import { useAppSafeAreaInsets } from "@/hooks/use-app-safe-area-insets"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { setTelegramChromeColors } from "@/services/telegram/telegram-web-app"
import { darkColors, lightColors } from "@/theme/colors"

function AppShellContent() {
    const appShellStyles = useThemeStyles(createAppShellStyles)
    const pathname = usePathname()
    const { top: topInset } = useAppSafeAreaInsets()
    const { accentPalette, isDark } = useTheme()
    const [routeAnimation, setRouteAnimation] = useState<RouteAnimation>("slide_from_right")
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

    const transitionContext = useMemo(() => ({ animation: routeAnimation, setAnimation: setRouteAnimation }), [routeAnimation])
    const shouldShowBrandOverlay = Platform.OS === "ios"
    const brandLabelTop = Math.max(2, topInset - 44)
    useEffect(() => {
        if (Platform.OS !== "web") {
            return
        }

        setTelegramChromeColors({
            backgroundColor: palette.pageBackground,
            bottomBarColor: palette.background,
            headerColor: pathname === ROUTES.home ? accentPalette.primary : palette.background,
        })
    }, [accentPalette.primary, palette.background, palette.pageBackground, pathname])

    return (
        <View style={appShellStyles.container}>
            {shouldShowBrandOverlay ? (
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

            <RouteTransitionContext.Provider value={transitionContext}>
                <NavigationThemeProvider value={navigationTheme}>
                    <AppStack />
                </NavigationThemeProvider>
            </RouteTransitionContext.Provider>
        </View>
    )
}

export default function AppShell() {
    return <AppShellContent />
}
