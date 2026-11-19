import { Alert, Linking } from "react-native"
import { requestRecordingPermissionsAsync } from "expo-audio"
import type { TranslationKey } from "@/i18n/translations"

export async function requestChatRecordingPermission(t: (key: TranslationKey) => string) {
    const permission = await requestRecordingPermissionsAsync()
    if (permission.granted) return true
    Alert.alert(t("chat.voicePermissionTitle"), t("chat.voicePermissionMessage"), [
        { text: t("common.cancel"), style: "cancel" },
        ...(!permission.canAskAgain ? [{ text: t("chat.voiceOpenSettings"), onPress: () => { void Linking.openSettings() } }] : []),
    ])
    return false
}
