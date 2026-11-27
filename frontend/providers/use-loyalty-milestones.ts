import { useEffect, useMemo, useRef, useSyncExternalStore } from "react"
import { AppState, Platform } from "react-native"
import * as SecureStore from "expo-secure-store"
import { ROUTES } from "@/constants/routes"
import { translate } from "@/i18n/translations"
import { partnerOfferBody } from "@/i18n/loyalty"
import { acceptMyPartnerOffer, checkMyMilestones } from "@/services/api/users"
import { getAuthTokens } from "@/services/auth/session"
import { commerceAccountId } from "@/services/commerce-account"
import { createLoyaltySession, initialMilestones } from "@/services/loyalty-session"
import { presentStartupNotice, queueStartupNotice } from "@/services/notifications/startup-notices"

const idleSnapshot = () => initialMilestones
const idleSubscribe = () => () => {}
const shown = new Set<string>()
type Session = ReturnType<typeof createLoyaltySession>

function queueMilestone(session: Session, userId: number, kind: "partner" | "code") {
    const key = `loyalty.milestones.${userId}.${kind}`
    if (shown.has(key)) return
    void queueStartupNotice(async () => {
        const current = () => session.current() && AppState.currentState === "active"
        if (!current() || shown.has(key) || await SecureStore.getItemAsync(key)) return
        const { data, pending, error } = session.snapshot()
        if (!current() || pending || error || !data) return
        const partner = kind === "partner"
        if (partner ? !data.offer_partner : !(data.own_code_eligible && data.own_promo_code)) return
        const dismissed = partner
            ? presentStartupNotice(translate("milestone.offerTitle"), partnerOfferBody(data.company_promo_code),
                [translate("milestone.later"), translate("milestone.accept")])
            : presentStartupNotice(translate("milestone.codeTitle"), translate("milestone.codeBody").replace("{code}", data.own_promo_code!),
                [translate("welcomeCredit.dismiss")])
        shown.add(key)
        const save = SecureStore.setItemAsync(key, "1").catch(() => undefined)
        const choice = await dismissed
        if (partner && choice === 1 && current()) {
            await session.accept()
            if (current() && session.snapshot().error === "accept") {
                await presentStartupNotice(translate("milestone.offerTitle"), translate("milestone.acceptFailed"), [translate("welcomeCredit.dismiss")])
            }
        }
        await save
    })
}

export function useLoyaltyMilestones(userId: number | undefined, sessionId: number | undefined, pathname: string) {
    const mounted = useRef(false)
    useEffect(() => {
        mounted.current = true
        return () => { mounted.current = false }
    }, [])
    const session = useMemo(() => {
        if (Platform.OS === "web" || userId == null || sessionId == null) return null
        return createLoyaltySession({ check: checkMyMilestones, accept: acceptMyPartnerOffer },
            () => mounted.current && getAuthTokens()?.sessionId === sessionId && commerceAccountId() === userId)
    }, [userId, sessionId])
    const state = useSyncExternalStore(session?.subscribe ?? idleSubscribe, session?.snapshot ?? idleSnapshot, idleSnapshot)
    useEffect(() => {
        if (!session) return
        let previous = AppState.currentState
        if (previous === "active") void session.check()
        const sub = AppState.addEventListener("change", next => {
            if (next === "active" && previous !== "active") void session.check()
            previous = next
        })
        return () => sub.remove()
    }, [session])
    useEffect(() => {
        if ((pathname === ROUTES.profile || pathname === ROUTES.profileDiscounts) && AppState.currentState === "active") void session?.check()
    }, [pathname, session])
    useEffect(() => {
        if (!session || userId == null || !state.data || state.error || state.pending) return
        if (state.data.offer_partner) queueMilestone(session, userId, "partner")
        if (state.data.own_code_eligible && state.data.own_promo_code) queueMilestone(session, userId, "code")
    }, [session, state, userId])
    return session ? { ...state, check: session.check, accept: session.accept } : null
}
