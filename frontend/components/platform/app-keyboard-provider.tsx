import type { PropsWithChildren } from "react"
import { Platform } from "react-native"
import { KeyboardProvider } from "react-native-keyboard-controller"

export function AppKeyboardProvider({ children }: PropsWithChildren) {
    return <KeyboardProvider enabled={Platform.OS === "ios"} preload={false}>{children}</KeyboardProvider>
}
