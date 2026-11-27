import { useEffect, useRef } from "react"
import { AppState, Platform } from "react-native"
import { translate } from "@/i18n/translations"
import { acknowledgeWelcomeNotice, claimWelcomeReminder, getWelcomeNotice } from "@/services/api/benefits"
import { syncOrderStatusNotifications } from "@/services/notifications/order-status-notifications"
import { presentStartupNotice, queueStartupNotice } from "@/services/notifications/startup-notices"
import { getAuthTokens } from "@/services/auth/session"

export function useWelcomeNotice(userId: number | undefined, ready: boolean, sessionId: number | undefined) {
    const shown = useRef<number | null>(null)
    useEffect(() => {
        if (!ready || userId == null || Platform.OS === "web") return
        let active = true
        let loading = false
        const current = () => active && sessionId === getAuthTokens()?.sessionId && AppState.currentState === "active"
        const sync = () => syncOrderStatusNotifications({ requestPermissions: true, automatic: true })
        const check = () => {
            if (loading || !current()) return
            loading = true
            void queueStartupNotice(async () => {
                if (!current()) return
                const notice = await getWelcomeNotice()
                if (!current()) return
                if (!notice) {
                    const token = await sync()
                    if (token || !current()) return
                    const reminder = await claimWelcomeReminder()
                    if (reminder && current()) {
                        await presentStartupNotice(reminder.title, reminder.body, [translate("welcomeCredit.dismiss")])
                    }
                    return
                }
                if (shown.current !== notice.credit_id) {
                    const deadline = new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "2-digit", year: "numeric",
                        hour: "2-digit", minute: "2-digit", timeZoneName: "short" }).format(new Date(notice.expires_at))
                    const dismissed = presentStartupNotice(translate("welcomeCredit.title"), translate("welcomeCredit.body").replace("{date}", deadline), [translate("welcomeCredit.dismiss")])
                    shown.current = notice.credit_id
                    await Promise.all([
                        acknowledgeWelcomeNotice(notice.credit_id).catch(() => undefined),
                        dismissed.then(() => current() ? sync() : undefined),
                    ])
                    return
                }
                await acknowledgeWelcomeNotice(notice.credit_id)
            }).finally(() => { loading = false })
        }
        void check()
        const listener = AppState.addEventListener("change", state => { if (state === "active") void check() })
        return () => { active = false; listener.remove() }
    }, [ready, userId, sessionId])
}
