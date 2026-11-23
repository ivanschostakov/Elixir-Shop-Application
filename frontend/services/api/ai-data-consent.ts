import { apiGet, apiPost } from "@/services/api/client"
import { getAuthTokens } from "@/services/auth/session"
import { translate } from "@/i18n/translations"

export type AiDataConsent = { version: string; granted: boolean }
const endpoint = "/v1/users/me/ai-chat/data-consent"
let prompt: (() => Promise<boolean>) | null = null
let pending: { sessionId: number; promise: Promise<void> } | null = null

export function registerAiConsentPrompt(handler: () => Promise<boolean>) {
    prompt = handler
    return () => { if (prompt === handler) prompt = null }
}

export const getAiDataConsent = () => apiGet<AiDataConsent>(endpoint)
export const setAiDataConsent = (granted: boolean, version: string) => apiPost<AiDataConsent, { granted: boolean; version: string }>(endpoint, { granted, version })

export class AiConsentDeclinedError extends Error {
    constructor() { super(translate("privacy.aiDeclined")); this.name = "AiConsentDeclinedError" }
}

export async function ensureAiDataConsent(): Promise<void> {
    const sessionId = getAuthTokens()?.sessionId
    if (sessionId === undefined) throw new AiConsentDeclinedError()
    if (pending?.sessionId === sessionId) return pending.promise
    const checkSession = () => { if (getAuthTokens()?.sessionId !== sessionId) throw new AiConsentDeclinedError() }
    const operation = (async () => {
        const state = await getAiDataConsent()
        checkSession()
        if (state.granted) return
        if (!prompt || !await prompt()) throw new AiConsentDeclinedError()
        checkSession()
        const granted = await setAiDataConsent(true, state.version)
        checkSession()
        if (!granted.granted) throw new AiConsentDeclinedError()
    })()
    pending = { sessionId, promise: operation }
    try { await operation } finally { if (pending?.promise === operation) pending = null }
}
