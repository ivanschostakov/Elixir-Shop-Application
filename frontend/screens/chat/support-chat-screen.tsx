import { AppFormLayout } from "@/components/platform/app-form-layout"
import { requestChatRecordingPermission } from "@/screens/chat/chat-recording-permission"
import { useCallback, useEffect, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Image,
    ImageBackground,
    Keyboard,
    Platform,
    RefreshControl,
    ScrollView,
    Text,
    View,
} from "react-native"
import { useCameraPermissions } from "expo-camera"
import {
    RecordingPresets,
    setAudioModeAsync,
    useAudioRecorder,
    useAudioRecorderState,
} from "expo-audio"
import * as ImagePicker from "expo-image-picker"
import { useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ChatKeyboardPane, ChatMessageScrollView, ChatComposerDock } from "@/components/platform/chat-layout"
import { AppEdgeMaterial as ChatEdgeBlur } from "@/components/platform/app-edge-material"
import { ROUTES } from "@/constants/routes"
import { useChatScroll } from "@/hooks/chat/use-chat-scroll"
import { useSupportChat } from "@/hooks/chat/use-support-chat"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { getTranslationLocale } from "@/i18n/translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { transcribeMyAiChatVoice } from "@/services/api/ai-chat"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import type { SupportConversationStatus } from "@/services/api/support.types"
import { API_BASE_URL } from "@/services/api/constants"
import { getAuthTokens } from "@/services/auth/session"
import {
    createAttachmentFromImagePickerAsset,
    formatVoiceDuration,
    getVoiceRecordingFilename,
    getVoiceRecordingMimeType,
} from "@/screens/chat/chat-attachments"
import { AttachmentSheet, QueuedAttachmentStrip } from "@/screens/chat/chat-screen.attachments"
import {
    CHAT_BACKGROUND_DARK,
    CHAT_BACKGROUND_LIGHT,
    CHAT_IDLE_AUDIO_MODE,
    CHAT_RECORDING_AUDIO_MODE,
} from "@/screens/chat/chat-screen.constants"
import { ChatComposer } from "@/screens/chat/chat-composer"
import { AppIconButton } from "@/components/platform/app-icon-button"
import { AppSurface } from "@/components/platform/app-surface"
import { AppMenu } from "@/components/platform/app-menu"
import type { ChatMode } from "@/screens/chat/chat-mode-switcher"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { createSupportChatStyles } from "@/screens/chat/support-chat-screen.styles"
import { QuietLoading } from "@/components/ui/quiet-loading"
import { spacing } from "@/theme/spacing"
import { createUuid } from "@/utils/uuid"

type SupportChatScreenProps = {
    embedded?: boolean
    headerInset?: number
    active: boolean
    communityUnreadCount: number
    mode: ChatMode
    onModeChange: (mode: ChatMode) => void
    onUnreadChange: (count: number) => void
    requestedConversationId: number | null
    supportUnreadCount: number
}

function messageTime(value: string) {
    return new Intl.DateTimeFormat(getTranslationLocale(), { hour: "2-digit", minute: "2-digit" }).format(new Date(value))
}

function historyDate(value: string | null) {
    if (!value) return ""
    return new Intl.DateTimeFormat(getTranslationLocale(), { day: "2-digit", month: "short" }).format(new Date(value))
}

function attachmentSource(path: string) {
    const token = getAuthTokens()?.accessToken
    return {
        uri: new URL(path, API_BASE_URL).toString(),
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    }
}


export function SupportChatScreen({
    embedded = false,
    headerInset = 0,
    active,
    onUnreadChange,
    requestedConversationId,
}: SupportChatScreenProps) {
    const styles = useThemeStyles(createSupportChatStyles)
    const chatStyles = useThemeStyles(createChatScreenStyles)
    const { isDark, palette, themeName } = useTheme()
    const { t } = useLanguage()
    const router = useRouter()
    const { top } = useSafeAreaInsets()
    const [cameraPermission, requestCameraPermission] = useCameraPermissions()
    const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY)
    const audioRecorderState = useAudioRecorderState(audioRecorder, 200)
    const scrollRef = useRef<ScrollView | null>(null)
    const chatScroll = useChatScroll(scrollRef, null)
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableChatAttachment[]>([])
    const [attachmentSheetVisible, setAttachmentSheetVisible] = useState(false)
    const [composerHeight, setComposerHeight] = useState(74)
    const voiceStarting = useRef(false)
    const [voiceRecording, setVoiceRecording] = useState(false)
    const [voiceTranscribing, setVoiceTranscribing] = useState(false)
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
    const contentTop = embedded ? headerInset : headerTop + 52
    const iosChat = Platform.OS === "ios"
    const isHistorical = Boolean(conversation && conversation.id !== inbox?.active?.id)
    const contentBottom = isHistorical ? 0 : composerHeight
    const hasComposerContent = Boolean(draft.trim()) || attachments.length > 0
    const voiceStatusVisible = voiceRecording || voiceTranscribing

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



    useEffect(() => () => {
        try {
            void audioRecorder.stop().catch(() => undefined)
        } catch {
            // The native recorder may already be released during unmount.
        }
    }, [audioRecorder])

    const appendAttachments = useCallback((items: UploadableChatAttachment[]) => {
        setAttachments((current) => [...current, ...items].slice(0, 4))
    }, [])

    const closeAttachmentSheet = useCallback(() => {
        setAttachmentSheetVisible(false)
    }, [])

    const openAttachmentSheet = useCallback(() => {
        if (!inbox?.active) {
            Alert.alert(t("chat.supportNewTitle"), t("chat.supportAttachmentAfterStart"))
            return
        }
        Keyboard.dismiss()
        setAttachmentSheetVisible(true)
    }, [inbox?.active, t])

    const openGallery = useCallback(async () => {
        try {
            const result = await ImagePicker.launchImageLibraryAsync({
                allowsMultipleSelection: true,
                mediaTypes: ["images"],
                quality: 0.92,
                selectionLimit: 4,
            })
            if (!result.canceled) {
                appendAttachments(result.assets.map(createAttachmentFromImagePickerAsset))
            }
            closeAttachmentSheet()
        } catch {
            Alert.alert(t("chat.attachmentsLoadFailedTitle"), t("chat.attachmentsLoadFailedMessage"))
        }
    }, [appendAttachments, closeAttachmentSheet, t])

    const openCamera = useCallback(async () => {
        try {
            let granted = cameraPermission?.granted === true
            if (!granted) {
                granted = (await requestCameraPermission()).granted
            }
            if (!granted) {
                Alert.alert(t("chat.attachmentsPhotoPermissionTitle"), t("chat.attachmentsPhotoPermissionMessage"))
                return
            }
            const result = await ImagePicker.launchCameraAsync({
                mediaTypes: ["images"],
                quality: 0.92,
            })
            if (!result.canceled) {
                appendAttachments(result.assets.map(createAttachmentFromImagePickerAsset))
            }
            closeAttachmentSheet()
        } catch {
            Alert.alert(t("chat.attachmentsLoadFailedTitle"), t("chat.attachmentsLoadFailedMessage"))
        }
    }, [appendAttachments, cameraPermission?.granted, closeAttachmentSheet, requestCameraPermission, t])

    const submitSupportContent = useCallback(async (
        text: string,
        pendingAttachments: UploadableChatAttachment[],
    ) => {
        if (!inbox?.active) {
            await createConversation({
                client_message_id: createUuid(),
                subject: text.slice(0, 120),
                message: text,
            })
            return
        }
        await sendMessage({
            clientMessageId: createUuid(),
            message: text,
            attachments: pendingAttachments,
        })
    }, [createConversation, inbox?.active, sendMessage])

    const handleSend = useCallback(async () => {
        if (!hasComposerContent || sending || isHistorical || voiceRecording || voiceTranscribing) return
        const text = draft.trim()
        if (!inbox?.active && !text) {
            Alert.alert(t("chat.supportNewTitle"), t("chat.supportFirstMessageRequired"))
            return
        }
        const pendingAttachments = attachments
        setDraft("")
        setAttachments([])
        try {
            await submitSupportContent(text, pendingAttachments)
        } catch (sendError) {
            setDraft(text)
            setAttachments(pendingAttachments)
            Alert.alert(
                t("chat.supportSendFailedTitle"),
                sendError instanceof Error ? sendError.message : t("chat.supportSendFailedMessage"),
            )
        }
    }, [
        attachments,
        draft,
        hasComposerContent,
        inbox?.active,
        isHistorical,
        sending,
        submitSupportContent,
        t,
        voiceRecording,
        voiceTranscribing,
    ])

    const startVoiceRecording = useCallback(async () => {
        if (voiceStarting.current || sending || voiceTranscribing) return
        voiceStarting.current = true
        Keyboard.dismiss()
        try {
            if (!await requestChatRecordingPermission(t)) return
            await setAudioModeAsync(CHAT_RECORDING_AUDIO_MODE)
            await audioRecorder.prepareToRecordAsync()
            audioRecorder.record()
            setVoiceRecording(true)
        } catch {
            setVoiceRecording(false)
            Alert.alert(t("chat.voiceTranscriptionFailedTitle"), t("chat.voiceTranscriptionFailedMessage"))
            await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined)
        } finally {
            voiceStarting.current = false
        }
    }, [audioRecorder, sending, t, voiceTranscribing])

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
            const transcription = await transcribeMyAiChatVoice({
                fileName: getVoiceRecordingFilename(audioUri),
                mimeType: getVoiceRecordingMimeType(audioUri),
                uri: audioUri,
            })
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
            await submitSupportContent(transcribedText, [])
        } catch (sendError) {
            Alert.alert(
                t("chat.supportSendFailedTitle"),
                sendError instanceof Error ? sendError.message : t("chat.supportSendFailedMessage"),
            )
        }
    }, [audioRecorder, submitSupportContent, t, voiceRecording, voiceTranscribing])

    const handleVoiceButtonPress = useCallback(async () => {
        if (voiceRecording) {
            await stopVoiceRecording()
            return
        }
        await startVoiceRecording()
    }, [startVoiceRecording, stopVoiceRecording, voiceRecording])

    const statusLabels: Record<SupportConversationStatus, string> = {
        new: t("chat.supportStatusNew"),
        open: t("chat.supportStatusOpen"),
        waiting_customer: t("chat.supportStatusWaitingCustomer"),
        waiting_team: t("chat.supportStatusWaitingTeam"),
        resolved: t("chat.supportStatusResolved"),
        spam: t("chat.supportStatusSpam"),
    }

    const historyItems = [...(inbox?.active ? [inbox.active] : []), ...(inbox?.previous ?? [])]

    if (!active && !embedded) {
        return null
    }

    return (
        <ChatKeyboardPane style={styles.overlay}>
            <View style={[styles.screen, embedded ? { backgroundColor: "transparent" } : null]}>
                {!embedded ? <>
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_LIGHT} style={[chatStyles.backgroundImage, themeName === "dark" ? chatStyles.backgroundImageHidden : null]} />
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_DARK} style={[chatStyles.backgroundImage, themeName === "dark" ? null : chatStyles.backgroundImageHidden]} />
                <View pointerEvents="none" style={[chatStyles.backgroundScrim, isDark ? chatStyles.backgroundScrimDark : chatStyles.backgroundScrimLight]} />
                </> : null}
                {!embedded ? <View style={[styles.header, { top: headerTop }]}>
                    <View style={styles.backControl}>
                        <AppIconButton action="back" dark={isDark} label={t("nav.back")} onPress={() => router.canGoBack() ? router.back() : router.replace(ROUTES.discover)} backgroundColor={palette.surfaceOverlay} color={palette.text} style={styles.nativeBackButton} />
                    </View>
                    <View style={styles.titlePill}>
                        <AppSurface dark={isDark} fallbackColor={palette.surfaceOverlay} pointerEvents="none" style={styles.titleMaterial} />
                        <Text accessibilityRole="header" numberOfLines={1} style={styles.headerTitle}>{t("chat.supportTitle")}</Text>
                    </View>
                </View> : null}

                <AppFormLayout
                    enabled={!embedded && !iosChat}

                    contentContainerStyle={chatStyles.keyboardContent}

                    style={styles.keyboard}
                >
                    <View style={chatStyles.keyboardContent}>
                        <ChatMessageScrollView
                            contentContainerStyle={[
                                styles.messagesContent,
                                {
                                    paddingTop: contentTop + spacing.sm,
                                    paddingBottom: iosChat ? spacing.sm : contentBottom + spacing.md,
                                },
                            ]}
                            keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
                            keyboardShouldPersistTaps="handled"
                            automaticallyAdjustsScrollIndicatorInsets={iosChat ? false : undefined}
                            scrollIndicatorInsets={iosChat ? { top: contentTop, bottom: contentBottom } : undefined}
                            ref={scrollRef}
                            onScroll={chatScroll.onScroll}
                            onScrollBeginDrag={chatScroll.onScrollBeginDrag}
                            onContentSizeChange={chatScroll.onContentSizeChange}
                            onLayout={chatScroll.onLayout}
                            scrollEventThrottle={16}
                            refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { void refresh() }} tintColor={palette.primary} />}
                            style={styles.messages}
                        >
                        {inbox?.previous.length ? <AppMenu dark={isDark} label={t("chat.supportHistory")} color={palette.text} fallbackColor={palette.surfaceOverlay}
                            options={historyItems.map(item => ({ id: String(item.id), label: item.id === inbox.active?.id ? t("chat.supportCurrent") : item.subject || `#${item.id}`, detail: `${statusLabels[item.status]} · ${historyDate(item.last_message_at)}` }))}
                            value={conversation ? String(conversation.id) : undefined}
                            onChange={id => { if (Number(id) === inbox.active?.id) closePrevious(); else void openPrevious(Number(id)) }}
                            style={{ minHeight: 44, marginBottom: spacing.md }} /> : null}

                        <QuietLoading loading={!inbox && !error} />
                        {inbox && !loading && !conversation ? (
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
                        </ChatMessageScrollView>

                        {error ? (
                            <View style={[chatStyles.inlineErrorWrap, { bottom: (isHistorical ? 0 : composerHeight) + spacing.sm }]}>
                                <Text style={chatStyles.inlineError}>{error}</Text>
                            </View>
                        ) : null}
                        {!isHistorical ? (
                            <ChatComposerDock
                                onLayout={(event) => setComposerHeight(event.nativeEvent.layout.height)}
                                pointerEvents={iosChat ? "box-none" : "auto"}
                                style={[chatStyles.composerDock, iosChat && chatStyles.composerDockOverlay]}
                            >
                                {voiceStatusVisible ? (
                                    <View style={chatStyles.voiceStatusPill}>
                                        {voiceTranscribing
                                            ? <ActivityIndicator color={palette.primary} size="small" />
                                            : <View style={chatStyles.voiceStatusDot} />}
                                        <Text style={chatStyles.voiceStatusText}>
                                            {voiceTranscribing
                                                ? t("chat.voiceTranscribing")
                                                : `${t("chat.voiceRecording")} ${formatVoiceDuration(audioRecorderState.durationMillis)}`}
                                        </Text>
                                    </View>
                                ) : null}
                                <QueuedAttachmentStrip
                                    attachments={attachments}
                                    onRemove={(index) => {
                                        setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))
                                    }}
                                />
                                <ChatComposer
                                    value={draft}
                                    onChangeText={setDraft}
                                    placeholder={voiceRecording ? t("chat.voiceRecording") : t("chat.supportInputPlaceholder")}
                                    onAttachment={openAttachmentSheet}
                                    onAction={() => { if (voiceRecording || !hasComposerContent) void handleVoiceButtonPress(); else void handleSend() }}
                                    hasContent={hasComposerContent}
                                    disabled={sending || voiceTranscribing}
                                    attachmentDisabled={voiceStatusVisible}
                                    recording={voiceRecording}
                                    busy={sending || voiceTranscribing}
                                    transcribing={voiceTranscribing}
                                />
                            </ChatComposerDock>
                        ) : null}
                    </View>
                </AppFormLayout>
                {!embedded && iosChat ? <ChatEdgeBlur dark={isDark} topEdge style={[chatStyles.dialogTopBlur, { height: contentTop + 10 }]} /> : null}
                <AttachmentSheet
                    allowFiles={false}
                    onClose={closeAttachmentSheet}
                    onOpenCamera={() => { void openCamera() }}
                    onOpenNativeGallery={() => { void openGallery() }}
                    onPickFiles={() => undefined}
                    visible={attachmentSheetVisible}
                />
            </View>
        </ChatKeyboardPane>
    )
}
