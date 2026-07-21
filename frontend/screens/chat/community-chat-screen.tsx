import { useCallback, useEffect, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    type AlertButton,
    Image,
    ImageBackground,
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
import * as Application from "expo-application"
import { useCameraPermissions } from "expo-camera"
import {
    RecordingPresets,
    requestRecordingPermissionsAsync,
    setAudioModeAsync,
    useAudioRecorder,
    useAudioRecorderState,
} from "expo-audio"
import * as DocumentPicker from "expo-document-picker"
import * as ImagePicker from "expo-image-picker"
import { useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import Svg, { Path } from "react-native-svg"

import AttachmentSvgIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import { ROUTES } from "@/constants/routes"
import { useCommunityChat } from "@/hooks/chat/use-community-chat"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import {
    createAttachmentFromImagePickerAsset,
    formatVoiceDuration,
    getVoiceRecordingFilename,
    getVoiceRecordingMimeType,
} from "@/screens/chat/chat-attachments"
import { ChatEmojiPicker, COMMUNITY_REACTION_EMOJIS } from "@/screens/chat/chat-emoji-picker"
import { ChatModeSwitcher, type ChatMode } from "@/screens/chat/chat-mode-switcher"
import { AttachmentSheet, QueuedAttachmentStrip } from "@/screens/chat/chat-screen.attachments"
import {
    type AttachmentMode,
    CHAT_BACKGROUND_DARK,
    CHAT_BACKGROUND_LIGHT,
    CHAT_IDLE_AUDIO_MODE,
    CHAT_RECORDING_AUDIO_MODE,
    IOS_MINIMUM_VOICE_RECORDING_BUILD,
} from "@/screens/chat/chat-screen.constants"
import { SendActionButton } from "@/screens/chat/chat-screen.core-components"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { createCommunityChatStyles } from "@/screens/chat/community-chat-screen.styles"
import { transcribeMyAiChatVoice } from "@/services/api/ai-chat"
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

function nativeBuildNumber() {
    const parsedBuild = Number(Application.nativeBuildVersion)
    return Number.isFinite(parsedBuild) ? parsedBuild : 0
}

export function CommunityChatScreen({ active, mode, onEnabledChange, onModeChange, onUnreadChange, unreadCount }: CommunityChatScreenProps) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const chatStyles = useThemeStyles(createChatScreenStyles)
    const { isDark, palette, themeName } = useTheme()
    const { t } = useLanguage()
    const router = useRouter()
    const { top, bottom } = useSafeAreaInsets()
    const [cameraPermission, requestCameraPermission] = useCameraPermissions()
    const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY)
    const audioRecorderState = useAudioRecorderState(audioRecorder, 200)
    const scrollRef = useRef<ScrollView | null>(null)
    const shouldAutoScrollRef = useRef(true)
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableChatAttachment[]>([])
    const [attachmentMode, setAttachmentMode] = useState<AttachmentMode>("photo")
    const [attachmentSheetVisible, setAttachmentSheetVisible] = useState(false)
    const [composerHeight, setComposerHeight] = useState(110)
    const [emojiPickerVisible, setEmojiPickerVisible] = useState(false)
    const [keyboardVisible, setKeyboardVisible] = useState(false)
    const [voiceRecording, setVoiceRecording] = useState(false)
    const [voiceTranscribing, setVoiceTranscribing] = useState(false)
    const [replyTo, setReplyTo] = useState<CommunityMessage | null>(null)
    const [editingMessage, setEditingMessage] = useState<CommunityMessage | null>(null)
    const [reactionPickerMessageId, setReactionPickerMessageId] = useState<number | null>(null)
    const chat = useCommunityChat(active, onUnreadChange)
    const markRead = chat.markRead
    const headerTop = top + 8
    const contentTop = headerTop + 58
    const composerBottomInset = keyboardVisible ? spacing.sm : Math.max(bottom, spacing.sm)
    const voiceStatusVisible = voiceRecording || voiceTranscribing
    const hasComposerContent = Boolean(draft.trim()) || attachments.length > 0
    const voiceRecordingSupported = __DEV__ || Platform.OS !== "ios" || nativeBuildNumber() >= IOS_MINIMUM_VOICE_RECORDING_BUILD
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
        setEmojiPickerVisible(false)
        setReactionPickerMessageId(null)
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

    useEffect(() => () => {
        try {
            void audioRecorder.stop().catch(() => undefined)
        } catch {
            // The native recorder may already be released during unmount.
        }
    }, [audioRecorder])

    const handleMessagesScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        const distanceFromBottom = contentSize.height - (contentOffset.y + layoutMeasurement.height)
        const isNearBottom = distanceFromBottom <= 56
        shouldAutoScrollRef.current = isNearBottom
        if (isNearBottom && newestMessageId) markRead(newestMessageId)
    }, [markRead, newestMessageId])

    const appendAttachments = useCallback((items: UploadableChatAttachment[]) => {
        setAttachments((current) => [...current, ...items].slice(0, 6))
    }, [])

    const closeAttachmentSheet = useCallback(() => setAttachmentSheetVisible(false), [])

    const openAttachmentSheet = useCallback(() => {
        Keyboard.dismiss()
        setEmojiPickerVisible(false)
        setAttachmentMode("photo")
        setAttachmentSheetVisible(true)
    }, [])

    const openGallery = useCallback(async () => {
        try {
            const result = await ImagePicker.launchImageLibraryAsync({ allowsMultipleSelection: true, mediaTypes: ["images"], quality: 0.92 })
            if (!result.canceled) appendAttachments(result.assets.map(createAttachmentFromImagePickerAsset))
            closeAttachmentSheet()
        } catch {
            Alert.alert(t("chat.communityAttachmentFailedTitle"), t("chat.communityAttachmentFailedMessage"))
        }
    }, [appendAttachments, closeAttachmentSheet, t])

    const openCamera = useCallback(async () => {
        try {
            let granted = cameraPermission?.granted === true
            if (!granted) granted = (await requestCameraPermission()).granted
            if (!granted) {
                Alert.alert(t("chat.attachmentsPhotoPermissionTitle"), t("chat.attachmentsPhotoPermissionMessage"))
                return
            }
            const result = await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.92 })
            if (!result.canceled) appendAttachments(result.assets.map(createAttachmentFromImagePickerAsset))
            closeAttachmentSheet()
        } catch {
            Alert.alert(t("chat.communityAttachmentFailedTitle"), t("chat.communityAttachmentFailedMessage"))
        }
    }, [appendAttachments, cameraPermission?.granted, closeAttachmentSheet, requestCameraPermission, t])

    const pickFiles = useCallback(async () => {
        try {
            const result = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, multiple: true, type: "*/*" })
            if (!result.canceled) appendAttachments(result.assets.map((asset) => ({ fileName: asset.name, mimeType: asset.mimeType ?? "application/octet-stream", uri: asset.uri })))
            closeAttachmentSheet()
        } catch {
            Alert.alert(t("chat.communityAttachmentFailedTitle"), t("chat.communityAttachmentFailedMessage"))
        }
    }, [appendAttachments, closeAttachmentSheet, t])

    const startVoiceRecording = useCallback(async () => {
        if (chat.sending || voiceTranscribing) return
        if (!voiceRecordingSupported) {
            Alert.alert(t("chat.voiceUpdateRequiredTitle"), t("chat.voiceUpdateRequiredMessage"))
            return
        }
        Keyboard.dismiss()
        setEmojiPickerVisible(false)
        try {
            const permission = await requestRecordingPermissionsAsync()
            if (!permission.granted) {
                Alert.alert(t("chat.voicePermissionTitle"), t("chat.voicePermissionMessage"))
                return
            }
            await setAudioModeAsync(CHAT_RECORDING_AUDIO_MODE)
            await audioRecorder.prepareToRecordAsync()
            audioRecorder.record()
            setVoiceRecording(true)
        } catch {
            setVoiceRecording(false)
            Alert.alert(t("chat.voiceTranscriptionFailedTitle"), t("chat.voiceTranscriptionFailedMessage"))
            await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined)
        }
    }, [audioRecorder, chat.sending, t, voiceRecordingSupported, voiceTranscribing])

    const stopVoiceRecording = useCallback(async () => {
        if (!voiceRecording || voiceTranscribing) return
        setVoiceRecording(false)
        setVoiceTranscribing(true)
        let transcribedText = ""
        try {
            await audioRecorder.stop()
            const audioUri = audioRecorder.uri ?? audioRecorder.getStatus().url
            await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE)
            if (!audioUri) throw new Error("Missing recording uri")
            const transcription = await transcribeMyAiChatVoice({ fileName: getVoiceRecordingFilename(audioUri), mimeType: getVoiceRecordingMimeType(audioUri), uri: audioUri })
            transcribedText = transcription.text.trim()
            if (!transcribedText) throw new Error("Empty transcription")
        } catch {
            Alert.alert(t("chat.voiceTranscriptionFailedTitle"), t("chat.voiceTranscriptionFailedMessage"))
        } finally {
            setVoiceTranscribing(false)
            await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined)
        }
        if (!transcribedText) return
        try {
            shouldAutoScrollRef.current = true
            await chat.send({ text: transcribedText, attachments: [], replyToMessageId: replyTo?.id })
            setReplyTo(null)
        } catch (error) {
            Alert.alert(t("chat.communitySendFailedTitle"), error instanceof Error ? error.message : t("chat.communitySendFailedMessage"))
        }
    }, [audioRecorder, chat, replyTo?.id, t, voiceRecording, voiceTranscribing])

    const handleVoiceButtonPress = useCallback(async () => {
        if (voiceRecording) await stopVoiceRecording()
        else await startVoiceRecording()
    }, [startVoiceRecording, stopVoiceRecording, voiceRecording])

    const handleSend = useCallback(async () => {
        const text = draft.trim()
        if ((!text && !attachments.length) || chat.sending || chat.mutatingMessageId || voiceRecording || voiceTranscribing) return
        setEmojiPickerVisible(false)
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
    }, [attachments, chat, draft, editingMessage, replyTo?.id, t, voiceRecording, voiceTranscribing])

    const handleReaction = useCallback(async (messageId: number, emoji: string) => {
        try {
            await chat.react(messageId, emoji)
            setReactionPickerMessageId(null)
        } catch (error) {
            Alert.alert(t("chat.communityReactionFailedTitle"), error instanceof Error ? error.message : t("chat.communityReactionFailedMessage"))
        }
    }, [chat, t])

    const handleMessageLongPress = useCallback((message: CommunityMessage) => {
        if (message.is_deleted) return
        const actions: AlertButton[] = [
            { text: t("chat.communityReplyAction"), onPress: () => { setEditingMessage(null); setReplyTo(message) } },
        ]
        if (Array.isArray(message.reactions)) {
            actions.push({ text: t("chat.communityAddReaction"), onPress: () => setReactionPickerMessageId(message.id) })
        }
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
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_LIGHT} style={[chatStyles.backgroundImage, themeName === "dark" ? chatStyles.backgroundImageHidden : null]} />
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_DARK} style={[chatStyles.backgroundImage, themeName === "dark" ? null : chatStyles.backgroundImageHidden]} />
                <View pointerEvents="none" style={[chatStyles.backgroundScrim, isDark ? chatStyles.backgroundScrimDark : chatStyles.backgroundScrimLight]} />
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
                                {chat.messages.map((message) => <CommunityMessageBubble key={message.id} message={message} onLongPress={handleMessageLongPress} onReact={(emoji) => { void handleReaction(message.id, emoji) }} reacting={chat.reactingMessageId === message.id} reactionPickerOpen={reactionPickerMessageId === message.id} toggleReactionPicker={() => setReactionPickerMessageId((current) => current === message.id ? null : message.id)} />)}
                            </ScrollView>
                            {chat.error ? <View style={styles.inlineError}><Text style={styles.inlineErrorText}>{chat.error}</Text></View> : null}
                            <View onLayout={(event) => setComposerHeight(event.nativeEvent.layout.height)} style={[chatStyles.composerDock, { paddingBottom: composerBottomInset }]}>
                                {emojiPickerVisible ? <ChatEmojiPicker onSelect={(emoji) => setDraft((current) => `${current}${emoji}`)} /> : null}
                                {editingMessage ? <View style={styles.replyComposer}><View style={styles.replyComposerCopy}><Text style={styles.replyComposerTitle}>{t("chat.communityEditingMessage")}</Text><Text numberOfLines={1} style={styles.replyComposerText}>{editingMessage.text}</Text></View><Pressable onPress={() => { setEditingMessage(null); setDraft("") }}><Text style={styles.closeReply}>×</Text></Pressable></View> : null}
                                {replyTo ? <View style={styles.replyComposer}><View style={styles.replyComposerCopy}><Text style={styles.replyComposerTitle}>{t("chat.communityReplyingTo")} {replyTo.author.full_name}</Text><Text numberOfLines={1} style={styles.replyComposerText}>{replyTo.text || t("chat.attachmentFallbackMessage")}</Text></View><Pressable onPress={() => setReplyTo(null)}><Text style={styles.closeReply}>×</Text></Pressable></View> : null}
                                {voiceStatusVisible ? <View style={chatStyles.voiceStatusPill}>{voiceTranscribing ? <ActivityIndicator color={palette.primary} size="small" /> : <View style={chatStyles.voiceStatusDot} />}<Text style={chatStyles.voiceStatusText}>{voiceTranscribing ? t("chat.voiceTranscribing") : `${t("chat.voiceRecording")} ${formatVoiceDuration(audioRecorderState.durationMillis)}`}</Text></View> : null}
                                <QueuedAttachmentStrip attachments={attachments} onRemove={(index) => setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))} />
                                {chat.selectedTopic.is_closed ? <View style={styles.replyComposer}><Text style={styles.replyComposerText}>{t("chat.communityClosedMessage")}</Text></View> : <View style={chatStyles.composerRow}><Pressable accessibilityLabel={t("chat.communityAddAttachment")} disabled={Boolean(editingMessage) || voiceStatusVisible} onPress={openAttachmentSheet} style={[chatStyles.circleButton, editingMessage || voiceStatusVisible ? chatStyles.sendButtonDisabled : null]}><AttachmentSvgIcon color="#12161A" height={28} width={28} /></Pressable><View style={chatStyles.composerInputWrap}><TextInput editable={!voiceStatusVisible} multiline onChangeText={setDraft} onFocus={() => setEmojiPickerVisible(false)} placeholder={voiceRecording ? t("chat.voiceRecording") : editingMessage ? t("chat.communityEditingMessage") : t("chat.communityInputPlaceholder")} placeholderTextColor={isDark ? "#9BB0BF" : "#8B9092"} style={chatStyles.composerInput} textAlignVertical="top" value={draft} /><Pressable accessibilityLabel={t("chat.emojiPickerLabel")} onPress={() => { Keyboard.dismiss(); setEmojiPickerVisible((visible) => !visible) }} style={chatStyles.stickerButton}><Svg fill="none" height={24} viewBox="0 0 24 24" width={24}><Path d="M12 3.8a8.2 8.2 0 1 0 8.2 8.2v0A8.2 8.2 0 0 0 12 3.8ZM8.8 11.6h.1m6.2 0h.1M8.5 15.2c.8 1 2 1.6 3.5 1.6s2.7-.6 3.5-1.6" stroke="#778085" strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} /></Svg></Pressable></View><SendActionButton disabled={chat.sending || Boolean(chat.mutatingMessageId) || voiceTranscribing} isDark={isDark} isActive={hasComposerContent && !voiceRecording} onPress={() => { if (voiceRecording || !hasComposerContent) void handleVoiceButtonPress(); else void handleSend() }} recording={voiceRecording} sending={chat.sending || Boolean(chat.mutatingMessageId)} transcribing={voiceTranscribing} /></View>}
                            </View>
                            </View>
                        </KeyboardAvoidingView>
                        </View>
                    ) : null}
                </View>
                <AttachmentSheet activeMode={attachmentMode} bottomInset={bottom} onClose={closeAttachmentSheet} onOpenCamera={() => { void openCamera() }} onOpenNativeGallery={() => { void openGallery() }} onPickFiles={() => { void pickFiles() }} onSelectMode={setAttachmentMode} visible={attachmentSheetVisible} />
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

function CommunityMessageBubble({ message, onLongPress, onReact, reacting, reactionPickerOpen, toggleReactionPicker }: { message: CommunityMessage; onLongPress: (message: CommunityMessage) => void; onReact: (emoji: string) => void; reacting: boolean; reactionPickerOpen: boolean; toggleReactionPicker: () => void }) {
    const styles = useThemeStyles(createCommunityChatStyles)
    const { t } = useLanguage()
    const delivery = message.delivery_status === "queued" || message.delivery_status === "sending" ? t("chat.communityPending") : message.delivery_status === "failed" ? t("chat.communityFailed") : message.delivery_status === "delivery_unknown" ? t("chat.communityUnknown") : ""
    const meta = [formatTime(message.created_at), message.is_edited && !message.is_deleted ? t("chat.communityEdited") : "", delivery].filter(Boolean).join(" · ")
    const mine = message.author.is_current_user
    // Keep OTA clients compatible while the backend reaction field rolls out.
    const reactionsSupported = Array.isArray(message.reactions)
    const reactions = Array.isArray(message.reactions) ? message.reactions : []
    return (
        <View style={[styles.messageBlock, mine ? styles.messageBlockMine : null]}>
            <View style={[styles.messageRow, mine ? styles.messageRowMine : null]}>
                <CommunityAuthorAvatar name={message.author.full_name} uri={message.author.avatar_url} />
                <Pressable onLongPress={() => onLongPress(message)} style={[styles.messageBubble, mine ? styles.messageBubbleMine : null, message.is_deleted ? styles.messageBubbleDeleted : null]}>
                    <Text style={styles.authorName}>{message.author.full_name}</Text>
                    {message.is_deleted ? <Text style={styles.deletedMessageText}>{t("chat.communityDeletedMessage")}</Text> : <>{message.reply_to ? <View style={styles.replyPreview}><Text style={styles.replyAuthor}>{message.reply_to.author_name}</Text><Text numberOfLines={2} style={styles.replyText}>{message.reply_to.text}</Text></View> : null}{message.attachments.map((attachment) => attachment.kind === "image" && attachment.media_url ? <CommunityMessageImage key={attachment.id} fallbackUrl={message.telegram_url} uri={attachment.media_url} /> : <Pressable key={attachment.id} onPress={() => { const url = resolveApiMediaUri(attachment.media_url) ?? message.telegram_url; if (url) void Linking.openURL(url) }} style={styles.documentCard}><Text style={styles.documentIcon}>▧</Text><Text numberOfLines={2} style={styles.documentName}>{attachment.filename}</Text></Pressable>)}{message.text ? <Text style={styles.messageText}>{message.text}</Text> : null}{message.unsupported_type ? <View style={styles.unsupportedCard}><Text style={styles.unsupportedText}>{t("chat.communityUnsupported")}</Text>{message.telegram_url ? <Pressable onPress={() => { void Linking.openURL(message.telegram_url as string) }}><Text style={styles.telegramLink}>{t("chat.communityOpenTelegram")}</Text></Pressable> : null}</View> : null}</>}
                    <Text style={styles.messageMeta}>{meta}</Text>
                </Pressable>
            </View>
            {!message.is_deleted && reactionsSupported ? <View style={[styles.reactionRow, mine ? styles.reactionRowMine : null]}>{reactions.map((reaction) => <Pressable disabled={reacting} key={reaction.emoji} onPress={() => onReact(reaction.emoji)} style={[styles.reactionChip, reaction.reacted_by_me ? styles.reactionChipMine : null]}><Text style={styles.reactionEmoji}>{reaction.emoji}</Text><Text style={[styles.reactionCount, reaction.reacted_by_me ? styles.reactionCountMine : null]}>{reaction.count}</Text></Pressable>)}<Pressable accessibilityLabel={t("chat.communityAddReaction")} disabled={reacting} onPress={toggleReactionPicker} style={styles.addReactionButton}>{reacting ? <ActivityIndicator size="small" /> : <Text style={styles.addReactionText}>＋</Text>}</Pressable></View> : null}
            {reactionPickerOpen && reactionsSupported ? <View style={[styles.reactionPicker, mine ? styles.reactionPickerMine : null]}>{COMMUNITY_REACTION_EMOJIS.map((emoji) => <Pressable key={emoji} onPress={() => onReact(emoji)} style={({ pressed }) => [styles.reactionPickerButton, pressed ? styles.reactionPickerButtonPressed : null]}><Text style={styles.reactionPickerEmoji}>{emoji}</Text></Pressable>)}</View> : null}
        </View>
    )
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
