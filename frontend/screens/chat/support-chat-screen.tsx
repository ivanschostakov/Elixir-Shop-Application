import { useCallback, useEffect, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Image,
    ImageBackground,
    Keyboard,
    KeyboardAvoidingView,
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
import * as ImagePicker from "expo-image-picker"
import { useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import AttachmentSvgIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import { ROUTES } from "@/constants/routes"
import { useSupportChat } from "@/hooks/chat/use-support-chat"
import { useThemeStyles } from "@/hooks/use-theme-styles"
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
    type AttachmentMode,
    CHAT_BACKGROUND_DARK,
    CHAT_BACKGROUND_LIGHT,
    CHAT_IDLE_AUDIO_MODE,
    CHAT_RECORDING_AUDIO_MODE,
    IOS_MINIMUM_VOICE_RECORDING_BUILD,
} from "@/screens/chat/chat-screen.constants"
import { SendActionButton } from "@/screens/chat/chat-screen.core-components"
import { ChatModeSwitcher, type ChatMode } from "@/screens/chat/chat-mode-switcher"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { createSupportChatStyles } from "@/screens/chat/support-chat-screen.styles"
import { spacing } from "@/theme/spacing"
import { createUuid } from "@/utils/uuid"

type SupportChatScreenProps = {
    active: boolean
    communityUnreadCount: number
    mode: ChatMode
    onModeChange: (mode: ChatMode) => void
    onUnreadChange: (count: number) => void
    requestedConversationId: number | null
    supportUnreadCount: number
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

function nativeBuildNumber() {
    const parsedBuild = Number(Application.nativeBuildVersion)
    return Number.isFinite(parsedBuild) ? parsedBuild : 0
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
    const [cameraPermission, requestCameraPermission] = useCameraPermissions()
    const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY)
    const audioRecorderState = useAudioRecorderState(audioRecorder, 200)
    const scrollRef = useRef<ScrollView | null>(null)
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableChatAttachment[]>([])
    const [attachmentMode, setAttachmentMode] = useState<AttachmentMode>("photo")
    const [attachmentSheetVisible, setAttachmentSheetVisible] = useState(false)
    const [composerHeight, setComposerHeight] = useState(74)
    const [keyboardVisible, setKeyboardVisible] = useState(false)
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
    const composerBottomInset = keyboardVisible ? spacing.sm : Math.max(bottom, spacing.sm)
    const isHistorical = Boolean(conversation && conversation.id !== inbox?.active?.id)
    const hasComposerContent = Boolean(draft.trim()) || attachments.length > 0
    const voiceStatusVisible = voiceRecording || voiceTranscribing
    const voiceRecordingSupported =
        __DEV__ || Platform.OS !== "ios" || nativeBuildNumber() >= IOS_MINIMUM_VOICE_RECORDING_BUILD

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

    useEffect(() => {
        const showEvent = Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow"
        const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide"
        const showSubscription = Keyboard.addListener(showEvent, (event) => {
            Keyboard.scheduleLayoutAnimation(event)
            setKeyboardVisible(true)
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
        setAttachmentMode("photo")
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
        if (sending || voiceTranscribing) return
        if (!voiceRecordingSupported) {
            Alert.alert(t("chat.voiceUpdateRequiredTitle"), t("chat.voiceUpdateRequiredMessage"))
            return
        }
        Keyboard.dismiss()
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
    }, [audioRecorder, sending, t, voiceRecordingSupported, voiceTranscribing])

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

    if (!active) {
        return null
    }

    return (
        <View style={styles.overlay}>
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

                <KeyboardAvoidingView
                    behavior={Platform.OS === "ios" ? "position" : "height"}
                    contentContainerStyle={chatStyles.keyboardContent}
                    keyboardVerticalOffset={0}
                    style={styles.keyboard}
                >
                    <View style={chatStyles.keyboardContent}>
                        <ScrollView
                            contentContainerStyle={[
                                styles.messagesContent,
                                {
                                    paddingTop: headerTop + 60,
                                    paddingBottom: isHistorical ? spacing.md : composerHeight + spacing.md,
                                },
                            ]}
                            keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
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

                        {error ? (
                            <View style={[chatStyles.inlineErrorWrap, { bottom: (isHistorical ? 0 : composerHeight) + spacing.sm }]}>
                                <Text style={chatStyles.inlineError}>{error}</Text>
                            </View>
                        ) : null}
                        {!isHistorical ? (
                            <View
                                onLayout={(event) => setComposerHeight(event.nativeEvent.layout.height)}
                                style={[chatStyles.composerDock, { paddingBottom: composerBottomInset }]}
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
                                <View style={chatStyles.composerRow}>
                                    <Pressable
                                        accessibilityLabel={t("chat.communityAddAttachment")}
                                        disabled={voiceStatusVisible}
                                        onPress={openAttachmentSheet}
                                        style={[
                                            chatStyles.circleButton,
                                            voiceStatusVisible ? chatStyles.sendButtonDisabled : null,
                                        ]}
                                    >
                                        <AttachmentSvgIcon color="#12161A" height={28} width={28} />
                                    </Pressable>
                                    <View style={chatStyles.composerInputWrap}>
                                        <TextInput
                                            editable={!voiceStatusVisible}
                                            multiline
                                            onChangeText={setDraft}
                                            placeholder={voiceRecording ? t("chat.voiceRecording") : t("chat.supportInputPlaceholder")}
                                            placeholderTextColor={isDark ? "#9BB0BF" : "#8B9092"}
                                            style={chatStyles.composerInput}
                                            textAlignVertical="top"
                                            value={draft}
                                        />
                                    </View>
                                    <SendActionButton
                                        disabled={sending || voiceTranscribing}
                                        isDark={isDark}
                                        isActive={hasComposerContent && !voiceRecording}
                                        onPress={() => {
                                            if (voiceRecording || !hasComposerContent) {
                                                void handleVoiceButtonPress()
                                                return
                                            }
                                            void handleSend()
                                        }}
                                        recording={voiceRecording}
                                        sending={sending}
                                        transcribing={voiceTranscribing}
                                    />
                                </View>
                            </View>
                        ) : null}
                    </View>
                </KeyboardAvoidingView>
                <AttachmentSheet
                    activeMode={attachmentMode}
                    allowFiles={false}
                    bottomInset={bottom}
                    onClose={closeAttachmentSheet}
                    onOpenCamera={() => { void openCamera() }}
                    onOpenNativeGallery={() => { void openGallery() }}
                    onPickFiles={() => undefined}
                    onSelectMode={setAttachmentMode}
                    visible={attachmentSheetVisible}
                />
            </View>
        </View>
    )
}
