import { useCallback, useEffect, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    type AlertButton,
    Image,
    Keyboard,
    KeyboardAvoidingView,
    Linking,
    type NativeScrollEvent,
    type NativeSyntheticEvent,
    Platform,
    Pressable,
    RefreshControl,
    ScrollView,
    Text,
    TextInput,
    View,
} from "react-native"
import * as DocumentPicker from "expo-document-picker"
import * as ImagePicker from "expo-image-picker"
import { useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ROUTES } from "@/constants/routes"
import { useCommunityChat } from "@/hooks/chat/use-community-chat"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { createAttachmentFromImagePickerAsset } from "@/screens/chat/chat-attachments"
import { ChatModeSwitcher, type ChatMode } from "@/screens/chat/chat-mode-switcher"
import { createCommunityChatStyles } from "@/screens/chat/community-chat-screen.styles"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import { resolveApiMediaUri } from "@/services/api/media"
import type { CommunityMessage, CommunityTopic } from "@/services/api/community.types"
import { spacing } from "@/theme/spacing"

type CommunityChatScreenProps = {
    active: boolean
    mode: ChatMode
    onEnabledChange: (enabled: boolean) => void
    onModeChange: (mode: ChatMode) => void
    onUnreadChange: (count: number) => void
    unreadCount: number
}

function initials(name: string) {
    return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "?"
}

function formatTime(value: string) {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function formatTopicTime(value: string | undefined) {
    if (!value) return ""
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ""
    const now = new Date()
    return date.toDateString() === now.toDateString() ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : date.toLocaleDateString([], { day: "numeric", month: "short" })
}

function topicColor(topic: CommunityTopic) {
    if (topic.icon_color) return `#${topic.icon_color.toString(16).padStart(6, "0")}`
    const colors = ["#0A84FF", "#8A3FFC", "#B0124F", "#20A957", "#D97706"]
    return colors[topic.id % colors.length]
}

export function CommunityChatScreen({ active, mode, onEnabledChange, onModeChange, onUnreadChange, unreadCount }: CommunityChatScreenProps) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const { palette } = useTheme()
    const { t } = useLanguage()
    const router = useRouter()
    const { top, bottom } = useSafeAreaInsets()
    const scrollRef = useRef<ScrollView | null>(null)
    const shouldAutoScrollRef = useRef(true)
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableChatAttachment[]>([])
    const [composerHeight, setComposerHeight] = useState(110)
    const [keyboardVisible, setKeyboardVisible] = useState(false)
    const [replyTo, setReplyTo] = useState<CommunityMessage | null>(null)
    const [editingMessage, setEditingMessage] = useState<CommunityMessage | null>(null)
    const chat = useCommunityChat(active, onUnreadChange)
    const markRead = chat.markRead
    const headerTop = top + 8
    const contentTop = headerTop + 58

    const newestMessageId = chat.messages.at(-1)?.id ?? null

    useEffect(() => {
        if (!newestMessageId || !shouldAutoScrollRef.current) return
        const frame = requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }))
        markRead(newestMessageId)
        return () => cancelAnimationFrame(frame)
    }, [composerHeight, markRead, newestMessageId])

    useEffect(() => {
        if (chat.status) onEnabledChange(chat.status.enabled)
    }, [chat.status, onEnabledChange])

    useEffect(() => {
        shouldAutoScrollRef.current = true
        setDraft("")
        setReplyTo(null)
        setEditingMessage(null)
        setAttachments([])
    }, [chat.selectedTopicId])

    useEffect(() => {
        const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow"
        const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide"
        const showSubscription = Keyboard.addListener(showEvent, (event) => {
            Keyboard.scheduleLayoutAnimation(event)
            setKeyboardVisible(true)
            if (shouldAutoScrollRef.current) {
                requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }))
            }
        })
        const hideSubscription = Keyboard.addListener(hideEvent, (event) => {
            Keyboard.scheduleLayoutAnimation(event)
            setKeyboardVisible(false)
        })
        return () => {
            showSubscription.remove()
            hideSubscription.remove()
        }
    }, [])

    const handleMessagesScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        const distanceFromBottom = contentSize.height - (contentOffset.y + layoutMeasurement.height)
        const isNearBottom = distanceFromBottom <= 56
        shouldAutoScrollRef.current = isNearBottom
        if (isNearBottom && newestMessageId) markRead(newestMessageId)
    }, [markRead, newestMessageId])

    const pickPhotos = useCallback(async () => {
        try {
            const result = await ImagePicker.launchImageLibraryAsync({ allowsMultipleSelection: true, mediaTypes: ["images"], quality: 0.9 })
            if (!result.canceled) setAttachments((current) => [...current, ...result.assets.map(createAttachmentFromImagePickerAsset)].slice(0, 6))
        } catch {
            Alert.alert(t("chat.communityAttachmentFailedTitle"), t("chat.communityAttachmentFailedMessage"))
        }
    }, [t])

    const pickDocuments = useCallback(async () => {
        try {
            const result = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: true, type: "*/*" })
            if (!result.canceled) setAttachments((current) => [...current, ...result.assets.map((asset) => ({ fileName: asset.name, mimeType: asset.mimeType ?? "application/octet-stream", uri: asset.uri }))].slice(0, 6))
        } catch {
            Alert.alert(t("chat.communityAttachmentFailedTitle"), t("chat.communityAttachmentFailedMessage"))
        }
    }, [t])

    const openAttachmentMenu = useCallback(() => {
        Alert.alert(t("chat.communityAddAttachment"), undefined, [
            { text: t("chat.communityChoosePhoto"), onPress: () => { void pickPhotos() } },
            { text: t("chat.communityChooseFile"), onPress: () => { void pickDocuments() } },
            { text: t("common.cancel"), style: "cancel" },
        ])
    }, [pickDocuments, pickPhotos, t])

    const handleSend = useCallback(async () => {
        const text = draft.trim()
        if ((!text && !attachments.length) || chat.sending || chat.mutatingMessageId) return
        if (editingMessage) {
            if (!text) return
            try {
                await chat.edit(editingMessage.id, text)
                setEditingMessage(null)
                setDraft("")
            } catch (error) {
                Alert.alert(t("chat.communityEditFailedTitle"), error instanceof Error ? error.message : t("chat.communityEditFailedMessage"))
            }
            return
        }
        shouldAutoScrollRef.current = true
        setDraft("")
        const pendingAttachments = attachments
        setAttachments([])
        try {
            await chat.send({ text, attachments: pendingAttachments, replyToMessageId: replyTo?.id })
            setReplyTo(null)
        } catch (error) {
            setDraft(text)
            setAttachments(pendingAttachments)
            Alert.alert(t("chat.communitySendFailedTitle"), error instanceof Error ? error.message : t("chat.communitySendFailedMessage"))
        }
    }, [attachments, chat, draft, editingMessage, replyTo?.id, t])

    const handleMessageLongPress = useCallback((message: CommunityMessage) => {
        if (message.is_deleted) return
        const actions: AlertButton[] = [
            { text: t("chat.communityReplyAction"), onPress: () => { setEditingMessage(null); setReplyTo(message) } },
        ]
        if (message.can_edit) {
            actions.push({
                text: t("chat.communityEditAction"),
                onPress: () => {
                    setReplyTo(null)
                    setAttachments([])
                    setEditingMessage(message)
                    setDraft(message.text)
                },
            })
            actions.push({
                text: t("chat.communityDeleteAction"),
                onPress: () => {
                    Alert.alert(t("chat.communityDeleteConfirmTitle"), t("chat.communityDeleteConfirmMessage"), [
                        { text: t("common.cancel"), style: "cancel" },
                        {
                            text: t("chat.communityDeleteAction"),
                            style: "destructive",
                            onPress: () => {
                                void chat.remove(message.id).catch((error) => {
                                    Alert.alert(t("chat.communityDeleteFailedTitle"), error instanceof Error ? error.message : t("chat.communityDeleteFailedMessage"))
                                })
                            },
                        },
                    ])
                },
            })
        }
        actions.push({ text: t("common.cancel"), style: "cancel" })
        Alert.alert(t("chat.communityMessageActions"), undefined, actions)
    }, [chat, t])

    const handleBack = () => {
        if (chat.selectedTopicId) {
            chat.selectTopic(null)
            return
        }
        router.push(ROUTES.discover)
    }

    return (
        <View pointerEvents={active ? "auto" : "none"} style={[styles.overlay, active ? null : styles.hidden]}>
            <View style={styles.screen}>
                <View style={[styles.header, { top: headerTop }]}>
                    <Pressable accessibilityLabel={t("nav.back")} onPress={handleBack} style={styles.backButton}>
                        <Text style={styles.backText}>‹</Text>
                    </Pressable>
                    <ChatModeSwitcher mode={mode} onChange={onModeChange} unreadCount={unreadCount} />
                </View>

                <View style={[styles.content, { paddingTop: contentTop }]}>
                    {chat.loading && !chat.status ? <View style={styles.stateCenter}><ActivityIndicator color={palette.primary} size="large" /></View> : null}
                    {!chat.loading && chat.status?.access !== "granted" ? (
                        <CommunityAccessState actionUrl={chat.status?.action_url ?? null} enabled={chat.status?.enabled ?? false} onRefresh={() => { void chat.refresh() }} state={chat.status?.access ?? "temporarily_unavailable"} />
                    ) : null}
                    {chat.status?.access === "granted" && !chat.selectedTopic ? (
                        <TopicList onOpen={chat.selectTopic} onRefresh={() => { void chat.refresh() }} refreshing={chat.refreshing} status={chat.status} topics={chat.topics} />
                    ) : null}
                    {chat.status?.access === "granted" && chat.selectedTopic ? (
                        <View style={styles.content}>
                            <View style={styles.topicHeader}>
                                <Text numberOfLines={1} style={styles.topicHeaderTitle}>{chat.selectedTopic.name}</Text>
                                <Text style={styles.topicHeaderStatus}>{chat.selectedTopic.is_closed ? t("chat.communityClosed") : t("chat.communityMemberChat")}</Text>
                            </View>
                        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "position" : "height"} contentContainerStyle={styles.keyboardContent} keyboardVerticalOffset={0} style={styles.content}>
                            <View style={styles.keyboardContent}>
                            <ScrollView contentContainerStyle={[styles.messageContent, { paddingBottom: composerHeight + spacing.sm }]} keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"} keyboardShouldPersistTaps="handled" maintainVisibleContentPosition={{ minIndexForVisible: 0 }} onScroll={handleMessagesScroll} ref={scrollRef} refreshControl={<RefreshControl onRefresh={() => { void chat.refresh() }} refreshing={chat.refreshing} tintColor={palette.primary} />} scrollEventThrottle={16} style={styles.messageScroll}>
                                {chat.hasMore ? <Pressable disabled={chat.loadingOlder} onPress={() => { void chat.loadOlder() }} style={styles.loadOlder}>{chat.loadingOlder ? <ActivityIndicator color={palette.primary} size="small" /> : <Text style={styles.loadOlderText}>{t("chat.communityLoadOlder")}</Text>}</Pressable> : null}
                                {!chat.messages.length && !chat.loading ? <View style={styles.stateCenter}><View style={styles.stateIcon}><Text style={styles.stateIconText}>✦</Text></View><Text style={styles.stateTitle}>{t("chat.communityNoMessagesTitle")}</Text><Text style={styles.stateBody}>{t("chat.communityNoMessagesMessage")}</Text></View> : null}
                                {chat.messages.map((message) => <CommunityMessageBubble key={message.id} message={message} onLongPress={handleMessageLongPress} />)}
                            </ScrollView>
                            {chat.error ? <View style={styles.inlineError}><Text style={styles.inlineErrorText}>{chat.error}</Text></View> : null}
                            <View onLayout={(event) => setComposerHeight(event.nativeEvent.layout.height)} style={[styles.composer, { paddingBottom: keyboardVisible ? spacing.sm : Math.max(bottom, spacing.sm) }]}>
                                {editingMessage ? <View style={styles.replyComposer}><View style={styles.replyComposerCopy}><Text style={styles.replyComposerTitle}>{t("chat.communityEditingMessage")}</Text><Text numberOfLines={1} style={styles.replyComposerText}>{editingMessage.text}</Text></View><Pressable onPress={() => { setEditingMessage(null); setDraft("") }}><Text style={styles.closeReply}>×</Text></Pressable></View> : null}
                                {replyTo ? <View style={styles.replyComposer}><View style={styles.replyComposerCopy}><Text style={styles.replyComposerTitle}>{t("chat.communityReplyingTo")} {replyTo.author.full_name}</Text><Text numberOfLines={1} style={styles.replyComposerText}>{replyTo.text || t("chat.attachmentFallbackMessage")}</Text></View><Pressable onPress={() => setReplyTo(null)}><Text style={styles.closeReply}>×</Text></Pressable></View> : null}
                                {attachments.length ? <ScrollView horizontal contentContainerStyle={styles.attachmentStrip} showsHorizontalScrollIndicator={false}>{attachments.map((attachment, index) => <View key={`${attachment.uri}-${index}`} style={styles.queuedAttachment}><Text numberOfLines={1} style={styles.queuedAttachmentName}>{attachment.fileName ?? t("chat.attachmentFallbackMessage")}</Text><Pressable onPress={() => setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))}><Text style={styles.queuedAttachmentRemove}>×</Text></Pressable></View>)}</ScrollView> : null}
                                {chat.selectedTopic.is_closed ? <View style={styles.replyComposer}><Text style={styles.replyComposerText}>{t("chat.communityClosedMessage")}</Text></View> : <View style={styles.composerRow}><Pressable accessibilityLabel={t("chat.communityAddAttachment")} disabled={Boolean(editingMessage)} onPress={openAttachmentMenu} style={[styles.composerButton, editingMessage ? styles.sendButtonDisabled : null]}><Text style={styles.composerButtonText}>＋</Text></Pressable><TextInput multiline onChangeText={setDraft} placeholder={editingMessage ? t("chat.communityEditingMessage") : t("chat.communityInputPlaceholder")} placeholderTextColor={palette.mutedText} style={styles.composerInput} textAlignVertical="top" value={draft} /><Pressable disabled={chat.sending || Boolean(chat.mutatingMessageId) || (!draft.trim() && !attachments.length)} onPress={() => { void handleSend() }} style={[styles.sendButton, chat.sending || chat.mutatingMessageId || (!draft.trim() && !attachments.length) ? styles.sendButtonDisabled : null]}>{chat.sending || chat.mutatingMessageId === editingMessage?.id ? <ActivityIndicator color={palette.onPrimary} size="small" /> : <Text style={styles.sendButtonText}>{editingMessage ? "✓" : "↑"}</Text>}</Pressable></View>}
                            </View>
                            </View>
                        </KeyboardAvoidingView>
                        </View>
                    ) : null}
                </View>
            </View>
        </View>
    )
}

function CommunityAccessState({ actionUrl, enabled, onRefresh, state }: { actionUrl: string | null; enabled: boolean; onRefresh: () => void; state: string }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const { t } = useLanguage()
    const copy = !enabled ? { icon: "✦", title: t("chat.communityDisabledTitle"), body: t("chat.communityDisabledMessage"), action: null } : state === "telegram_link_required" ? { icon: "↗", title: t("chat.communityLinkTitle"), body: t("chat.communityLinkMessage"), action: t("chat.communityLinkAction") } : state === "membership_required" ? { icon: "＋", title: t("chat.communityJoinTitle"), body: t("chat.communityJoinMessage"), action: t("chat.communityJoinAction") } : { icon: "…", title: t("chat.communityUnavailableTitle"), body: t("chat.communityUnavailableMessage"), action: null }
    return <View style={styles.stateCenter}><View style={styles.stateIcon}><Text style={styles.stateIconText}>{copy.icon}</Text></View><Text style={styles.stateTitle}>{copy.title}</Text><Text style={styles.stateBody}>{copy.body}</Text>{copy.action && actionUrl ? <Pressable onPress={() => { void Linking.openURL(actionUrl) }} style={styles.primaryButton}><Text style={styles.primaryButtonText}>{copy.action}</Text></Pressable> : null}<Pressable onPress={onRefresh} style={styles.secondaryButton}><Text style={styles.secondaryButtonText}>{t("chat.communityRefresh")}</Text></Pressable></View>
}

function TopicList({ onOpen, onRefresh, refreshing, status, topics }: { onOpen: (topicId: number) => void; onRefresh: () => void; refreshing: boolean; status: { group: { title: string; image_url: string | null } | null }; topics: CommunityTopic[] }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const { palette } = useTheme()
    const { t } = useLanguage()
    const title = status.group?.title ?? t("chat.modeGroup")
    return <ScrollView contentContainerStyle={styles.topicsContent} refreshControl={<RefreshControl onRefresh={onRefresh} refreshing={refreshing} tintColor={palette.primary} />}><View style={styles.groupHero}><CommunityGroupAvatar name={title} uri={status.group?.image_url} /><View style={styles.groupCopy}><Text style={styles.groupTitle}>{title}</Text><Text style={styles.groupSubtitle}>{t("chat.communityTopicsSubtitle")}</Text></View></View><Text style={styles.sectionLabel}>{t("chat.communityTopicsTitle")}</Text>{!topics.length ? <View style={styles.stateCenter}><Text style={styles.stateTitle}>{t("chat.communityNoTopicsTitle")}</Text><Text style={styles.stateBody}>{t("chat.communityNoTopicsMessage")}</Text></View> : topics.map((topic) => <Pressable key={topic.id} onPress={() => onOpen(topic.id)} style={({ pressed }) => [styles.topicCard, pressed ? styles.topicCardPressed : null]}><View style={[styles.topicIcon, { backgroundColor: topicColor(topic) }]}><Text style={styles.topicIconText}>#</Text></View><View style={styles.topicCopy}><View style={styles.topicTitleRow}><Text numberOfLines={1} style={styles.topicTitle}>{topic.name}</Text>{topic.is_closed ? <View style={styles.closedPill}><Text style={styles.closedText}>{t("chat.communityClosed")}</Text></View> : null}</View><Text numberOfLines={1} style={styles.topicPreview}>{topic.last_message ? `${topic.last_message.author.full_name}: ${topic.last_message.is_deleted ? t("chat.communityDeletedMessage") : topic.last_message.text || t("chat.attachmentFallbackMessage")}` : t("chat.communityNoActivity")}</Text></View><View style={styles.topicMeta}><Text style={styles.topicTime}>{formatTopicTime(topic.last_message?.created_at)}</Text>{topic.unread_count ? <View style={styles.unreadBadge}><Text style={styles.unreadText}>{topic.unread_count > 99 ? "99+" : topic.unread_count}</Text></View> : null}</View></Pressable>)}</ScrollView>
}

function CommunityGroupAvatar({ name, uri }: { name: string; uri: string | null | undefined }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const resolvedUri = resolveApiMediaUri(uri)
    const [failedUri, setFailedUri] = useState<string | null>(null)
    const shouldShowImage = Boolean(resolvedUri && resolvedUri !== failedUri)
    return shouldShowImage ? <Image onError={() => setFailedUri(resolvedUri)} resizeMode="cover" source={{ uri: resolvedUri as string }} style={styles.groupAvatar} /> : <View style={[styles.groupAvatar, styles.groupAvatarFallback]}><Text style={styles.groupAvatarText}>{initials(name)}</Text></View>
}

function CommunityMessageBubble({ message, onLongPress }: { message: CommunityMessage; onLongPress: (message: CommunityMessage) => void }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const { t } = useLanguage()
    const delivery = message.delivery_status === "queued" || message.delivery_status === "sending" ? t("chat.communityPending") : message.delivery_status === "failed" ? t("chat.communityFailed") : message.delivery_status === "delivery_unknown" ? t("chat.communityUnknown") : ""
    const meta = [formatTime(message.created_at), message.is_edited && !message.is_deleted ? t("chat.communityEdited") : "", delivery].filter(Boolean).join(" · ")
    return <View style={[styles.messageRow, message.author.is_current_user ? styles.messageRowMine : null]}><CommunityAuthorAvatar name={message.author.full_name} uri={message.author.avatar_url} /><Pressable onLongPress={() => onLongPress(message)} style={[styles.messageBubble, message.author.is_current_user ? styles.messageBubbleMine : null, message.is_deleted ? styles.messageBubbleDeleted : null]}><Text style={styles.authorName}>{message.author.full_name}</Text>{message.is_deleted ? <Text style={styles.deletedMessageText}>{t("chat.communityDeletedMessage")}</Text> : <>{message.reply_to ? <View style={styles.replyPreview}><Text style={styles.replyAuthor}>{message.reply_to.author_name}</Text><Text numberOfLines={2} style={styles.replyText}>{message.reply_to.text}</Text></View> : null}{message.attachments.map((attachment) => attachment.kind === "image" && attachment.media_url ? <CommunityMessageImage key={attachment.id} fallbackUrl={message.telegram_url} uri={attachment.media_url} /> : <Pressable key={attachment.id} onPress={() => { const url = resolveApiMediaUri(attachment.media_url) ?? message.telegram_url; if (url) void Linking.openURL(url) }} style={styles.documentCard}><Text style={styles.documentIcon}>▧</Text><Text numberOfLines={2} style={styles.documentName}>{attachment.filename}</Text></Pressable>)}{message.text ? <Text style={styles.messageText}>{message.text}</Text> : null}{message.unsupported_type ? <View style={styles.unsupportedCard}><Text style={styles.unsupportedText}>{t("chat.communityUnsupported")}</Text>{message.telegram_url ? <Pressable onPress={() => { void Linking.openURL(message.telegram_url as string) }}><Text style={styles.telegramLink}>{t("chat.communityOpenTelegram")}</Text></Pressable> : null}</View> : null}</>}<Text style={styles.messageMeta}>{meta}</Text></Pressable></View>
}

function CommunityAuthorAvatar({ name, uri }: { name: string; uri: string | null }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const resolvedUri = resolveApiMediaUri(uri)
    const [failedUri, setFailedUri] = useState<string | null>(null)
    const shouldShowImage = Boolean(resolvedUri && resolvedUri !== failedUri)
    return shouldShowImage ? <Image onError={() => setFailedUri(resolvedUri)} resizeMode="cover" source={{ uri: resolvedUri as string }} style={styles.authorAvatar} /> : <View style={[styles.authorAvatar, styles.avatarFallback]}><Text style={styles.avatarInitials}>{initials(name)}</Text></View>
}

function CommunityMessageImage({ fallbackUrl, uri }: { fallbackUrl: string | null; uri: string }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const { t } = useLanguage()
    const resolvedUri = resolveApiMediaUri(uri)
    const [failedUri, setFailedUri] = useState<string | null>(null)
    const failed = Boolean(resolvedUri && resolvedUri === failedUri)
    const openUrl = failed ? fallbackUrl : resolvedUri
    if (!resolvedUri || failed) {
        return <Pressable disabled={!openUrl} onPress={() => { if (openUrl) void Linking.openURL(openUrl) }} style={styles.documentCard}><Text style={styles.documentIcon}>▧</Text><Text numberOfLines={2} style={styles.documentName}>{t("chat.attachmentFallbackMessage")}</Text></Pressable>
    }
    return <Pressable onPress={() => { void Linking.openURL(resolvedUri) }}><Image onError={() => setFailedUri(resolvedUri)} resizeMode="cover" source={{ uri: resolvedUri }} style={styles.messageImage} /></Pressable>
}
