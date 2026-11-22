import { useLocalSearchParams } from "expo-router"
import { useAuth } from "@/providers/auth-provider"
import { SupportChatScreen } from "@/screens/chat/support-chat-screen"

export default function ChatScreen() {
    const { user } = useAuth()
    const { conversationId } = useLocalSearchParams<{ conversationId?: string | string[] }>()
    const rawId = Array.isArray(conversationId) ? conversationId[0] : conversationId
    const parsedId = Number(rawId)
    const requestedConversationId = Number.isSafeInteger(parsedId) && parsedId > 0 ? parsedId : null
    return <SupportChatScreen key={user?.id ?? "guest"} requestedConversationId={requestedConversationId} />
}
