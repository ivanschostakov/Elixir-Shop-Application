let accountId: number | null = null
let revision = 0
const listeners = new Set<() => void>()

export const commerceAccountId = () => accountId
export const commerceAccountRevision = () => revision

export function setCommerceAccount(next: number | null) {
    if (next === accountId) return
    accountId = next
    revision++
    listeners.forEach(listener => listener())
}

export function subscribeCommerceAccount(listener: () => void) {
    listeners.add(listener)
    return () => { listeners.delete(listener) }
}
