import * as Clipboard from "expo-clipboard"
import { Alert } from "react-native"

import type { UseCopyableProfileValueParams } from "@/hooks/profile/use-copyable-profile-value.types"

export function useCopyableProfileValue({ t }: UseCopyableProfileValueParams) {
    const handleCopy = async (value: string | null | undefined) => {
        if (!value) {
            return false
        }

        await Clipboard.setStringAsync(value)
        Alert.alert(t("profile.copiedTitle"), value)
        return true
    }

    return {
        handleCopy,
    }
}
