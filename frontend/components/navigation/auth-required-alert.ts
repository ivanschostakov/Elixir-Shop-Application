import { Alert } from "react-native"

type AuthRequiredAlertOptions = {
    onLogin: () => void
}

export function showAuthRequiredAlert({ onLogin }: AuthRequiredAlertOptions) {
    Alert.alert(
        "Требуется вход",
        "Это действие доступно только для авторизованных пользователей.",
        [
            {
                text: "Отмена",
                style: "destructive",
            },
            {
                text: "Войти",
                onPress: onLogin,
            },
        ],
    )
}
