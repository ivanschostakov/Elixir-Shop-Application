import { useCallback, useState } from "react"
import { useLocalSearchParams } from "expo-router"

import { SupportChatScreen } from "@/screens/chat/support-chat-screen"

export default function IosSupportRouteScreen() {
    const params = useLocalSearchParams<{ conversationId?: string | string[] }>()
    const rawConversationId = Array.isArray(params.conversationId) ? params.conversationId[0] : params.conversationId
    const parsedConversationId = Number(rawConversationId)
    const requestedConversationId = Number.isInteger(parsedConversationId) && parsedConversationId > 0
        ? parsedConversationId
        : null
    const [supportUnreadCount, setSupportUnreadCount] = useState(0)
    const keepSupportMode = useCallback(() => undefined, [])

    return (
        <SupportChatScreen
            active
            communityUnreadCount={0}
            mode="support"
            onModeChange={keepSupportMode}
            onUnreadChange={setSupportUnreadCount}
            requestedConversationId={requestedConversationId}
            supportUnreadCount={supportUnreadCount}
        />
    )
}
