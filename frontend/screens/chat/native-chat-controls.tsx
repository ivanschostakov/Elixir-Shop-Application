import { requireNativeView, requireOptionalNativeModule } from "expo"
import { Platform, type ViewProps } from "react-native"

const moduleName = "ElixirChatControls"
const nativeModule = Platform.OS === "ios" ? requireOptionalNativeModule<{ interfaceVersion?: number }>(moduleName) : null
// Interface 8 was the support-only binary and has no mode/keyboard controls.
// Use the complete JS fallback until the restored native interface is installed.
const nativeModuleAvailable = (nativeModule?.interfaceVersion ?? 0) >= 9

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
export const nativeChatInlineBadgesAvailable = nativeModuleAvailable
export const nativeChatMentorActionAvailable = nativeModuleAvailable
export const nativeChatSettingsActionAvailable = nativeModuleAvailable
export const nativeChatMentorGreetingAvailable = nativeModuleAvailable
export const NativeChatAction = nativeModuleAvailable ? requireNativeView<ActionControlProps>(moduleName, "ActionControl") : null
export const NativeComposerMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; topEdge?: boolean }>(moduleName, "ComposerMaterial") : null
export const NativeChatInputMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; joined: boolean }>(moduleName, "InputMaterial") : null
export const NativeChatKeyboardMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean }>(moduleName, "KeyboardMaterial") : null
export const NativeChatMenu = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; label: string; labels: string[]; details: string[]; selectedIndex: number; onSelect: (event: { nativeEvent: { index: number } }) => void }>(moduleName, "MenuControl") : null
export const NativeChatTitleMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean }>(moduleName, "TitleMaterial") : null
