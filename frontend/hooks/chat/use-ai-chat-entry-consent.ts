import { useEffect, useState } from "react"
import { useIsFocused } from "@react-navigation/native"
import { useRouter } from "expo-router"
import { Alert } from "react-native"
import { ROUTES } from "@/constants/routes"
import { useAuth } from "@/providers/auth-provider"
import { translate } from "@/i18n/translations"
import { AiConsentDeclinedError, ensureAiDataConsent } from "@/services/api/ai-data-consent"
import { getErrorMessage } from "@/utils/errors"

export function useAiChatEntryConsent(active: boolean) {
    const focused = useIsFocused()
    const router = useRouter()
    const { user } = useAuth()
    const userId = user?.id
    const [allowedUser, setAllowedUser] = useState<typeof userId>(undefined)

    useEffect(() => {
        let disposed = false
        setAllowedUser(undefined)
        if (active && focused && userId !== undefined) {
            void ensureAiDataConsent().then(() => {
                if (!disposed) setAllowedUser(userId)
            }).catch(error => {
                if (disposed) return
                if (!(error instanceof AiConsentDeclinedError)) {
                    Alert.alert(translate("common.errorTitle"), getErrorMessage(error))
                }
                if (router.canGoBack()) router.back()
                else router.replace(ROUTES.home)
            })
        }
        return () => { disposed = true }
    }, [active, focused, router, userId])

    return active && focused && userId !== undefined && allowedUser === userId
}
