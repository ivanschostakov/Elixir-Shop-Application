import type { ReactNode } from "react"
import { KeyboardAvoidingView, Platform, StyleSheet, type StyleProp, type ViewStyle } from "react-native"

/** Own keyboard avoidance once, from the fullscreen origin, including the header. */
export function ChatKeyboardLayout({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
    return <KeyboardAvoidingView
        testID="chat-keyboard-layout"
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        enabled={Platform.OS === "ios"}
        keyboardVerticalOffset={0}
        style={[styles.screen, style]}
    >{children}</KeyboardAvoidingView>
}
const styles = StyleSheet.create({ screen: { flex: 1, minHeight: 0 } })
