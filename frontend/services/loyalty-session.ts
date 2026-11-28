import type { LoyaltyMilestones } from "@/services/api/users.types"

type Operation = "check" | "accept"
type Snapshot = {
    data: LoyaltyMilestones | null
    pending: Operation | null
    error: Operation | null
    programRevision: number
}

export const initialMilestones: Snapshot = { data: null, pending: null, error: null, programRevision: 0 }

export function createLoyaltySession(api: Record<Operation, () => Promise<LoyaltyMilestones>>, current: () => boolean) {
    let state = initialMilestones
    let checking: Promise<void> | null = null
    let accepting: Promise<void> | null = null
    let paidDuringRequest = false
    const listeners = new Set<() => void>()
    function update(patch: Partial<Snapshot>) {
        state = { ...state, ...patch }
        listeners.forEach(fn => fn())
    }
    async function run(op: Operation) {
        if (!current()) return
        update({ pending: op, error: null })
        try {
            const data = await api[op]()
            // An empty/pending response is not evidence that an offer or code disappeared.
            if (!data || typeof data.offer_partner !== "boolean" || typeof data.own_code_eligible !== "boolean"
                || !(data.own_promo_code === null || typeof data.own_promo_code === "string")
                || !(data.company_promo_code === null || typeof data.company_promo_code === "string")) {
                throw new Error("Incomplete milestone response")
            }
            if (current()) update({ data, pending: null, programRevision: state.programRevision + Number(op === "accept" && !data.offer_partner) })
        } catch {
            if (current()) update({ pending: null, error: op })
        }
    }
    function drainPaid() {
        if (!paidDuringRequest || checking || accepting || !current()) return
        paidDuringRequest = false
        void check()
    }
    function check(reason?: "paid"): Promise<void> {
        if (!current()) return Promise.resolve()
        if (accepting || checking) {
            // A confirmed payment can post after an earlier check started.
            if (reason === "paid") paidDuringRequest = true
            return (accepting ?? checking)!
        }
        checking = run("check").finally(() => { checking = null; drainPaid() })
        return checking
    }
    function accept(): Promise<void> {
        if (!current() || !state.data?.offer_partner) return Promise.resolve()
        if (!accepting) accepting = (async () => {
            if (checking) await checking
            if (state.data?.offer_partner) await run("accept")
        })().finally(() => { accepting = null; drainPaid() })
        return accepting
    }
    return {
        current, check, accept,
        bindingChanged: () => { if (current()) update({ programRevision: state.programRevision + 1 }) },
        snapshot: () => state,
        subscribe: (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn) } },
    }
}
