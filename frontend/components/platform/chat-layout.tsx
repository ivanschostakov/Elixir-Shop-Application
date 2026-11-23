import { createContext, forwardRef, useContext, useEffect, useState, type ReactNode } from "react"
import { Keyboard, Platform, ScrollView, StyleSheet, View, type ScrollViewProps, type ViewProps } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { KeyboardChatScrollView, KeyboardStickyView, useReanimatedKeyboardAnimation } from "react-native-keyboard-controller"
import Reanimated, { useAnimatedStyle, useDerivedValue, useSharedValue, type SharedValue } from "react-native-reanimated"
import { useTheme } from "@/providers/theme-provider"
import { AppEdgeMaterial as ChatEdgeBlur } from "@/components/platform/app-edge-material"

type Geometry = { dock: SharedValue<number>; padding: SharedValue<number> }
const ComposerGeometry = createContext<Geometry | null>(null)

/** Separate geometry for each retained conversation, sharing the system keyboard clock. */
export function ChatKeyboardPane({ children, style }: { children: ReactNode; style?: ViewProps["style"] }) {
    const dock = useSharedValue(0)
    const { bottom } = useSafeAreaInsets()
    const { progress } = useReanimatedKeyboardAnimation()
    const padding = useDerivedValue(() => Math.max(0, dock.value - (dock.value > 0 ? progress.value * Math.max(0, bottom - 8) : 0)))
    return <ComposerGeometry.Provider value={{ dock, padding }}><View style={[styles.pane, style]}>{children}</View></ComposerGeometry.Provider>
}

export const ChatMessageScrollView = forwardRef<ScrollView, ScrollViewProps>(function ChatMessageScrollView(props, ref) {
    const geometry = useContext(ComposerGeometry)
    if (Platform.OS !== "ios") return <ScrollView {...props} ref={ref} />
    return <KeyboardChatScrollView {...props} ref={ref} automaticallyAdjustKeyboardInsets={false} contentInsetAdjustmentBehavior="never" extraContentPadding={geometry?.padding} keyboardLiftBehavior="always" scrollIndicatorInsets={{ ...props.scrollIndicatorInsets, bottom: 0 }} />
})

export const ChatComposerDock = forwardRef<View, ViewProps>(function ChatComposerDock({ children, onLayout, style, ...props }, ref) {
    const geometry = useContext(ComposerGeometry)
    const dock = geometry?.dock
    useEffect(() => () => { if (dock) dock.value = 0 }, [dock])
    const { bottom } = useSafeAreaInsets()
    const { isDark } = useTheme()
    const [keyboardVisible, setKeyboardVisible] = useState(false)
    useEffect(() => {
        if (Platform.OS === "ios") return
        const show = Keyboard.addListener("keyboardDidShow", () => setKeyboardVisible(true))
        const hide = Keyboard.addListener("keyboardDidHide", () => setKeyboardVisible(false))
        return () => { show.remove(); hide.remove() }
    }, [])
    const handleLayout: ViewProps["onLayout"] = event => {
        if (dock) dock.value = event.nativeEvent.layout.height
        onLayout?.(event)
    }
    const dockStyle = [style, styles.dock, { paddingBottom: keyboardVisible ? 8 : Math.max(bottom, 8) }]
    if (Platform.OS !== "ios") return <View {...props} style={dockStyle} onLayout={handleLayout} ref={ref}>{children}</View>
    return <KeyboardStickyView {...props} style={[dockStyle, styles.iosDock]} onLayout={handleLayout} ref={ref} offset={{ opened: Math.max(0, bottom - 8) }}>
        <ChatEdgeBlur dark={isDark} style={styles.material} />
        {children}
    </KeyboardStickyView>
})

export function ChatKeyboardFloating(props: ViewProps) {
    const { bottom } = useSafeAreaInsets()
    const { height, progress } = useReanimatedKeyboardAnimation()
    const motion = useAnimatedStyle(() => ({ transform: [{ translateY: height.value + progress.value * Math.max(0, bottom - 8) }] }))
    if (Platform.OS !== "ios") return <View {...props} />
    return <Reanimated.View {...props} style={[props.style, motion]} />
}

const styles = StyleSheet.create({
    pane: { flex: 1, minHeight: 0 },
    dock: { left: 0, right: 0, bottom: 0, width: "100%", paddingHorizontal: 8, paddingTop: 6, flexShrink: 0 },
    iosDock: { position: "absolute" },
    material: { ...StyleSheet.absoluteFillObject, top: -10 },
})
