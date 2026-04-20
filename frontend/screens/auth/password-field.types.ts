import type { TextInputProps } from "react-native"

export type PasswordFieldProps = {
    label: string
    onChangeText: (value: string) => void
    onFocus?: () => void
    placeholder: string
    returnKeyType?: TextInputProps["returnKeyType"]
    value: string
}
