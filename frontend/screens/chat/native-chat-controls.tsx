import { requireNativeView, requireOptionalNativeModule } from "expo"
import { Platform, type ViewProps } from "react-native"

const moduleName = "ElixirChatControls"
const nativeModule = Platform.OS === "ios" ? requireOptionalNativeModule<{ interfaceVersion?: number }>(moduleName) : null
const nativeModuleAvailable = nativeModule !== null

type ModeControlProps = ViewProps & {
    dark: boolean
    labels: string[]
    badges?: string[]
    onSelect: (event: { nativeEvent: { index: number } }) => void
    selectedIndex: number
}

type ActionControlProps = ViewProps & {
    action: "back" | "attachment" | "latest" | "mentor" | "microphone" | "send" | "stop" | "busy"
    dark: boolean
    disabled?: boolean
    label: string
    onAction: () => void
}

export const NativeChatModeControl = nativeModuleAvailable ? requireNativeView<ModeControlProps>(moduleName, "ModeControl") : null
export const nativeChatInlineBadgesAvailable = (nativeModule?.interfaceVersion ?? 1) >= 4
export const nativeChatMentorActionAvailable = (nativeModule?.interfaceVersion ?? 1) >= 5
export const NativeChatAction = nativeModuleAvailable ? requireNativeView<ActionControlProps>(moduleName, "ActionControl") : null
export const NativeComposerMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; topEdge?: boolean }>(moduleName, "ComposerMaterial") : null
export const NativeChatInputMaterial = (nativeModule?.interfaceVersion ?? 1) >= 2 ? requireNativeView<ViewProps & { dark: boolean; joined: boolean }>(moduleName, "InputMaterial") : null
export const NativeChatKeyboardMaterial = (nativeModule?.interfaceVersion ?? 1) >= 2 ? requireNativeView<ViewProps & { dark: boolean }>(moduleName, "KeyboardMaterial") : null
export const NativeChatMenu = (nativeModule?.interfaceVersion ?? 1) >= 2 ? requireNativeView<ViewProps & { dark: boolean; label: string; labels: string[]; details: string[]; selectedIndex: number; onSelect: (event: { nativeEvent: { index: number } }) => void }>(moduleName, "MenuControl") : null
export const NativeChatTitleMaterial = (nativeModule?.interfaceVersion ?? 1) >= 3 ? requireNativeView<ViewProps & { dark: boolean }>(moduleName, "TitleMaterial") : null
