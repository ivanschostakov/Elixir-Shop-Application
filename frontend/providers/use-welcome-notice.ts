import { useEffect, useRef } from "react"
import { Alert, AppState, Platform } from "react-native"
import { translate } from "@/i18n/translations"
import { acknowledgeWelcomeNotice, getWelcomeNotice } from "@/services/api/benefits"

export function useWelcomeNotice(userId: number | undefined, ready: boolean) {
    const shown = useRef<number | null>(null)
    useEffect(() => {
        if (!ready || userId == null || Platform.OS === "web") return
        let active = true
        let loading = false
        const check = async () => {
            if (loading || !active || AppState.currentState !== "active") return
            loading = true
            try {
                const notice = await getWelcomeNotice()
                if (!active || !notice || AppState.currentState !== "active") return
                if (shown.current !== notice.credit_id) {
                    const deadline = new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "2-digit", year: "numeric",
                        hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(new Date(notice.expires_at))
                    Alert.alert(translate("welcomeCredit.title"), translate("welcomeCredit.body").replace("{date}", deadline))
                    shown.current = notice.credit_id
                }
                await acknowledgeWelcomeNotice(notice.credit_id)
            } catch {
                // A failed acknowledgement is retried on foreground without reopening the alert.
            } finally {
                loading = false
            }
        }
        void check()
        const listener = AppState.addEventListener("change", state => { if (state === "active") void check() })
        return () => { active = false; listener.remove() }
    }, [ready, userId])
}
