import { useContext, type ReactElement, type ReactNode } from "react"
import { useRouter } from "expo-router"
import { Platform, View } from "react-native"
import { PanGestureHandler, State, type PanGestureHandlerStateChangeEvent } from "react-native-gesture-handler"
import { SafeAreaView } from "react-native-safe-area-context"

import StickyFooter from "@/components/footer/sticky-footer"
import AppHeader from "@/components/header/app-header"
import { createAppShellStyles } from "@/components/navigation/app-shell.styles"
import { NativeRouteTransitionContext, RouteTransitionContext } from "@/components/navigation/route-transition-context"
import { getScreenPathname } from "@/components/navigation/route-screen-path"
import { getDefaultScreenChromeTemplate, mergeScreenChromeTemplate } from "@/components/navigation/screen-template-registry"
import { PRIMARY_APP_ROUTES, ROUTES } from "@/constants/routes"
import { useAppSafeAreaInsets } from "@/hooks/use-app-safe-area-insets"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useAuth } from "@/providers/auth-provider"
import { useLanguage } from "@/providers/language-provider"
import { ScreenChromeTemplateProvider, useScreenChromeTemplate } from "@/providers/screen-chrome-template-provider"
import { ScreenTemplateProvider } from "@/providers/screen-template-provider"

/** Chrome lives inside the native screen, so an entering route cannot resize the outgoing one. */
function RouteScreenContent({ children, pathname }: { children: ReactNode; pathname: string }) {
    useLanguage()
    const styles = useThemeStyles(createAppShellStyles)
    const { top } = useAppSafeAreaInsets()
    const { isAuthenticated, isReady } = useAuth()
    const { screenChromeTemplate } = useScreenChromeTemplate()
    const { setAnimation } = useContext(RouteTransitionContext)
    const router = useRouter()
    const template = mergeScreenChromeTemplate(getDefaultScreenChromeTemplate(pathname, isReady && isAuthenticated), screenChromeTemplate)
    const edges: "top"[] = template.mode === "fullscreen" || pathname === ROUTES.home ? [] : ["top"]
    const primaryAppRoutes = PRIMARY_APP_ROUTES
    const index = primaryAppRoutes.findIndex(route => route === pathname)

    const handleSwipe = (event: PanGestureHandlerStateChangeEvent) => {
        if (index < 0 || event.nativeEvent.state !== State.END) return
        const { translationX, velocityX } = event.nativeEvent
        const left = translationX < -70 || velocityX < -650
        const right = translationX > 70 || velocityX > 650
        if (!left && !right) return
        const next = Math.max(0, Math.min(index + (left ? 1 : -1), primaryAppRoutes.length - 1))
        if (next === index) return
        setAnimation(left ? "slide_from_right" : "slide_from_left")
        router.replace(primaryAppRoutes[next])
    }

    return <SafeAreaView style={[styles.safeArea, Platform.OS === "web" && edges.length ? { paddingTop: top } : null]} edges={Platform.OS === "web" ? [] : edges}>
        {template.header !== "none" ? <AppHeader pathname={pathname} template={template} /> : null}
        <PanGestureHandler activeOffsetX={[-40, 40]} enabled={index >= 0} failOffsetY={[-24, 24]} onHandlerStateChange={handleSwipe}>
            <View style={styles.content}>{children}</View>
        </PanGestureHandler>
        {template.footer !== "none" ? <StickyFooter pathname={pathname} template={template} /> : null}
    </SafeAreaView>
}

export function renderRouteScreen({ route, children }: { route: { name: string; params?: object }; children: ReactElement }) {
    const pathname = getScreenPathname(route.name, route.params)
    // Nested navigators supply a surface for each leaf, rather than wrapping the entire group twice.
    if (pathname === null) return children
    return <NativeRouteTransitionContext.Provider value={Platform.OS !== "web"}>
        <ScreenTemplateProvider><ScreenChromeTemplateProvider>
            <RouteScreenContent pathname={pathname}>{children}</RouteScreenContent>
        </ScreenChromeTemplateProvider></ScreenTemplateProvider>
    </NativeRouteTransitionContext.Provider>
}
