import type { CommunityMessage } from "@/services/api/community.types"

export function filterBlockedCommunityMessages(messages: CommunityMessage[], blockedAuthorIds: number[]) {
    const blocked = new Set(blockedAuthorIds)
    return messages.filter((message) => !blocked.has(message.author.id)).map((message) => {
        const reply = message.reply_to
        return reply?.author_id && blocked.has(reply.author_id) ? { ...message, reply_to: null } : message
    })
}
