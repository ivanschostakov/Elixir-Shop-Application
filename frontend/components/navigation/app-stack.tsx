import { useContext } from "react"
import { Stack } from "expo-router"

import { renderRouteScreen } from "@/components/navigation/route-screen"
import { RouteTransitionContext } from "@/components/navigation/route-transition-context"
import { useTheme } from "@/providers/theme-provider"
import { motion } from "@/theme/motion"

/** Use the same native transition at the root and inside authenticated/guest groups. */
export function AppStack() {
    const { animation } = useContext(RouteTransitionContext)
    const { palette } = useTheme()
    return <Stack screenLayout={renderRouteScreen} screenOptions={{
        animation,
        animationDuration: motion.duration.route,
        contentStyle: { backgroundColor: palette.pageBackground },
        gestureEnabled: true,
        headerShown: false,
    }} />
}
