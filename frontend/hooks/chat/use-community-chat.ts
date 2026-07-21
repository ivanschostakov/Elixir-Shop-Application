import { useCallback, useEffect, useRef, useState } from "react"
import { AppState } from "react-native"
import { useIsFocused } from "@react-navigation/native"

import {
    deleteCommunityMessage,
    editCommunityMessage,
    getCommunityMessages,
    getCommunityStatus,
    getCommunityTopics,
    markCommunityTopicRead,
    sendCommunityMessage,
    toggleCommunityMessageReaction,
} from "@/services/api/community"
import type {
    CommunityMessage,
    CommunityStatus,
    CommunityTopic,
    SendCommunityMessagePayload,
} from "@/services/api/community.types"

const MESSAGE_POLL_INTERVAL_MS = 1250
const TOPIC_POLL_INTERVAL_MS = 5000
const FULL_RECONCILE_INTERVAL_MS = 45_000
const MAX_RECONNECT_DELAY_MS = 15_000

export type CommunityConnectionState = "connecting" | "live" | "reconnecting" | "offline"

function normalizeMessage(message: CommunityMessage): CommunityMessage {
    return {
        ...message,
        attachments: Array.isArray(message.attachments) ? message.attachments : [],
        reactions: Array.isArray(message.reactions) ? message.reactions : [],
    }
}

function normalizeMessages(messages: CommunityMessage[]) {
    return messages.map(normalizeMessage)
}

function mergeMessages(current: CommunityMessage[], incoming: CommunityMessage[]) {
    const byId = new Map(current.map((message) => [message.id, message]))
    for (const message of normalizeMessages(incoming)) byId.set(message.id, message)
    return [...byId.values()]
        .filter((message) => !message.is_deleted)
        .sort((left, right) => left.id - right.id)
}

function errorMessage(error: unknown, fallback: string) {
    return error instanceof Error && error.message ? error.message : fallback
}

export function useCommunityChat(
    active: boolean,
    onUnreadChange?: (count: number) => void,
    requestedTopicId?: number | null,
) {
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
    const [reactingMessageId, setReactingMessageId] = useState<number | null>(null)
    const [connectionState, setConnectionState] = useState<CommunityConnectionState>("connecting")
    const [error, setError] = useState<string | null>(null)

    const mountedRef = useRef(true)
    const activeRef = useRef(active)
    const focusedRef = useRef(isFocused)
    const appActiveRef = useRef(AppState.currentState === "active")
    const hasLoadedStatusRef = useRef(false)
    const selectedTopicIdRef = useRef<number | null>(null)
    const topicGenerationRef = useRef(0)
    const newestIdRef = useRef<number | null>(null)
    const syncCursorRef = useRef<string | null>(null)
    const syncCursorIdRef = useRef(0)
    const lastFullSyncAtRef = useRef(0)
    const messageQueueRef = useRef<Promise<void>>(Promise.resolve())
    const topicRequestRef = useRef<Promise<Awaited<ReturnType<typeof getCommunityTopics>>> | null>(null)
    const requestedTopicHandledRef = useRef<number | null>(null)
    const readRequestedIdRef = useRef(0)
    const readAcknowledgedIdRef = useRef(0)
    const readRequestRunningRef = useRef(false)
    const readRequestOwnerRef = useRef<{ generation: number; topicId: number } | null>(null)
    const readRetryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

    const selectedTopic = topics.find((topic) => topic.id === selectedTopicId) ?? null

    useEffect(() => {
        mountedRef.current = true
        return () => {
            mountedRef.current = false
            if (readRetryTimerRef.current) clearTimeout(readRetryTimerRef.current)
        }
    }, [])

    useEffect(() => {
        activeRef.current = active
        focusedRef.current = isFocused
    }, [active, isFocused])

    useEffect(() => {
        selectedTopicIdRef.current = selectedTopicId
    }, [selectedTopicId])

    const loadTopics = useCallback(async () => {
        if (topicRequestRef.current) return topicRequestRef.current
        const request = getCommunityTopics()
            .then((response) => {
                if (!mountedRef.current) return response
                setTopics(response.topics)
                onUnreadChange?.(response.total_unread)
                return response
            })
            .finally(() => {
                if (topicRequestRef.current === request) topicRequestRef.current = null
            })
        topicRequestRef.current = request
        return request
    }, [onUnreadChange])

    const loadStatus = useCallback(async (refresh = false) => {
        const response = await getCommunityStatus(refresh)
        if (!mountedRef.current) return response
        setStatus(response)
        if (response.access === "granted") {
            await loadTopics()
        } else {
            setTopics([])
            onUnreadChange?.(0)
        }
        return response
    }, [loadTopics, onUnreadChange])

    const syncMessages = useCallback((topicId: number, options: { full?: boolean; replace?: boolean; showLoading?: boolean } = {}) => {
        const generation = topicGenerationRef.current
        const operation = messageQueueRef.current
            .catch(() => undefined)
            .then(async () => {
                if (
                    !mountedRef.current ||
                    selectedTopicIdRef.current !== topicId ||
                    topicGenerationRef.current !== generation
                ) return

                if (options.showLoading) setLoading(true)
                try {
                    const response = options.full
                        ? await getCommunityMessages(topicId)
                        : await getCommunityMessages(topicId, {
                            afterId: newestIdRef.current ?? undefined,
                            changedAfter: syncCursorRef.current ?? undefined,
                            changedAfterId: syncCursorIdRef.current,
                        })

                    if (
                        !mountedRef.current ||
                        selectedTopicIdRef.current !== topicId ||
                        topicGenerationRef.current !== generation
                    ) return

                    const incoming = normalizeMessages(response.messages)
                    setMessages((current) => options.replace
                        ? incoming.filter((message) => !message.is_deleted)
                        : mergeMessages(current, incoming))
                    if (options.replace) setHasMore(response.has_more)
                    if (options.full) {
                        newestIdRef.current = response.newest_id
                        lastFullSyncAtRef.current = Date.now()
                    } else if (response.newest_id) {
                        newestIdRef.current = Math.max(newestIdRef.current ?? 0, response.newest_id)
                    }
                    // A full page only contains the newest messages. Preserve
                    // an existing change cursor so edits/deletes to older
                    // loaded bubbles are still reconciled after foregrounding.
                    if (!options.full || options.replace || !syncCursorRef.current) {
                        syncCursorRef.current = response.sync_cursor
                        syncCursorIdRef.current = response.sync_cursor_id
                    }
                    setConnectionState("live")
                    setError(null)
                } catch (syncError) {
                    if (mountedRef.current && selectedTopicIdRef.current === topicId) {
                        setError(errorMessage(syncError, "Could not update messages"))
                    }
                    throw syncError
                } finally {
                    if (options.showLoading && mountedRef.current && selectedTopicIdRef.current === topicId) {
                        setLoading(false)
                    }
                }
            })
        messageQueueRef.current = operation.catch(() => undefined)
        return operation
    }, [])

    useEffect(() => {
        if (!isFocused) return
        let cancelled = false
        const shouldRefresh = hasLoadedStatusRef.current
        if (!shouldRefresh) setLoading(true)
        hasLoadedStatusRef.current = true
        void loadStatus(shouldRefresh)
            .catch((loadError) => {
                if (!cancelled) setError(errorMessage(loadError, "Could not load the group"))
            })
            .finally(() => {
                if (!cancelled) setLoading(false)
            })
        return () => { cancelled = true }
    }, [isFocused, loadStatus])

    useEffect(() => {
        const subscription = AppState.addEventListener("change", (nextState) => {
            const becameActive = !appActiveRef.current && nextState === "active"
            appActiveRef.current = nextState === "active"
            if (!becameActive || !focusedRef.current) return
            void loadStatus(true)
                .then((nextStatus) => {
                    const topicId = selectedTopicIdRef.current
                    if (nextStatus.access === "granted" && topicId) {
                        return syncMessages(topicId, { full: true })
                    }
                    return undefined
                })
                .catch(() => undefined)
        })
        return () => subscription.remove()
    }, [loadStatus, syncMessages])

    useEffect(() => {
        if (!requestedTopicId || requestedTopicHandledRef.current === requestedTopicId) return
        if (status?.access !== "granted" || !topics.some((topic) => topic.id === requestedTopicId)) return
        requestedTopicHandledRef.current = requestedTopicId
        setSelectedTopicId(requestedTopicId)
    }, [requestedTopicId, status?.access, topics])

    useEffect(() => {
        topicGenerationRef.current += 1
        if (readRetryTimerRef.current) {
            clearTimeout(readRetryTimerRef.current)
            readRetryTimerRef.current = null
        }
        readRequestedIdRef.current = 0
        readAcknowledgedIdRef.current = 0
        setError(null)
        setLoadingOlder(false)

        if (!selectedTopicId) {
            setLoading(false)
            setMessages([])
            setHasMore(false)
            newestIdRef.current = null
            syncCursorRef.current = null
            syncCursorIdRef.current = 0
            lastFullSyncAtRef.current = 0
            return
        }

        setMessages([])
        setHasMore(false)
        newestIdRef.current = null
        syncCursorRef.current = null
        syncCursorIdRef.current = 0
        lastFullSyncAtRef.current = 0
        setConnectionState("connecting")
        void syncMessages(selectedTopicId, { full: true, replace: true, showLoading: true }).catch(() => undefined)
    }, [selectedTopicId, syncMessages])

    useEffect(() => {
        if (!isFocused || status?.access !== "granted") return
        let cancelled = false
        let timer: ReturnType<typeof setTimeout> | null = null

        const poll = async () => {
            if (cancelled) return
            if (appActiveRef.current) await loadTopics().catch(() => undefined)
            if (!cancelled) timer = setTimeout(() => { void poll() }, TOPIC_POLL_INTERVAL_MS)
        }

        timer = setTimeout(() => { void poll() }, TOPIC_POLL_INTERVAL_MS)
        return () => {
            cancelled = true
            if (timer) clearTimeout(timer)
        }
    }, [isFocused, loadTopics, status?.access])

    useEffect(() => {
        if (!active || !isFocused || !selectedTopicId || status?.access !== "granted") return
        let cancelled = false
        let timer: ReturnType<typeof setTimeout> | null = null
        let consecutiveFailures = 0

        const schedule = (delay: number) => {
            if (!cancelled) timer = setTimeout(() => { void poll() }, delay)
        }
        const poll = async () => {
            if (cancelled) return
            if (!appActiveRef.current) {
                schedule(MESSAGE_POLL_INTERVAL_MS)
                return
            }
            try {
                const needsFullReconcile = Date.now() - lastFullSyncAtRef.current >= FULL_RECONCILE_INTERVAL_MS
                await syncMessages(selectedTopicId, { full: needsFullReconcile })
                consecutiveFailures = 0
                schedule(MESSAGE_POLL_INTERVAL_MS)
            } catch {
                consecutiveFailures += 1
                if (!cancelled) setConnectionState(consecutiveFailures >= 4 ? "offline" : "reconnecting")
                schedule(Math.min(MESSAGE_POLL_INTERVAL_MS * (2 ** consecutiveFailures), MAX_RECONNECT_DELAY_MS))
            }
        }

        void poll()
        return () => {
            cancelled = true
            if (timer) clearTimeout(timer)
        }
    }, [active, isFocused, selectedTopicId, status?.access, syncMessages])

    const refresh = useCallback(async () => {
        setRefreshing(true)
        setError(null)
        try {
            const nextStatus = await loadStatus(true)
            const topicId = selectedTopicIdRef.current
            if (nextStatus.access === "granted" && topicId) {
                setConnectionState("connecting")
                await syncMessages(topicId, { full: true })
            }
        } catch (refreshError) {
            setConnectionState("offline")
            setError(errorMessage(refreshError, "Could not refresh the group"))
        } finally {
            if (mountedRef.current) setRefreshing(false)
        }
    }, [loadStatus, syncMessages])

    const loadOlder = useCallback(async () => {
        const topicId = selectedTopicIdRef.current
        if (!topicId || loadingOlder || !hasMore || !messages.length) return
        const generation = topicGenerationRef.current
        setLoadingOlder(true)
        try {
            const response = await getCommunityMessages(topicId, { beforeId: messages[0].id })
            if (selectedTopicIdRef.current !== topicId || topicGenerationRef.current !== generation) return
            setMessages((current) => mergeMessages(response.messages, current))
            setHasMore(response.has_more)
        } catch (loadError) {
            setError(errorMessage(loadError, "Could not load earlier messages"))
        } finally {
            if (mountedRef.current && selectedTopicIdRef.current === topicId) setLoadingOlder(false)
        }
    }, [hasMore, loadingOlder, messages])

    const send = useCallback(async (payload: Omit<SendCommunityMessagePayload, "clientId">) => {
        const topicId = selectedTopicIdRef.current
        if (!topicId || sending) return null
        setSending(true)
        try {
            const message = normalizeMessage(await sendCommunityMessage(topicId, {
                ...payload,
                clientId: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
            }))
            if (selectedTopicIdRef.current === topicId) {
                setMessages((current) => mergeMessages(current, [message]))
                newestIdRef.current = Math.max(newestIdRef.current ?? 0, message.id)
                setConnectionState("live")
            }
            void loadTopics().catch(() => undefined)
            return message
        } finally {
            if (mountedRef.current) setSending(false)
        }
    }, [loadTopics, sending])

    const flushReadQueue = useCallback(async () => {
        const topicId = selectedTopicIdRef.current
        if (!topicId || !activeRef.current || !focusedRef.current || !appActiveRef.current) return
        if (readRequestRunningRef.current) {
            if (!readRetryTimerRef.current) {
                readRetryTimerRef.current = setTimeout(() => {
                    readRetryTimerRef.current = null
                    void flushReadQueue()
                }, 100)
            }
            return
        }
        const generation = topicGenerationRef.current
        const owner = { generation, topicId }
        readRequestRunningRef.current = true
        readRequestOwnerRef.current = owner
        let failed = false
        try {
            while (
                mountedRef.current &&
                selectedTopicIdRef.current === topicId &&
                topicGenerationRef.current === generation &&
                readRequestedIdRef.current > readAcknowledgedIdRef.current
            ) {
                const targetId = readRequestedIdRef.current
                await markCommunityTopicRead(topicId, targetId)
                if (
                    selectedTopicIdRef.current !== topicId ||
                    topicGenerationRef.current !== generation
                ) break
                readAcknowledgedIdRef.current = targetId
            }
        } catch {
            failed = true
        } finally {
            if (readRequestOwnerRef.current === owner) {
                readRequestRunningRef.current = false
                readRequestOwnerRef.current = null
            }
        }
        if (
            failed &&
            mountedRef.current &&
            selectedTopicIdRef.current === topicId &&
            topicGenerationRef.current === generation
        ) {
            readRetryTimerRef.current = setTimeout(() => {
                readRetryTimerRef.current = null
                void flushReadQueue()
            }, 2000)
            return
        }
        if (
            mountedRef.current &&
            readRequestedIdRef.current > readAcknowledgedIdRef.current
        ) {
            void flushReadQueue()
            return
        }
        void loadTopics().catch(() => undefined)
    }, [loadTopics])

    const markRead = useCallback((messageId: number) => {
        if (!activeRef.current || !focusedRef.current || !appActiveRef.current) return
        if (!selectedTopicIdRef.current || messageId <= readRequestedIdRef.current) return
        readRequestedIdRef.current = messageId
        void flushReadQueue()
    }, [flushReadQueue])

    const edit = useCallback(async (messageId: number, text: string) => {
        const topicId = selectedTopicIdRef.current
        if (!topicId || mutatingMessageId) return null
        setMutatingMessageId(messageId)
        try {
            const updated = normalizeMessage(await editCommunityMessage(topicId, messageId, text))
            if (selectedTopicIdRef.current === topicId) setMessages((current) => mergeMessages(current, [updated]))
            void loadTopics().catch(() => undefined)
            return updated
        } finally {
            if (mountedRef.current) setMutatingMessageId(null)
        }
    }, [loadTopics, mutatingMessageId])

    const remove = useCallback(async (messageId: number) => {
        const topicId = selectedTopicIdRef.current
        if (!topicId || mutatingMessageId) return false
        setMutatingMessageId(messageId)
        try {
            await deleteCommunityMessage(topicId, messageId)
            if (selectedTopicIdRef.current === topicId) {
                setMessages((current) => current.filter((message) => message.id !== messageId))
            }
            await loadTopics()
            return true
        } finally {
            if (mountedRef.current) setMutatingMessageId(null)
        }
    }, [loadTopics, mutatingMessageId])

    const react = useCallback(async (messageId: number, emoji: string) => {
        const topicId = selectedTopicIdRef.current
        if (!topicId || reactingMessageId) return null
        setReactingMessageId(messageId)
        try {
            const reactions = await toggleCommunityMessageReaction(topicId, messageId, emoji)
            if (selectedTopicIdRef.current === topicId) {
                setMessages((current) => current.map((message) => message.id === messageId ? { ...message, reactions } : message))
            }
            return reactions
        } finally {
            if (mountedRef.current) setReactingMessageId(null)
        }
    }, [reactingMessageId])

    return {
        connectionState,
        error,
        hasMore,
        loading,
        loadingOlder,
        messages,
        mutatingMessageId,
        reactingMessageId,
        refreshing,
        selectedTopic,
        selectedTopicId,
        sending,
        status,
        topics,
        edit,
        loadOlder,
        markRead,
        react,
        refresh,
        remove,
        selectTopic: setSelectedTopicId,
        send,
    }
}
