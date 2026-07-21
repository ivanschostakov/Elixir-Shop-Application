import { useCallback, useEffect, useRef, useState } from "react"
import { AppState } from "react-native"
import { useIsFocused } from "@react-navigation/native"

import { deleteCommunityMessage, editCommunityMessage, getCommunityMessages, getCommunityStatus, getCommunityTopics, markCommunityTopicRead, sendCommunityMessage } from "@/services/api/community"
import type { CommunityMessage, CommunityStatus, CommunityTopic, SendCommunityMessagePayload } from "@/services/api/community.types"

const MESSAGE_POLL_INTERVAL_MS = 2500
const TOPIC_POLL_INTERVAL_MS = 2500

function mergeMessages(current: CommunityMessage[], incoming: CommunityMessage[]) {
    const byId = new Map(current.map((message) => [message.id, message]))
    for (const message of incoming) byId.set(message.id, message)
    return [...byId.values()].sort((left, right) => left.id - right.id)
}

export function useCommunityChat(active: boolean, onUnreadChange?: (count: number) => void) {
    const isFocused = useIsFocused()
    const [status, setStatus] = useState<CommunityStatus | null>(null)
    const [topics, setTopics] = useState<CommunityTopic[]>([])
    const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null)
    const [messages, setMessages] = useState<CommunityMessage[]>([])
    const [loading, setLoading] = useState(false)
    const [refreshing, setRefreshing] = useState(false)
    const [loadingOlder, setLoadingOlder] = useState(false)
    const [hasMore, setHasMore] = useState(false)
    const [sending, setSending] = useState(false)
    const [mutatingMessageId, setMutatingMessageId] = useState<number | null>(null)
    const [error, setError] = useState<string | null>(null)
    const appActiveRef = useRef(AppState.currentState === "active")
    const hasLoadedStatusRef = useRef(false)
    const newestIdRef = useRef<number | null>(null)
    const lastReadIdRef = useRef<number | null>(null)
    const syncCursorRef = useRef<string | null>(null)
    const syncCursorIdRef = useRef(0)
    const selectedTopicIdRef = useRef<number | null>(null)

    const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null

    useEffect(() => {
        selectedTopicIdRef.current = selectedTopicId
    }, [selectedTopicId])

    const loadTopics = useCallback(async () => {
        const response = await getCommunityTopics()
        setTopics(response.topics)
        onUnreadChange?.(response.total_unread)
        return response
    }, [onUnreadChange])

    const loadStatus = useCallback(async (refresh = false) => {
        const response = await getCommunityStatus(refresh)
        setStatus(response)
        if (response.access === "granted") {
            await loadTopics()
        } else {
            setTopics([])
            onUnreadChange?.(0)
        }
        return response
    }, [loadTopics, onUnreadChange])

    const loadInitialMessages = useCallback(async (topicId: number, showLoading = true) => {
        if (showLoading) setLoading(true)
        setError(null)
        try {
            const response = await getCommunityMessages(topicId)
            if (selectedTopicIdRef.current !== topicId) return
            setMessages(response.messages)
            setHasMore(response.has_more)
            newestIdRef.current = response.newest_id
            syncCursorRef.current = response.sync_cursor
            syncCursorIdRef.current = response.sync_cursor_id
        } catch (loadError) {
            setError(loadError instanceof Error ? loadError.message : "Could not load messages")
        } finally {
            if (showLoading) setLoading(false)
        }
    }, [])

    useEffect(() => {
        if (!isFocused) return
        setLoading(true)
        const shouldRefreshMembership = hasLoadedStatusRef.current
        hasLoadedStatusRef.current = true
        void loadStatus(shouldRefreshMembership).catch((loadError) => {
            setError(loadError instanceof Error ? loadError.message : "Could not load the group")
        }).finally(() => setLoading(false))
    }, [isFocused, loadStatus])

    useEffect(() => {
        const subscription = AppState.addEventListener("change", (nextState) => {
            const becameActive = !appActiveRef.current && nextState === "active"
            appActiveRef.current = nextState === "active"
            if (!becameActive || !isFocused) return
            void loadStatus(true)
                .then((nextStatus) => {
                    const topicId = selectedTopicIdRef.current
                    if (nextStatus.access === "granted" && topicId) {
                        void loadInitialMessages(topicId, false)
                    }
                })
                .catch(() => undefined)
        })
        return () => subscription.remove()
    }, [isFocused, loadInitialMessages, loadStatus])

    useEffect(() => {
        if (!selectedTopicId) {
            setMessages([])
            setHasMore(false)
            newestIdRef.current = null
            syncCursorRef.current = null
            syncCursorIdRef.current = 0
            lastReadIdRef.current = null
            return
        }
        setMessages([])
        setHasMore(false)
        newestIdRef.current = null
        lastReadIdRef.current = null
        void loadInitialMessages(selectedTopicId)
    }, [loadInitialMessages, selectedTopicId])

    useEffect(() => {
        if (!isFocused || status?.access !== "granted") return
        let requestActive = false
        const topicInterval = setInterval(() => {
            if (!appActiveRef.current || requestActive) return
            requestActive = true
            void loadTopics()
                .catch(() => loadStatus(true).catch(() => undefined))
                .finally(() => { requestActive = false })
        }, TOPIC_POLL_INTERVAL_MS)
        return () => clearInterval(topicInterval)
    }, [isFocused, loadStatus, loadTopics, status?.access])

    useEffect(() => {
        if (!active || !isFocused || !selectedTopicId || status?.access !== "granted") return
        let requestActive = false
        const interval = setInterval(() => {
            if (!appActiveRef.current || requestActive) return
            requestActive = true
            void getCommunityMessages(selectedTopicId, { afterId: newestIdRef.current ?? undefined, changedAfter: syncCursorRef.current ?? undefined, changedAfterId: syncCursorIdRef.current })
                .then((response) => {
                    if (selectedTopicIdRef.current !== selectedTopicId) return
                    if (response.messages.length) setMessages((current) => mergeMessages(current, response.messages))
                    if (response.newest_id) {
                        newestIdRef.current = Math.max(newestIdRef.current ?? 0, response.newest_id)
                    }
                    syncCursorRef.current = response.sync_cursor
                    syncCursorIdRef.current = response.sync_cursor_id
                })
                .catch(() => loadStatus(true).catch(() => undefined))
                .finally(() => { requestActive = false })
        }, MESSAGE_POLL_INTERVAL_MS)
        return () => clearInterval(interval)
    }, [active, isFocused, loadStatus, selectedTopicId, status?.access])

    const refresh = useCallback(async () => {
        setRefreshing(true)
        setError(null)
        try {
            const nextStatus = await loadStatus(true)
            if (nextStatus.access === "granted" && selectedTopicIdRef.current) await loadInitialMessages(selectedTopicIdRef.current, false)
        } catch (refreshError) {
            setError(refreshError instanceof Error ? refreshError.message : "Could not refresh the group")
        } finally {
            setRefreshing(false)
        }
    }, [loadInitialMessages, loadStatus])

    const loadOlder = useCallback(async () => {
        if (!selectedTopicId || loadingOlder || !hasMore || !messages.length) return
        setLoadingOlder(true)
        try {
            const response = await getCommunityMessages(selectedTopicId, { beforeId: messages[0].id })
            setMessages((current) => mergeMessages(response.messages, current))
            setHasMore(response.has_more)
        } catch (loadError) {
            setError(loadError instanceof Error ? loadError.message : "Could not load earlier messages")
        } finally {
            setLoadingOlder(false)
        }
    }, [hasMore, loadingOlder, messages, selectedTopicId])

    const send = useCallback(async (payload: Omit<SendCommunityMessagePayload, "clientId">) => {
        if (!selectedTopicId || sending) return null
        setSending(true)
        try {
            const message = await sendCommunityMessage(selectedTopicId, { ...payload, clientId: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}` })
            setMessages((current) => mergeMessages(current, [message]))
            newestIdRef.current = Math.max(newestIdRef.current ?? 0, message.id)
            return message
        } finally {
            setSending(false)
        }
    }, [selectedTopicId, sending])

    const markRead = useCallback((messageId: number) => {
        const topicId = selectedTopicIdRef.current
        if (!topicId || messageId <= (lastReadIdRef.current ?? 0)) return
        lastReadIdRef.current = messageId
        void markCommunityTopicRead(topicId, messageId)
            .then(loadTopics)
            .catch(() => {
                if (lastReadIdRef.current === messageId) lastReadIdRef.current = null
            })
    }, [loadTopics])

    const edit = useCallback(async (messageId: number, text: string) => {
        if (!selectedTopicId || mutatingMessageId) return null
        setMutatingMessageId(messageId)
        try {
            const updated = await editCommunityMessage(selectedTopicId, messageId, text)
            setMessages((current) => mergeMessages(current, [updated]))
            return updated
        } finally {
            setMutatingMessageId(null)
        }
    }, [mutatingMessageId, selectedTopicId])

    const remove = useCallback(async (messageId: number) => {
        if (!selectedTopicId || mutatingMessageId) return false
        setMutatingMessageId(messageId)
        try {
            await deleteCommunityMessage(selectedTopicId, messageId)
            setMessages((current) => current.map((message) => message.id === messageId
                ? { ...message, attachments: [], can_delete: false, can_edit: false, is_deleted: true, text: "", unsupported_type: null }
                : message))
            await loadTopics()
            return true
        } finally {
            setMutatingMessageId(null)
        }
    }, [loadTopics, mutatingMessageId, selectedTopicId])

    return { error, hasMore, loading, loadingOlder, messages, mutatingMessageId, refreshing, selectedTopic, selectedTopicId, sending, status, topics, edit, loadOlder, markRead, refresh, remove, selectTopic: setSelectedTopicId, send }
}
