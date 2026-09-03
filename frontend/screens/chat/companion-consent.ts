import type { CompanionAction, CompanionState } from "@/services/api/companion"

export class CompanionActionCancelled extends Error {}

export async function withStorageConsent(
    state: CompanionState | null,
    action: CompanionAction,
    confirm: (version: string) => Promise<boolean>,
): Promise<CompanionAction> {
    if (!state?.consent_required || ["enable", "disable", "cancel", "delete_entry"].includes(action.kind)) return action
    if (!await confirm(state.consent_version)) throw new CompanionActionCancelled()
    // The explicit 18+ save button, never merely opening the chat, grants consent.
    return { ...action, consent_version: state.consent_version, adult_confirmed: true }
}
