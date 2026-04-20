import { Alert } from "react-native"

import type { TranslationFn } from "@/providers/language-provider.types"

export function showRemoveFavouriteConfirmation(t: TranslationFn, onConfirm: () => void) {
    Alert.alert(
        t("favorites.removeConfirmTitle"),
        t("favorites.removeConfirmMessage"),
        [
            {
                style: "cancel",
                text: t("common.cancel"),
            },
            {
                onPress: onConfirm,
                style: "destructive",
                text: t("cart.removeItem"),
            },
        ],
    )
}
