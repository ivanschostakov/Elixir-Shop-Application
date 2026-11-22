import { requireNativeView, requireOptionalNativeModule } from "expo"
import { Platform, type ViewProps } from "react-native"

const moduleName = "ElixirChatControls"
const nativeModule = Platform.OS === "ios"
    ? requireOptionalNativeModule<{ interfaceVersion?: number }>(moduleName)
    : null
const nativeModuleAvailable = (nativeModule?.interfaceVersion ?? 0) >= 8

type ActionControlProps = ViewProps & {
    action: "back" | "attachment" | "send" | "busy"
    dark: boolean
    disabled?: boolean
    label: string
    onAction: () => void
}
export const NativeChatAction = nativeModuleAvailable ? requireNativeView<ActionControlProps>(moduleName, "ActionControl") : null
export const NativeComposerMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; topEdge?: boolean }>(moduleName, "ComposerMaterial") : null
export const NativeChatInputMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; joined: boolean }>(moduleName, "InputMaterial") : null
export const NativeChatMenu = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; label: string; labels: string[]; details: string[]; selectedIndex: number; onSelect: (event: { nativeEvent: { index: number } }) => void }>(moduleName, "MenuControl") : null

export const NativeChatTitleMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean }>(moduleName, "TitleMaterial") : null
