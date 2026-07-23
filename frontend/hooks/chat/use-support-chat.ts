import { useCallback, useEffect, useRef, useState } from "react"
import { useIsFocused } from "@react-navigation/native"

import {
    createMySupportConversation,
    getMySupportConversation,
    getMySupportInbox,
    markMySupportConversationRead,
    sendMySupportMessage,
} from "@/services/api/support"
import type {
    CreateSupportConversationPayload,
    SendSupportMessagePayload,
    SupportConversation,
    SupportInbox,
} from "@/services/api/support.types"

const ACTIVE_POLL_INTERVAL_MS = 5000

export function useSupportChat(active: boolean, onUnreadChange: (count: number) => void) {
    const isFocused = useIsFocused()
    const [inbox, setInbox] = useState<SupportInbox | null>(null)
    const [selectedConversation, setSelectedConversation] = useState<SupportConversation | null>(null)
    const [loading, setLoading] = useState(false)
    const [refreshing, setRefreshing] = useState(false)
    const [sending, setSending] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const loadedOnce = useRef(false)

    const applyInbox = useCallback((next: SupportInbox) => {
        setInbox(next)
        onUnreadChange(next.total_unread)
        if (next.active && selectedConversation?.id === next.active.id) {
            setSelectedConversation(next.active)
        }
    }, [onUnreadChange, selectedConversation?.id])

    const refresh = useCallback(async (showSpinner = false) => {
        if (showSpinner) setRefreshing(true)
        else if (!loadedOnce.current) setLoading(true)
        try {
            const next = await getMySupportInbox()
            applyInbox(next)
            setError(null)
            loadedOnce.current = true
            return next
        } catch (refreshError) {
            setError(refreshError instanceof Error ? refreshError.message : "Support is unavailable")
            return null
        } finally {
            setLoading(false)
            setRefreshing(false)
        }
    }, [applyInbox])

    useEffect(() => {
        if (!isFocused) return
        void refresh()
    }, [isFocused, refresh])

    useEffect(() => {
        if (!isFocused || !active) return
        const interval = setInterval(() => {
            void refresh()
        }, ACTIVE_POLL_INTERVAL_MS)
        return () => clearInterval(interval)
    }, [active, isFocused, refresh])

    useEffect(() => {
        const conversation = selectedConversation ?? inbox?.active
        if (!active || !conversation?.customer_unread_count) return
        void markMySupportConversationRead(conversation.id)
            .then(() => {
                const nextTotalUnread = Math.max(
                    0,
                    (inbox?.total_unread || 0) - conversation.customer_unread_count,
                )
                setInbox((current) => current ? {
                    ...current,
                    active: current.active?.id === conversation.id
                        ? { ...current.active, customer_unread_count: 0 }
                        : current.active,
                    total_unread: nextTotalUnread,
                } : current)
                setSelectedConversation((current) => current?.id === conversation.id
                    ? { ...current, customer_unread_count: 0 }
                    : current)
                onUnreadChange(nextTotalUnread)
            })
            .catch(() => undefined)
    }, [active, inbox?.active, inbox?.total_unread, onUnreadChange, selectedConversation])

    const createConversation = useCallback(async (payload: CreateSupportConversationPayload) => {
        setSending(true)
        try {
            const conversation = await createMySupportConversation(payload)
            const next: SupportInbox = {
                active: conversation,
                previous: inbox?.previous || [],
                total_unread: conversation.customer_unread_count,
            }
            applyInbox(next)
            setSelectedConversation(null)
            setError(null)
            return conversation
        } finally {
            setSending(false)
        }
    }, [applyInbox, inbox?.previous])

    const sendMessage = useCallback(async (payload: SendSupportMessagePayload) => {
        const conversation = inbox?.active
        if (!conversation) throw new Error("No active support conversation")
        setSending(true)
        try {
            const updated = await sendMySupportMessage(conversation.id, payload)
            applyInbox({
                ...inbox,
                active: updated,
                total_unread: updated.customer_unread_count,
            })
            setError(null)
            return updated
        } finally {
            setSending(false)
        }
    }, [applyInbox, inbox])

    const openPrevious = useCallback(async (conversationId: number) => {
        setLoading(true)
        try {
            const conversation = await getMySupportConversation(conversationId)
            setSelectedConversation(conversation)
            return conversation
        } finally {
            setLoading(false)
        }
    }, [])

    return {
        conversation: selectedConversation ?? inbox?.active ?? null,
        error,
        inbox,
        loading,
        refreshing,
        sending,
        createConversation,
        openPrevious,
        closePrevious: () => setSelectedConversation(null),
        refresh: () => refresh(true),
        sendMessage,
    }
}
