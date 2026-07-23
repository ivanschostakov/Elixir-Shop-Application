import { useCallback, useEffect, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Image,
    ImageBackground,
    KeyboardAvoidingView,
    Platform,
    Pressable,
    RefreshControl,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import * as ImagePicker from "expo-image-picker"
import { useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ROUTES } from "@/constants/routes"
import { useSupportChat } from "@/hooks/chat/use-support-chat"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import type { SupportConversationStatus } from "@/services/api/support.types"
import { API_BASE_URL } from "@/services/api/constants"
import { getAuthTokens } from "@/services/auth/session"
import { CHAT_BACKGROUND_DARK, CHAT_BACKGROUND_LIGHT } from "@/screens/chat/chat-screen.constants"
import { ChatModeSwitcher, type ChatMode } from "@/screens/chat/chat-mode-switcher"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { createSupportChatStyles } from "@/screens/chat/support-chat-screen.styles"
import { spacing } from "@/theme/spacing"

type SupportChatScreenProps = {
    active: boolean
    communityUnreadCount: number
    mode: ChatMode
    onModeChange: (mode: ChatMode) => void
    onUnreadChange: (count: number) => void
    requestedConversationId: number | null
    supportUnreadCount: number
}

function createId() {
    if (typeof globalThis.crypto?.randomUUID === "function") return globalThis.crypto.randomUUID()
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`
}

function messageTime(value: string) {
    return new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" }).format(new Date(value))
}

function historyDate(value: string | null) {
    if (!value) return ""
    return new Intl.DateTimeFormat(undefined, { day: "2-digit", month: "short" }).format(new Date(value))
}

function attachmentSource(path: string) {
    const token = getAuthTokens()?.accessToken
    return {
        uri: new URL(path, API_BASE_URL).toString(),
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    }
}

export function SupportChatScreen({
    active,
    communityUnreadCount,
    mode,
    onModeChange,
    onUnreadChange,
    requestedConversationId,
    supportUnreadCount,
}: SupportChatScreenProps) {
    const styles = useThemeStyles(createSupportChatStyles)
    const chatStyles = useThemeStyles(createChatScreenStyles)
    const { isDark, palette, themeName } = useTheme()
    const { t } = useLanguage()
    const router = useRouter()
    const { top, bottom } = useSafeAreaInsets()
    const scrollRef = useRef<ScrollView | null>(null)
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableChatAttachment[]>([])
    const {
        closePrevious,
        conversation,
        createConversation,
        error,
        inbox,
        loading,
        openPrevious,
        refresh,
        refreshing,
        sendMessage,
        sending,
    } = useSupportChat(active, onUnreadChange)
    const headerTop = top + 8
    const composerBottom = Math.max(bottom, spacing.sm)
    const isHistorical = Boolean(conversation && conversation.id !== inbox?.active?.id)
    const hasContent = Boolean(draft.trim()) || attachments.length > 0

    useEffect(() => {
        if (!active || !requestedConversationId || conversation?.id === requestedConversationId) return
        if (inbox?.active?.id === requestedConversationId) {
            closePrevious()
            return
        }
        if (inbox?.previous.some((item) => item.id === requestedConversationId)) {
            void openPrevious(requestedConversationId)
        }
    }, [active, closePrevious, conversation?.id, inbox?.active?.id, inbox?.previous, openPrevious, requestedConversationId])

    useEffect(() => {
        if (!active || !conversation?.messages.length) return
        const frame = requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }))
        return () => cancelAnimationFrame(frame)
    }, [active, conversation?.messages.length])

    const pickImages = useCallback(async () => {
        if (!inbox?.active) {
            Alert.alert(t("chat.supportNewTitle"), t("chat.supportAttachmentAfterStart"))
            return
        }
        const result = await ImagePicker.launchImageLibraryAsync({
            allowsMultipleSelection: true,
            mediaTypes: ["images"],
            quality: 0.9,
            selectionLimit: Math.max(1, 4 - attachments.length),
        })
        if (result.canceled) return
        setAttachments((current) => [
            ...current,
            ...result.assets.slice(0, 4 - current.length).map((asset) => ({
                uri: asset.uri,
                fileName: asset.fileName || `support-${Date.now()}.jpg`,
                mimeType: asset.mimeType || "image/jpeg",
            })),
        ])
    }, [attachments.length, inbox?.active, t])

    const handleSend = useCallback(async () => {
        if (!hasContent || sending || isHistorical) return
        const text = draft.trim()
        try {
            if (!inbox?.active) {
                if (!text) {
                    Alert.alert(t("chat.supportNewTitle"), t("chat.supportFirstMessageRequired"))
                    return
                }
                await createConversation({
                    client_message_id: createId(),
                    subject: text.slice(0, 120),
                    message: text,
                })
            } else {
                await sendMessage({
                    clientMessageId: createId(),
                    message: text,
                    attachments,
                })
            }
            setDraft("")
            setAttachments([])
        } catch (sendError) {
            Alert.alert(
                t("chat.supportSendFailedTitle"),
                sendError instanceof Error ? sendError.message : t("chat.supportSendFailedMessage"),
            )
        }
    }, [attachments, createConversation, draft, hasContent, inbox?.active, isHistorical, sendMessage, sending, t])

    const statusLabels: Record<SupportConversationStatus, string> = {
        new: t("chat.supportStatusNew"),
        open: t("chat.supportStatusOpen"),
        waiting_customer: t("chat.supportStatusWaitingCustomer"),
        waiting_team: t("chat.supportStatusWaitingTeam"),
        resolved: t("chat.supportStatusResolved"),
        spam: t("chat.supportStatusSpam"),
    }

    return (
        <View pointerEvents={active ? "auto" : "none"} style={[styles.overlay, active ? null : styles.hidden]}>
            <View style={styles.screen}>
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_LIGHT} style={[chatStyles.backgroundImage, themeName === "dark" ? chatStyles.backgroundImageHidden : null]} />
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_DARK} style={[chatStyles.backgroundImage, themeName === "dark" ? null : chatStyles.backgroundImageHidden]} />
                <View pointerEvents="none" style={[chatStyles.backgroundScrim, isDark ? chatStyles.backgroundScrimDark : chatStyles.backgroundScrimLight]} />
                <View style={[styles.header, { top: headerTop }]}>
                    <Pressable accessibilityLabel={t("nav.back")} onPress={() => router.push(ROUTES.discover)} style={styles.backButton}>
                        <Text style={styles.backText}>‹</Text>
                    </Pressable>
                    <ChatModeSwitcher
                        mode={mode}
                        onChange={onModeChange}
                        supportUnreadCount={supportUnreadCount}
                        unreadCount={communityUnreadCount}
                    />
                </View>

                <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={styles.keyboard}>
                    <ScrollView
                        contentContainerStyle={[
                            styles.messagesContent,
                            { paddingTop: headerTop + 60, paddingBottom: spacing.md },
                        ]}
                        keyboardShouldPersistTaps="handled"
                        ref={scrollRef}
                        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { void refresh() }} tintColor={palette.primary} />}
                        style={styles.messages}
                    >
                        {inbox?.previous.length ? (
                            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.historyRow}>
                                {inbox.active && isHistorical ? (
                                    <Pressable onPress={closePrevious} style={styles.historyCard}>
                                        <Text style={styles.historyTitle}>{t("chat.supportCurrent")}</Text>
                                        <Text style={styles.historyMeta}>{inbox.active.subject}</Text>
                                    </Pressable>
                                ) : null}
                                {inbox.previous.map((item) => (
                                    <Pressable
                                        key={item.id}
                                        onPress={() => { void openPrevious(item.id) }}
                                        style={[styles.historyCard, conversation?.id === item.id ? styles.historyCardActive : null]}
                                    >
                                        <Text numberOfLines={1} style={styles.historyTitle}>{item.subject || `#${item.id}`}</Text>
                                        <Text style={styles.historyMeta}>{statusLabels[item.status]} · {historyDate(item.last_message_at)}</Text>
                                    </Pressable>
                                ))}
                            </ScrollView>
                        ) : null}

                        {loading && !conversation ? <ActivityIndicator color={palette.primary} size="large" /> : null}
                        {!loading && !conversation ? (
                            <View style={styles.state}>
                                <View style={styles.stateIcon}><Text style={styles.stateIconText}>?</Text></View>
                                <Text style={styles.stateTitle}>{t("chat.supportNewTitle")}</Text>
                                <Text style={styles.stateBody}>{t("chat.supportNewMessage")}</Text>
                            </View>
                        ) : null}
                        {conversation ? (
                            <>
                                <View style={styles.statusBar}>
                                    <Text style={styles.statusText}>{statusLabels[conversation.status]}</Text>
                                </View>
                                {conversation.messages.map((message) => {
                                    const mine = message.sender_type === "user"
                                    return (
                                        <View key={message.id} style={[styles.messageBlock, mine ? styles.messageBlockMine : null]}>
                                            <View style={[styles.messageBubble, mine ? styles.messageBubbleMine : null]}>
                                                {!mine ? <Text style={styles.author}>{message.author_name}{message.author_role ? ` · ${message.author_role}` : ""}</Text> : null}
                                                {message.attachments.map((attachment) => attachment.mime_type.startsWith("image/") ? (
                                                    <Image key={attachment.id} resizeMode="cover" source={attachmentSource(attachment.download_url)} style={styles.attachmentImage} />
                                                ) : (
                                                    <Text key={attachment.id} style={styles.attachmentName}>{attachment.original_filename}</Text>
                                                ))}
                                                {message.body ? <Text style={styles.messageText}>{message.body}</Text> : null}
                                                <Text style={styles.messageMeta}>
                                                    {messageTime(message.created_at)}
                                                    {mine ? message.read_at ? ` · ${t("chat.supportRead")}` : ` · ${t("chat.supportDelivered")}` : ""}
                                                </Text>
                                            </View>
                                        </View>
                                    )
                                })}
                            </>
                        ) : null}
                    </ScrollView>

                    {error ? <View style={styles.inlineError}><Text style={styles.inlineErrorText}>{error}</Text></View> : null}
                    {!isHistorical ? (
                        <View style={[styles.composer, { paddingBottom: composerBottom }]}>
                            {attachments.length ? (
                                <View style={styles.queuedRow}>
                                    {attachments.map((attachment, index) => (
                                        <View key={`${attachment.uri}-${index}`} style={styles.queuedCard}>
                                            <Text numberOfLines={1} style={styles.queuedName}>{attachment.fileName || t("chat.supportImage")}</Text>
                                            <Pressable onPress={() => setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))}>
                                                <Text style={styles.queuedRemove}>×</Text>
                                            </Pressable>
                                        </View>
                                    ))}
                                </View>
                            ) : null}
                            <View style={styles.composerRow}>
                                <Pressable onPress={() => { void pickImages() }} style={styles.circleButton}>
                                    <Text style={styles.circleButtonText}>＋</Text>
                                </Pressable>
                                <TextInput
                                    multiline
                                    onChangeText={setDraft}
                                    placeholder={t("chat.supportInputPlaceholder")}
                                    placeholderTextColor={isDark ? "#9BB0BF" : "#8B9092"}
                                    style={styles.input}
                                    value={draft}
                                />
                                <Pressable
                                    disabled={!hasContent || sending}
                                    onPress={() => { void handleSend() }}
                                    style={[styles.sendButton, !hasContent || sending ? styles.sendButtonDisabled : null]}
                                >
                                    {sending ? <ActivityIndicator color={palette.onPrimary} size="small" /> : <Text style={styles.sendText}>↑</Text>}
                                </Pressable>
                            </View>
                        </View>
                    ) : null}
                </KeyboardAvoidingView>
            </View>
        </View>
    )
}
