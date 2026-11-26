import { forwardRef, useEffect, useState } from "react"
import { Keyboard, ScrollView, StyleSheet, View, type ViewProps } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { AppEdgeMaterial } from "@/components/platform/app-edge-material"
import { useTheme } from "@/providers/theme-provider"

// Play build 6 uses adjustResize, so Android already sizes the conversation above the IME.
export function ChatKeyboardPane({ children, style }: ViewProps) {
    return <View style={[styles.pane, style]}>{children}</View>
}

export const ChatMessageScrollView = ScrollView
export const ChatKeyboardFloating = View

export const ChatComposerDock = forwardRef<View, ViewProps>(function ChatComposerDock({ children, style, ...props }, ref) {
    const { bottom } = useSafeAreaInsets()
    const { isDark } = useTheme()
    const [keyboardVisible, setKeyboardVisible] = useState(() => Keyboard.isVisible())

    useEffect(() => {
        const show = Keyboard.addListener("keyboardDidShow", () => setKeyboardVisible(true))
        const hide = Keyboard.addListener("keyboardDidHide", () => setKeyboardVisible(false))
        return () => { show.remove(); hide.remove() }
    }, [])

    return <View {...props} ref={ref} style={[style, styles.dock, { paddingBottom: keyboardVisible ? 8 : Math.max(bottom, 8) }]}>
        <AppEdgeMaterial dark={isDark} style={styles.material} />
        {children}
    </View>
})

const styles = StyleSheet.create({
    pane: { flex: 1, minHeight: 0 },
    dock: { width: "100%", flexShrink: 0, paddingHorizontal: 8, paddingTop: 6 },
    material: { ...StyleSheet.absoluteFillObject, top: -10 },
})
