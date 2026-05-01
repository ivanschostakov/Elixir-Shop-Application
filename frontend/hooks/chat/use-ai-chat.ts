import { useEffect, useRef, useState } from "react"
import { useIsFocused } from "@react-navigation/native"

import { setBasketSnapshot } from "@/hooks/basket/basket-store"
import { useAsyncData } from "@/hooks/shared/use-async-data"
import { getMyAiChat, performAiChatAction, sendMyAiChatMessage } from "@/services/api/ai-chat"
import type {
    AIAttachmentRead,
    AIChatActionPayload,
    AIChatActionResponse,
    AIChatResponse,
    AIMessageRead,
    UploadableChatAttachment,
} from "@/services/api/ai-chat.types"

export type ChatMessageDeliveryStatus = "pending" | "failed"

export type ChatDisplayMessage = AIMessageRead & {
    client_id?: string
    delivery_status?: ChatMessageDeliveryStatus
}

type UseAiChatResult = {
    aiTyping: boolean
    chat: AIChatResponse | null
    error: string | null
    loading: boolean
    messages: ChatDisplayMessage[]
    refreshing: boolean
    sending: boolean
    performAction: (payload: AIChatActionPayload) => Promise<AIChatActionResponse>
    refresh: () => Promise<void>
    sendMessage: (text: string, attachments?: UploadableChatAttachment[]) => Promise<AIChatResponse>
}

const AI_REPLY_POLL_INTERVAL_MS = 1500
const AI_REPLY_POLL_MAX_ATTEMPTS = 30

export function useAiChat(): UseAiChatResult {
    const isFocused = useIsFocused()
    const [refreshing, setRefreshing] = useState(false)
    const [sending, setSending] = useState(false)
    const [aiTyping, setAiTyping] = useState(false)
    const [optimisticMessages, setOptimisticMessages] = useState<ChatDisplayMessage[]>([])
    const hasLoadedOnceRef = useRef(false)
    const optimisticIdRef = useRef(0)
    const {
        data: chat,
        error,
        loading,
        reload,
        setData: setChat,
    } = useAsyncData({
        deps: [],
        enabled: false,
        fetcher: getMyAiChat,
        initialData: null as AIChatResponse | null,
    })
    const hasPendingServerReply = hasServerPendingAssistantReply(chat)

    const refresh = async () => {
        setRefreshing(true)
        try {
            const nextChat = await reload({ showLoading: false })

            if (nextChat) {
                setOptimisticMessages([])
                setAiTyping(false)
            }
        } finally {
            setRefreshing(false)
            hasLoadedOnceRef.current = true
        }
    }

    useEffect(() => {
        if (!isFocused) {
            return
        }

        void reload({ showLoading: !hasLoadedOnceRef.current }).finally(() => {
            hasLoadedOnceRef.current = true
        })
    }, [isFocused, reload])

    useEffect(() => {
        if (!isFocused || sending || !hasPendingServerReply) {
            return
        }

        let isDisposed = false
        let attempts = 0
        let nextPollTimeout: ReturnType<typeof setTimeout> | null = null

        const scheduleNextPoll = () => {
            if (isDisposed || attempts >= AI_REPLY_POLL_MAX_ATTEMPTS) {
                return
            }

            nextPollTimeout = setTimeout(() => {
                void pollForAssistantReply()
            }, AI_REPLY_POLL_INTERVAL_MS)
        }

        const pollForAssistantReply = async () => {
            if (isDisposed) {
                return
            }

            attempts += 1

            try {
                const nextChat = await getMyAiChat()
                if (isDisposed) {
                    return
                }

                setChat(nextChat)
                if (!hasPendingAssistantReply(nextChat)) {
                    return
                }
            } catch {
                // Keep retrying in short bursts to pick up delayed AI replies.
            }

            scheduleNextPoll()
        }

        scheduleNextPoll()

        return () => {
            isDisposed = true
            if (nextPollTimeout) {
                clearTimeout(nextPollTimeout)
            }
        }
    }, [hasPendingServerReply, isFocused, sending, setChat])

    const sendMessage = async (text: string, attachments: UploadableChatAttachment[] = []) => {
        const createdAt = new Date().toISOString()
        const nextOptimisticIndex = optimisticIdRef.current + 1
        optimisticIdRef.current = nextOptimisticIndex
        const optimisticId = -nextOptimisticIndex
        const optimisticMessage = createOptimisticUserMessage({
            attachments,
            chat,
            createdAt,
            id: optimisticId,
            text,
        })

        setOptimisticMessages((currentMessages) => [...currentMessages, optimisticMessage])
        setAiTyping(true)
        setSending(true)

        try {
            const nextChat = await sendMyAiChatMessage(text, attachments)
            if (nextChat.basket) {
                setBasketSnapshot(nextChat.basket)
            }
            setChat(nextChat)
            setOptimisticMessages([])
            return nextChat
        } catch (sendError) {
            setOptimisticMessages((currentMessages) =>
                currentMessages.map((message) =>
                    message.id === optimisticId
                        ? { ...message, delivery_status: "failed" }
                        : message,
                ),
            )
            throw sendError
        } finally {
            setAiTyping(false)
            setSending(false)
        }
    }

    const performAction = async (payload: AIChatActionPayload) => {
        const nextChat = await performAiChatAction(payload)
        if (nextChat.basket) {
            setBasketSnapshot(nextChat.basket)
        }
        setChat(nextChat)
        return nextChat
    }

    const messages = [
        ...(chat?.chat.messages ?? []),
        ...optimisticMessages,
    ]

    return {
        aiTyping,
        chat,
        error,
        loading,
        messages,
        performAction,
        refreshing,
        sending,
        refresh,
        sendMessage,
    }
}

function hasPendingAssistantReply(chat: AIChatResponse | null) {
    const messages = chat?.chat.messages ?? []
    const lastMessage = messages[messages.length - 1]
    if (!lastMessage) {
        return false
    }

    return lastMessage.sender === "user"
}

function hasServerPendingAssistantReply(chat: AIChatResponse | null) {
    if (!chat) {
        return false
    }

    return hasPendingAssistantReply(chat)
}

function createOptimisticUserMessage({
    attachments,
    chat,
    createdAt,
    id,
    text,
}: {
    attachments: UploadableChatAttachment[]
    chat: AIChatResponse | null
    createdAt: string
    id: number
    text: string
}): ChatDisplayMessage {
    return {
        attachments: attachments.map((attachment, attachmentIndex) =>
            createOptimisticAttachment({
                attachment,
                attachmentIndex,
                createdAt,
                messageId: id,
            }),
        ),
        chat_id: chat?.chat.id ?? 0,
        client_id: `local-${Math.abs(id)}`,
        created_at: createdAt,
        delivery_status: "pending",
        id,
        interactive: null,
        sender: "user",
        text,
        updated_at: createdAt,
        user_id: chat?.chat.user_id ?? 0,
        usage: null,
    }
}

function createOptimisticAttachment({
    attachment,
    attachmentIndex,
    createdAt,
    messageId,
}: {
    attachment: UploadableChatAttachment
    attachmentIndex: number
    createdAt: string
    messageId: number
}): AIAttachmentRead {
    const fallbackFilename = `attachment-${attachmentIndex + 1}`
    const filename = attachment.fileName ?? fallbackFilename

    return {
        created_at: createdAt,
        filename,
        id: messageId * 100 - attachmentIndex,
        message_id: messageId,
        mime_type: attachment.mimeType ?? null,
        original_filename: attachment.fileName ?? null,
        relative_path: attachment.uri,
        size_bytes: 0,
        type: attachment.mimeType?.startsWith("image/") ? "image" : "document",
        updated_at: createdAt,
    }
}
