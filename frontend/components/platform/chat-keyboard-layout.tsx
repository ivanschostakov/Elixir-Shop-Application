import { useEffect, useRef, type ReactNode } from "react"
import { Animated, Dimensions, Keyboard, Platform, StyleSheet, View, type StyleProp, type ViewStyle } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { AppEdgeMaterial as ChatEdgeBlur } from "@/components/platform/app-edge-material"
import { NativeChatKeyboardMaterial } from "@/components/platform/native-controls"

/** Keep screen and header geometry fixed; each conversation follows the keyboard on the UI thread. */
export function ChatKeyboardLayout({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
    const { isDark } = useTheme()
    const keyboardFill = useRef(new Animated.Value(0)).current
    useEffect(() => {
        if (Platform.OS !== "ios" || NativeChatKeyboardMaterial) return
        const update = (height: number, duration: number) => {
            // This backing stays in the full-screen layer, below the resized
            // conversation. It fills the exposed corners of the floating keyboard.
            Animated.timing(keyboardFill, { toValue: height, duration, useNativeDriver: false }).start()
        }
        const frame = Keyboard.addListener("keyboardWillChangeFrame", event => {
            const height = Math.max(0, Dimensions.get("screen").height - event.endCoordinates.screenY)
            update(height, event.duration)
        })
        const hide = Keyboard.addListener("keyboardWillHide", event => update(0, event.duration))
        return () => { frame.remove(); hide.remove() }
    }, [keyboardFill])
    return <View style={[styles.screen, style]}>
        {NativeChatKeyboardMaterial ? <NativeChatKeyboardMaterial dark={isDark} pointerEvents="none" style={StyleSheet.absoluteFill} /> : Platform.OS === "ios" ? <Animated.View testID="chat-keyboard-corner-fill" pointerEvents="none" style={[styles.keyboardFill, { height: keyboardFill }]}><ChatEdgeBlur dark={isDark} style={styles.material} /></Animated.View> : null}
        <View
        testID="chat-keyboard-layout"
        style={styles.screen}
    >{children}</View>
    </View>
}
const styles = StyleSheet.create({
    screen: { flex: 1, minHeight: 0 },
    keyboardFill: { position: "absolute", bottom: 0, left: 0, right: 0, overflow: "hidden" },
    material: { ...StyleSheet.absoluteFillObject, top: -32 },
})
