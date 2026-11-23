import { requireNativeView, requireOptionalNativeModule } from "expo"
import { Platform, type ViewProps } from "react-native"

const moduleName = "ElixirChatControls"
const nativeModule = Platform.OS === "ios" ? requireOptionalNativeModule<{ interfaceVersion?: number }>(moduleName) : null
// Interface 10 keeps the custom UIKit controls; surfaces and menus use shared libraries.
// A previous native binary receives the shared React fallback until rebuilt.
const nativeModuleAvailable = (nativeModule?.interfaceVersion ?? 0) >= 10
export const nativeControlsAvailable = nativeModuleAvailable

type ModeControlProps = ViewProps & {
    dark: boolean
    labels: string[]
    badges?: string[]
    onSelect: (event: { nativeEvent: { index: number } }) => void
    selectedIndex: number
}

type ActionControlProps = ViewProps & {
    action: "back" | "settings" | "attachment" | "latest" | "mentor" | "microphone" | "send" | "stop" | "busy"
    dark: boolean
    disabled?: boolean
    label: string
    title?: string
    onAction: () => void
}

export const NativeChatModeControl = nativeModuleAvailable ? requireNativeView<ModeControlProps>(moduleName, "ModeControl") : null
export const NativeChatAction = nativeModuleAvailable ? requireNativeView<ActionControlProps>(moduleName, "ActionControl") : null
export const NativeComposerMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; topEdge?: boolean }>(moduleName, "ComposerMaterial") : null
export const NativeChatKeyboardMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean }>(moduleName, "KeyboardMaterial") : null
