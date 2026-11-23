import { Image, type StyleProp, type ImageStyle } from "react-native"
import { getReadAttachmentUri } from "@/screens/chat/chat-attachments"
import { getAuthTokens } from "@/services/auth/session"
import type { AIAttachmentRead } from "@/services/api/ai-chat.types"

export function MentorMealImage({ attachment, style }: { attachment: AIAttachmentRead; style: StyleProp<ImageStyle> }) {
    const uri = getReadAttachmentUri(attachment)
    if (!uri) return null
    return <Image source={{ uri, ...(attachment.is_private ? { headers: { Authorization: `Bearer ${getAuthTokens()?.accessToken ?? ""}` }, cache: "reload" as const } : {}) }} style={style} />
}
