import { requireOptionalNativeModule } from "expo"
import { Platform, StyleSheet, View, type ViewProps } from "react-native"
import { BlurView } from "expo-blur"
import Animated, { Easing, ReduceMotion, useAnimatedStyle, withTiming } from "react-native-reanimated"
import type * as Glass from "expo-glass-effect"

// Older installed binaries can still open the JS fallback while native dependencies are rebuilt.
const glass: typeof Glass | null = Platform.OS === "ios" && requireOptionalNativeModule("ExpoGlassEffect")
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- Load only after checking the installed native binary.
    ? require("expo-glass-effect") : null
type Props = ViewProps & { dark: boolean; fallbackColor: string; tintColor?: string; radius?: number; interactive?: boolean }

export function AppSurface({ dark, fallbackColor, tintColor, radius = 22, interactive = false, style, ...props }: Props) {
    const shape = { borderRadius: radius, overflow: "hidden" as const }
    if (glass?.isLiquidGlassAvailable() && glass.isGlassEffectAPIAvailable()) {
        return <glass.GlassView {...props} colorScheme={dark ? "dark" : "light"} tintColor={tintColor} isInteractive={interactive} style={[shape, style]} />
    }
    if (Platform.OS === "ios") return <BlurView {...props} intensity={70} tint={dark ? "systemThinMaterialDark" : "systemThinMaterialLight"} style={[shape, style]} />
    return <View {...props} style={[shape, { backgroundColor: fallbackColor }, style]} />
}

export function AppComposerSurface({ dark, joined, fallbackColor, borderColor }: { dark: boolean; joined: boolean; fallbackColor: string; borderColor: string }) {
    const geometry = useAnimatedStyle(() => ({ right: withTiming(joined ? 0 : 50, { duration: 320, easing: Easing.out(Easing.cubic), reduceMotion: ReduceMotion.System }) }))
    return <Animated.View pointerEvents="none" style={[StyleSheet.absoluteFill, geometry]}>
        <AppSurface dark={dark} fallbackColor={fallbackColor} tintColor={dark ? "rgba(38,48,64,0.55)" : "rgba(242,250,245,0.55)"} pointerEvents="none" style={[StyleSheet.absoluteFill, { borderWidth: StyleSheet.hairlineWidth, borderColor }]} />
    </Animated.View>
}
