import { KeyboardAvoidingView, Platform, type KeyboardAvoidingViewProps } from "react-native"

type Props = Omit<KeyboardAvoidingViewProps, "behavior" | "keyboardVerticalOffset"> & {
    iosBehavior?: KeyboardAvoidingViewProps["behavior"]
    androidBehavior?: KeyboardAvoidingViewProps["behavior"] | null
    iosOffset?: number; androidOffset?: number
}
export function AppFormLayout({ iosBehavior = "padding", androidBehavior = "height", iosOffset = 0, androidOffset = 0, ...props }: Props) {
    return <KeyboardAvoidingView {...props} behavior={Platform.OS === "ios" ? iosBehavior : androidBehavior ?? undefined} keyboardVerticalOffset={Platform.OS === "ios" ? iosOffset : androidOffset} />
}
