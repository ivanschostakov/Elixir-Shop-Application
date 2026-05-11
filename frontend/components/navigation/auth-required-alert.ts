import { Alert } from "react-native"

import { translate } from "@/i18n/translations"

type AuthRequiredAlertOptions = {
    onLogin: () => void
}

export function showAuthRequiredAlert({ onLogin }: AuthRequiredAlertOptions) {
    Alert.alert(
        translate("auth.requiredAlertTitle"),
        translate("auth.requiredAlertMessage"),
        [
            {
                text: translate("common.cancel"),
                style: "destructive",
            },
            {
                text: translate("auth.entry.login"),
                onPress: onLogin,
            },
        ],
    )
}
