import { requireNativeView, requireOptionalNativeModule } from "expo"
import { Platform, type ViewProps } from "react-native"

const moduleName = "ElixirChatControls"
const nativeModuleAvailable = Platform.OS === "ios"
    && requireOptionalNativeModule(moduleName) !== null

type ModeControlProps = ViewProps & {
    dark: boolean
    labels: string[]
    onSelect: (event: { nativeEvent: { index: number } }) => void
    selectedIndex: number
}

type ActionControlProps = ViewProps & {
    action: "back" | "attachment" | "latest" | "microphone" | "send" | "stop" | "busy"
    dark: boolean
    disabled?: boolean
    label: string
    onAction: () => void
}

export const NativeChatModeControl = nativeModuleAvailable ? requireNativeView<ModeControlProps>(moduleName, "ModeControl") : null
export const NativeChatAction = nativeModuleAvailable ? requireNativeView<ActionControlProps>(moduleName, "ActionControl") : null
export const NativeComposerMaterial = nativeModuleAvailable ? requireNativeView<ViewProps & { dark: boolean; topEdge?: boolean }>(moduleName, "ComposerMaterial") : null
