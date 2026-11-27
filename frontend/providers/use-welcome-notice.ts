import { useEffect, useRef } from "react"
import { Alert, AppState, Platform } from "react-native"
import { translate } from "@/i18n/translations"
import { acknowledgeWelcomeNotice, claimWelcomeReminder, getWelcomeNotice } from "@/services/api/benefits"
import { syncOrderStatusNotifications } from "@/services/notifications/order-status-notifications"

export function useWelcomeNotice(userId: number | undefined, ready: boolean) {
    const shown = useRef<number | null>(null)
    useEffect(() => {
        if (!ready || userId == null || Platform.OS === "web") return
        let active = true
        let loading = false
        let alertOpen = false
        const sync = () => syncOrderStatusNotifications({ requestPermissions: true, automatic: true })
        const check = async () => {
            if (alertOpen || loading || !active || AppState.currentState !== "active") return
            loading = true
            try {
                const notice = await getWelcomeNotice()
                if (!active || AppState.currentState !== "active") return
                if (!notice) {
                    const token = await sync()
                    if (token || !active || AppState.currentState !== "active") return
                    const reminder = await claimWelcomeReminder()
                    if (reminder && active && AppState.currentState === "active") {
                        Alert.alert(reminder.title, reminder.body, [{ text: translate("welcomeCredit.dismiss") }])
                    }
                    return
                }
                if (shown.current !== notice.credit_id) {
                    const deadline = new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "2-digit", year: "numeric",
                        hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(new Date(notice.expires_at))
                    alertOpen = true
                    Alert.alert(translate("welcomeCredit.title"), translate("welcomeCredit.body").replace("{date}", deadline), [
                        { text: translate("welcomeCredit.dismiss"), onPress: () => {
                            alertOpen = false
                            if (active) void sync()
                        } },
                    ], { cancelable: false })
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
