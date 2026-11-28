import { Alert, Platform } from "react-native"
import { commerceAccountRevision } from "@/services/commerce-account"

export async function confirmPromoBinding(title: string, message: string, cancel: string): Promise<boolean> {
    const account = commerceAccountRevision()
    if (Platform.OS === "web") return Promise.resolve(window.confirm(message))
    const confirmed = await new Promise<boolean>(resolve => Alert.alert(title, message, [
        { text: cancel, style: "cancel", onPress: () => resolve(false) },
        { text: title, onPress: () => resolve(true) },
    ], { cancelable: true, onDismiss: () => resolve(false) }))
    return confirmed && account === commerceAccountRevision()
}
