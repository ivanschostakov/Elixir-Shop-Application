import { useCallback, useRef, useState } from "react"

import type { DeliveryRecipientRead } from "@/services/api/order-drafts.types"

type RecipientSelection = {
    scope: string
    recipient: DeliveryRecipientRead | null
}

export function useCheckoutRecipientSelection(
    scope: string,
    snapshotRecipient: DeliveryRecipientRead | null,
) {
    const activeScope = useRef(scope)
    activeScope.current = scope
    const [confirmed, setConfirmed] = useState<RecipientSelection | null>(null)

    // A read started before the save can still publish the previous recipient to the shared snapshot.
    const recipient = confirmed?.scope === scope ? confirmed.recipient : snapshotRecipient
    const confirmRecipient = useCallback((value: DeliveryRecipientRead | null) => {
        if (activeScope.current !== scope) return
        setConfirmed({ scope, recipient: value })
    }, [scope])

    return { recipient, confirmRecipient }
}
