import { requestChatRecordingPermission } from "@/screens/chat/chat-recording-permission"
import { useCallback, useEffect, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Keyboard,
    Linking,
    Platform,
    Pressable,
    RefreshControl,
    ScrollView,
    Text,
    TextInput,
    useWindowDimensions,
    View,
} from "react-native"
import * as Clipboard from "expo-clipboard"
import { useCameraPermissions } from "expo-camera"
import {
    RecordingPresets,
    setAudioModeAsync,
    useAudioRecorder,
    useAudioRecorderState,
} from "expo-audio"
import * as DocumentPicker from "expo-document-picker"
import * as ImagePicker from "expo-image-picker"
import * as SecureStore from "expo-secure-store"
import { useLocalSearchParams, useRouter } from "expo-router"
import Svg, { Path } from "react-native-svg"

import { EmptyState } from "@/components/content/empty-state"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { ROUTES, getProductRoute } from "@/constants/routes"
import { useBasket } from "@/hooks/basket/use-basket"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { useAiChatEntryConsent } from "@/hooks/chat/use-ai-chat-entry-consent"
import { useAiChat, type ChatDisplayMessage } from "@/hooks/chat/use-ai-chat"
import { useLanguage } from "@/providers/language-provider"
import { useAuth } from "@/providers/auth-provider"
import { useTheme } from "@/providers/theme-provider"
import { transcribeMyAiChatVoice } from "@/services/api/ai-chat"
import { AiConsentDeclinedError } from "@/services/api/ai-data-consent"
import { CompanionCards, useCompanion } from "@/screens/chat/companion"
import type { MentorTab } from "@/screens/chat/mentor-navigation"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { MentorSetup } from "@/screens/chat/mentor-setup"
import { MENTOR_SHORTCUT_HEIGHT, MentorShortcut } from "@/screens/chat/mentor-shortcut"
import { ChatBackdrop } from "@/screens/chat/chat-backdrop"
import { ChatEdgeBlur } from "@/screens/chat/chat-edge-blur"
import { ContentReveal, QuietLoading } from "@/components/ui/quiet-loading"
import { ChatKeyboardLayout } from "@/screens/chat/chat-keyboard-layout"
import { ChatKeyboardPane, ChatMessageScrollView, ChatComposerDock, ChatKeyboardFloating } from "@/screens/chat/chat-keyboard-motion"
import { ChatTopicTitle, type ChatTopicNavigation } from "@/screens/chat/chat-topic-title"
import { ChatComposer } from "@/screens/chat/chat-composer"
import { NativeChatAction, NativeComposerMaterial } from "@/screens/chat/native-chat-controls"
import { useChatScroll } from "@/hooks/chat/use-chat-scroll"
import { trackCustomerEvent } from "@/services/customer-intelligence"
import type {
    AIInteractiveAction,
    AIInteractiveVariant,
    UploadableChatAttachment,
} from "@/services/api/ai-chat.types"
import type { BasketItemRead } from "@/types/basket"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { spacing } from "@/theme/spacing"
import { createChatScreenStyles } from "./chat-screen.styles"
import { ChatModeSwitcher, type ChatMode } from "@/screens/chat/chat-mode-switcher"
import { isCommunityChatAvailable, isMentorAvailable, resolveChatMode } from "@/screens/chat/chat-mode-policy"
import { ChatModePane, ChatModeTransition, useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { CommunityChatScreen } from "@/screens/chat/community-chat-screen"
import { SupportChatScreen } from "@/screens/chat/support-chat-screen"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import {
    AttachmentSheet,
    MessageAttachmentList,
    QueuedAttachmentStrip,
} from "@/screens/chat/chat-screen.attachments"
import {
    AIInteractiveContent,
    AiTypingBubble,
    AnimatedMessageBlock,
    MessageMarkdown,
} from "@/screens/chat/chat-screen.core-components"
import {
    createAttachmentFromImagePickerAsset,
    formatVoiceDuration,
    getVoiceRecordingFilename,
    getVoiceRecordingMimeType,
    isImageAttachment,
} from "@/screens/chat/chat-attachments"
import {
    type AttachmentMode,
    CHAT_IDLE_AUDIO_MODE,
    CHAT_RECORDING_AUDIO_MODE,
    INTERNAL_PRODUCT_LINK_PATTERN,
    MESSAGE_IMAGE_MAX_WIDTH,
    SAFE_LINK_PROTOCOL_PATTERN,
} from "@/screens/chat/chat-screen.constants"


const CHAT_MODE_STORAGE_KEY = "elixirpeptide-chat-mode"

async function readStoredChatMode(): Promise<ChatMode | null> {
    try {
        const value = Platform.OS === "web"
            ? (typeof window !== "undefined" ? window.localStorage?.getItem(CHAT_MODE_STORAGE_KEY) : null)
            : await SecureStore.getItemAsync(CHAT_MODE_STORAGE_KEY)
        return resolveChatMode(value, Platform.OS)
    } catch {
        return null
    }
}

async function persistChatMode(mode: ChatMode) {
    try {
        if (Platform.OS === "web") {
            if (typeof window !== "undefined") window.localStorage?.setItem(CHAT_MODE_STORAGE_KEY, mode)
            return
        }
        await SecureStore.setItemAsync(CHAT_MODE_STORAGE_KEY, mode)
    } catch {
        // The visible mode can still change when local persistence is unavailable.
    }
}

export default function ChatScreen() {
    const { user } = useAuth()
    return <ChatScreenContent key={user?.id ?? "guest"} />
}

type EmbeddedMentor = { controller: ReturnType<typeof useCompanion>; active: boolean; onBack: () => void }
export function MentorChatScreen(props: EmbeddedMentor) { return <ChatScreenContent mentor={props} /> }

function ChatScreenContent({ mentor }: { mentor?: EmbeddedMentor } = {}) {
    const mentorChat = !!mentor
    const screenActive = mentor?.active ?? true
    const screenActiveRef = useRef(screenActive); screenActiveRef.current = screenActive
    const chatScreenStyles = useThemeStyles(createChatScreenStyles)
    const router = useRouter()
    const localParams = useLocalSearchParams<{ mode?: string | string[]; topicId?: string | string[]; conversationId?: string | string[]; companion?: string }>()
    const routeParams = mentorChat ? {} : localParams
    const { t } = useLanguage()
    const { isDark, palette } = useTheme()
    const { width: screenWidth } = useWindowDimensions()
    const { top: topInset, bottom: bottomInset } = useSafeAreaInsets()
    const [cameraPermission, requestCameraPermission] = useCameraPermissions()
    const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY)
    const audioRecorderState = useAudioRecorderState(audioRecorder, 200)
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableChatAttachment[]>([])
    const [activeActionId, setActiveActionId] = useState<string | null>(null)
    const [activeBasketVariantId, setActiveBasketVariantId] = useState<number | null>(null)
    const [attachmentMode, setAttachmentMode] = useState<AttachmentMode>("photo")
    const [attachmentSheetVisible, setAttachmentSheetVisible] = useState(false)
    const voiceStarting = useRef(false)
    const [voiceRecording, setVoiceRecording] = useState(false)
    const [voiceTranscribing, setVoiceTranscribing] = useState(false)
    const [chatMode, setChatMode] = useState<ChatMode>("ai")
    const [modeReady, setModeReady] = useState(mentorChat)
    const [topicNavigation, setTopicNavigation] = useState<ChatTopicNavigation | null>(null)
    const [communityUnread, setCommunityUnread] = useState(0)
    const [supportUnread, setSupportUnread] = useState(0)
    const requestedMode = Array.isArray(routeParams.mode) ? routeParams.mode[0] : routeParams.mode
    const requestedTopicValue = Array.isArray(routeParams.topicId) ? routeParams.topicId[0] : routeParams.topicId
    const requestedConversationValue = Array.isArray(routeParams.conversationId) ? routeParams.conversationId[0] : routeParams.conversationId
    const parsedRequestedTopicId = Number(requestedTopicValue)
    const requestedTopicId = Number.isInteger(parsedRequestedTopicId) && parsedRequestedTopicId > 0
        ? parsedRequestedTopicId
        : null
    const parsedRequestedConversationId = Number(requestedConversationValue)
    const requestedConversationId = Number.isInteger(parsedRequestedConversationId) && parsedRequestedConversationId > 0
        ? parsedRequestedConversationId
        : null
    const iosChat = Platform.OS === "ios"
    const nativeIosChat = iosChat && NativeChatAction !== null && NativeComposerMaterial !== null
    const simpleIosChat = iosChat && !nativeIosChat
    const [composerDockHeight, setComposerDockHeight] = useState(0)
    const [followingLatest, setFollowingLatest] = useState(true)
    const communityAvailable = !mentorChat && isCommunityChatAvailable(Platform.OS)
    const mentorAvailable = !mentorChat && isMentorAvailable(Platform.OS)
    const communityRoute = requestedMode === "community" || requestedTopicId !== null
    const communityRequestedByRoute = communityAvailable && communityRoute
    const blockedCommunityRoute = !communityAvailable && communityRoute
    const supportRequestedByRoute = requestedMode === "support" || requestedConversationId !== null
    const chatModeRequestedByRoute = communityRoute || supportRequestedByRoute || requestedMode === "ai"
    const aiAllowed = useAiChatEntryConsent(modeReady && chatMode === "ai" && screenActive)
    const ownCompanion = useCompanion(aiAllowed && mentorAvailable)
    const companion = mentor?.controller ?? ownCompanion
    const [mentorOpen, setMentorOpen] = useState(false)
    const mentorExitToShop = useRef(false)
    const [mentorVisited, setMentorVisited] = useState(false)
    const [mentorInitialTab, setMentorInitialTab] = useState<MentorTab>("nutrition")
    const resolveMentorChat = async () => mentorChat ? companion.resolveEnabled() : false
    const { aiTyping, chat, error, loading, messages, performAction, refresh, refreshing, sending, sendMessage } = useAiChat(resolveMentorChat, companion.resolveProtocol, aiAllowed, mentorChat ? "mentor" : "ordinary")
    const latestMentorMessage = mentorChat ? chat?.chat?.messages.at(-1) : undefined
    const mentorReplyId = latestMentorMessage?.sender === "ai" ? latestMentorMessage.id : undefined
    const refreshCompanion = companion.refresh
    useEffect(() => {
        if (mentorReplyId !== undefined) void refreshCompanion()
    }, [mentorReplyId, refreshCompanion])
    const initialMessageIds = useRef<Set<number> | null>(null)
    if (chat && !initialMessageIds.current) initialMessageIds.current = new Set((chat.chat?.messages ?? []).map(message => message.id))
    const scrollRef = useRef<ScrollView | null>(null)
    const mentorInputRef = useRef<TextInput | null>(null)
    const overlaysChatChrome = Platform.OS === "ios"
    const topBarOffset = topInset + 8
    const headerHeight = topBarOffset + 52
    const scrollTopInset = overlaysChatChrome ? headerHeight : 0
    const scrollBottomInset = overlaysChatChrome ? composerDockHeight : 0
    const aiContentReady = chat !== null || error !== null
    const chatScroll = useChatScroll(scrollRef, null, iosChat ? setFollowingLatest : undefined)
    const { followLatest } = chatScroll
    const settleFollowingConversation = chatScroll.onContentSizeChange
    useEffect(() => {
        // A retained, prewarmed chat may measure before its native composer inset.
        // Settle again on entry, respecting readers who scrolled up in the history.
        if (mentorChat && screenActive && aiContentReady && composerDockHeight > 0) settleFollowingConversation()
    }, [mentorChat, screenActive, aiContentReady, composerDockHeight, settleFollowingConversation])
    const showConversation = useCallback(() => { followLatest() }, [followLatest])
    const openMentor = useCallback(() => { mentorExitToShop.current = false; Keyboard.dismiss(); setMentorInitialTab("nutrition"); setMentorVisited(true); setMentorOpen(true) }, [])
    const cameraPermissionPromptedRef = useRef(false)
    const voiceStatusVisible = voiceRecording || voiceTranscribing
    const messageMediaWidth = Math.min(screenWidth * 0.68, MESSAGE_IMAGE_MAX_WIDTH)
    const messageTextWidth = Math.max(180, Math.min(screenWidth * 0.74, 330))
    const { basket } = useBasket()
    const {
        addItem: addBasketItem,
        removeItem: removeBasketItem,
        updateItemQuantity: updateBasketItemQuantity,
    } = useBasketMutations()

    useEffect(() => {
        if (mentorChat) return
        let mounted = true
        void readStoredChatMode().then((storedMode) => {
            if (!mounted) return
            if (storedMode && !chatModeRequestedByRoute) setChatMode(storedMode)
            setModeReady(true)
        })
        return () => { mounted = false }
    }, [chatModeRequestedByRoute, mentorChat])

    useEffect(() => {
        if (routeParams.companion !== "1") return
        Keyboard.dismiss(); setMentorInitialTab("chat"); setMentorVisited(true); setMentorOpen(true)
    }, [routeParams.companion])

    useEffect(() => {
        if (!communityRequestedByRoute) return
        setChatMode("community")
        void persistChatMode("community")
    }, [communityRequestedByRoute, requestedTopicId])

    useEffect(() => {
        if (!supportRequestedByRoute) return
        setChatMode("support")
        void persistChatMode("support")
    }, [requestedConversationId, supportRequestedByRoute])

    useEffect(() => {
        if ((requestedMode === "ai" || blockedCommunityRoute) && !communityRequestedByRoute && !supportRequestedByRoute) {
            setChatMode("ai")
            if (blockedCommunityRoute) void persistChatMode("ai")
        }
    }, [requestedMode, communityRequestedByRoute, supportRequestedByRoute, blockedCommunityRoute])

    const handleChatModeChange = useCallback((nextMode: ChatMode) => {
        Keyboard.dismiss()
        const availableMode = resolveChatMode(nextMode, Platform.OS) ?? "ai"
        setChatMode(availableMode)
        void persistChatMode(availableMode)
    }, [])

    const handleCommunityUnreadChange = useCallback((count: number) => {
        setCommunityUnread(count)
    }, [])

    const handleCommunityEnabledChange = useCallback((enabled: boolean) => {
        if (!enabled) {
            setChatMode((current) => current === "community" ? "ai" : current)
        }
    }, [])

    useApplyScreenTemplate("feed", {
        header: "none",
        footer: "none",
        mode: "fullscreen",
    }, !mentorChat)

    useEffect(() => {
        if (
            !attachmentSheetVisible ||
            attachmentMode !== "photo" ||
            cameraPermissionPromptedRef.current ||
            cameraPermission === null ||
            cameraPermission.granted ||
            !cameraPermission.canAskAgain
        ) {
            return
        }

        cameraPermissionPromptedRef.current = true
        void requestCameraPermission()
    }, [
        attachmentMode,
        attachmentSheetVisible,
        cameraPermission,
        requestCameraPermission,
    ])



    useEffect(() => () => {
        try {
            void audioRecorder.stop().catch(() => undefined)
        } catch {
            // Ignore cleanup failures when the recorder native object is already released.
        }
    }, [audioRecorder])

    useEffect(() => {
        if (screenActive) return
        setAttachmentSheetVisible(false)
        if (voiceRecording) {
            void audioRecorder.stop().catch(() => undefined).finally(() => setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined))
            setVoiceRecording(false)
        }
    }, [screenActive, audioRecorder, voiceRecording])

    const appendAttachments = useCallback((nextAttachments: UploadableChatAttachment[]) => {
        if (!nextAttachments.length) {
            return
        }

        setAttachments((currentAttachments) => [...currentAttachments, ...nextAttachments])
    }, [])

    const handleOpenAttachmentSheet = useCallback(() => {
        Keyboard.dismiss()
        setAttachmentMode("photo")
        setAttachmentSheetVisible(true)
    }, [])

    const handleCloseAttachmentSheet = useCallback(() => {
        setAttachmentSheetVisible(false)
    }, [])

    const handleSelectAttachmentMode = useCallback((mode: AttachmentMode) => {
        setAttachmentMode(mode)
    }, [])

    const handleOpenNativeGallery = useCallback(async () => {
        try {
            const result = await ImagePicker.launchImageLibraryAsync({
                allowsMultipleSelection: true,
                mediaTypes: ["images"],
                quality: 0.92,
            })

            if (result.canceled) {
                return
            }

            appendAttachments(result.assets.map(createAttachmentFromImagePickerAsset))
            handleCloseAttachmentSheet()
        } catch {
            Alert.alert(t("chat.attachmentsLoadFailedTitle"), t("chat.attachmentsLoadFailedMessage"))
        }
    }, [appendAttachments, handleCloseAttachmentSheet, t])

    const handleOpenCamera = useCallback(async () => {
        try {
            let cameraAccessGranted = cameraPermission?.granted === true

            if (!cameraAccessGranted) {
                const permission = await requestCameraPermission()
                cameraAccessGranted = permission.granted
            }

            if (!cameraAccessGranted) {
                Alert.alert(t("chat.attachmentsPhotoPermissionTitle"), t("chat.attachmentsPhotoPermissionMessage"))
                return
            }

            const result = await ImagePicker.launchCameraAsync({
                mediaTypes: ["images"],
                quality: 0.92,
            })

            if (result.canceled) {
                return
            }

            appendAttachments(result.assets.map(createAttachmentFromImagePickerAsset))
            handleCloseAttachmentSheet()
        } catch {
            Alert.alert(t("chat.attachmentsLoadFailedTitle"), t("chat.attachmentsLoadFailedMessage"))
        }
    }, [appendAttachments, cameraPermission?.granted, handleCloseAttachmentSheet, requestCameraPermission, t])

    const handlePickFiles = useCallback(async () => {
        try {
            const result = await DocumentPicker.getDocumentAsync({
                copyToCacheDirectory: true,
                multiple: true,
                type: "*/*",
            })

            if (result.canceled) {
                return
            }

            appendAttachments(
                result.assets.map((asset) => ({
                    fileName: asset.name,
                    mimeType: asset.mimeType ?? "application/octet-stream",
                    uri: asset.uri,
                })),
            )
            handleCloseAttachmentSheet()
        } catch {
            Alert.alert(t("chat.attachmentsLoadFailedTitle"), t("chat.attachmentsLoadFailedMessage"))
        }
    }, [appendAttachments, handleCloseAttachmentSheet, t])

    const handleRemoveAttachment = useCallback((attachmentIndex: number) => {
        setAttachments((currentAttachments) => currentAttachments.filter((_, index) => index !== attachmentIndex))
    }, [])

    const startVoiceRecording = useCallback(async () => {
        if (voiceStarting.current || sending || voiceTranscribing) {
            return
        }

        voiceStarting.current = true
        Keyboard.dismiss()

        try {
            if (!await requestChatRecordingPermission(t)) return

            await setAudioModeAsync(CHAT_RECORDING_AUDIO_MODE)
            await audioRecorder.prepareToRecordAsync()
            if (!screenActiveRef.current) { await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE); return }
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
        if (!voiceRecording || voiceTranscribing) {
            return
        }

        setVoiceRecording(false)
        setVoiceTranscribing(true)
        let transcribedText = ""

        try {
            await audioRecorder.stop()
            const audioUri = audioRecorder.uri ?? audioRecorder.getStatus().url
            await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE)

            if (!audioUri) {
                throw new Error("Missing recording uri")
            }

            const transcription = await transcribeMyAiChatVoice({
                fileName: getVoiceRecordingFilename(audioUri),
                mimeType: getVoiceRecordingMimeType(audioUri),
                uri: audioUri,
            })
            transcribedText = transcription.text.trim()
            if (!transcribedText) {
                throw new Error("Empty transcription")
            }
        } catch {
            Alert.alert(t("chat.voiceTranscriptionFailedTitle"), t("chat.voiceTranscriptionFailedMessage"))
        } finally {
            setVoiceTranscribing(false)
            await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined)
        }

        if (!transcribedText) {
            return
        }

        try {
            showConversation()
            await sendMessage(transcribedText)
        } catch (sendError) {
            Alert.alert(
                t("chat.sendFailedTitle"),
                sendError instanceof Error ? sendError.message : t("chat.sendFailedMessage"),
            )
        }
    }, [audioRecorder, sendMessage, showConversation, t, voiceRecording, voiceTranscribing])

    const handleVoiceButtonPress = useCallback(async () => {
        if (voiceRecording) {
            await stopVoiceRecording()
            return
        }

        await startVoiceRecording()
    }, [startVoiceRecording, stopVoiceRecording, voiceRecording])

    const handleSend = async () => {
        const draftText = draft.trim()
        const queuedAttachments = attachments
        const hasContent = Boolean(draftText) || queuedAttachments.length > 0

        if (!hasContent || sending || voiceRecording || voiceTranscribing) {
            return
        }

        showConversation()
        const text = draftText || t("chat.attachmentFallbackMessage")
        setDraft("")
        setAttachments([])

        try {
            await sendMessage(text, queuedAttachments)
        } catch (sendError) {
            setDraft(draftText)
            setAttachments(queuedAttachments)
            if (sendError instanceof AiConsentDeclinedError) return
            Alert.alert(
                t("chat.sendFailedTitle"),
                sendError instanceof Error ? sendError.message : t("chat.sendFailedMessage"),
            )
        }
    }

    const formatTime = (isoTimestamp: string) => {
        const parsedDate = new Date(isoTimestamp)
        if (Number.isNaN(parsedDate.getTime())) {
            return ""
        }
        return parsedDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    }

    const getDayToken = (isoTimestamp: string) => {
        const parsedDate = new Date(isoTimestamp)
        if (Number.isNaN(parsedDate.getTime())) {
            return ""
        }
        return parsedDate.toDateString()
    }

    const formatDayLabel = (isoTimestamp: string) => {
        const parsedDate = new Date(isoTimestamp)
        if (Number.isNaN(parsedDate.getTime())) {
            return ""
        }
        return parsedDate.toLocaleDateString([], { month: "long", day: "numeric" })
    }

    const getMessageMeta = (message: ChatDisplayMessage) => {
        const timeLabel = formatTime(message.created_at)

        if (message.delivery_status === "pending") {
            return timeLabel ? `${timeLabel} · ${t("chat.messagePending")}` : t("chat.messagePending")
        }

        if (message.delivery_status === "failed") {
            return timeLabel ? `${timeLabel} · ${t("chat.messageFailed")}` : t("chat.messageFailed")
        }

        return timeLabel
    }

    const handleCopyMessage = useCallback(async (messageText: string) => {
        const nextText = messageText.trim()
        if (!nextText) {
            return
        }

        try {
            await Clipboard.setStringAsync(nextText)
        } catch {
            // Keep chat interactions quiet even if clipboard write fails on some platforms.
        }
    }, [])

    const handleOpenMessageLink = useCallback((href: string) => {
        const normalizedHref = href.trim()
        const productMatch = normalizedHref.match(INTERNAL_PRODUCT_LINK_PATTERN)

        if (productMatch?.[1]) {
            router.push(getProductRoute(productMatch[1]))
            return
        }

        if (SAFE_LINK_PROTOCOL_PATTERN.test(normalizedHref)) {
            void Linking.openURL(normalizedHref).catch(() => undefined)
        }
    }, [router])

    const handleInteractiveAction = useCallback(async (message: ChatDisplayMessage, action: AIInteractiveAction, quantity?: number) => {
        if (activeActionId) {
            return
        }

        if (action.type === "open_product" && action.product_id) {
            void trackCustomerEvent("ai_action_clicked", {
                entityType: "ai_message",
                entityId: message.id,
                properties: { action_id: action.id, action_type: action.type, product_id: action.product_id },
            }).catch(() => undefined)
            router.push(getProductRoute(action.product_id))
            return
        }

        if (action.type === "open_checkout") {
            void trackCustomerEvent("ai_action_clicked", {
                entityType: "ai_message",
                entityId: message.id,
                properties: { action_id: action.id, action_type: action.type },
            }).catch(() => undefined)
            router.push(ROUTES.checkout)
            return
        }

        if (action.type === "ask_ai") {
            const prompt = action.prompt?.trim()
            if (!prompt || sending) {
                return
            }

            try {
                void trackCustomerEvent("ai_action_clicked", {
                    entityType: "ai_message",
                    entityId: message.id,
                    properties: { action_id: action.id, action_type: action.type },
                }).catch(() => undefined)
                await sendMessage(prompt)
                void trackCustomerEvent("ai_action_completed", {
                    entityType: "ai_message",
                    entityId: message.id,
                    properties: { action_id: action.id, action_type: action.type },
                }).catch(() => undefined)
            } catch (sendError) {
                Alert.alert(
                    t("chat.sendFailedTitle"),
                    sendError instanceof Error ? sendError.message : t("chat.sendFailedMessage"),
                )
            }
            return
        }

        if (action.type !== "add_to_basket") {
            return
        }

        if (action.completed && action.created_basket_item_id) {
            return
        }

        if (!action.action_token) {
            Alert.alert(t("chat.sendFailedTitle"), t("chat.sendFailedMessage"))
            return
        }

        setActiveActionId(action.id)
        try {
            await performAction({
                action_id: action.id,
                action_token: action.action_token,
                message_id: message.id,
                quantity,
            })
        } catch (actionError) {
            Alert.alert(
                t("chat.sendFailedTitle"),
                actionError instanceof Error ? actionError.message : t("chat.sendFailedMessage"),
            )
        } finally {
            setActiveActionId(null)
        }
    }, [activeActionId, performAction, router, sendMessage, sending, t])

    const handleAddVariantToBasket = useCallback(async (variant: AIInteractiveVariant) => {
        if (activeBasketVariantId || activeActionId) {
            return
        }

        setActiveBasketVariantId(variant.id)
        try {
            await addBasketItem(variant.id, 1)
        } catch (basketError) {
            Alert.alert(
                t("chat.sendFailedTitle"),
                basketError instanceof Error ? basketError.message : t("chat.sendFailedMessage"),
            )
        } finally {
            setActiveBasketVariantId(null)
        }
    }, [activeActionId, activeBasketVariantId, addBasketItem, t])

    const handleBasketItemQuantityChange = useCallback(async (item: BasketItemRead, nextQuantity: number) => {
        if (activeBasketVariantId || activeActionId) {
            return
        }

        setActiveBasketVariantId(item.variant_id)
        try {
            if (nextQuantity < 1) {
                await removeBasketItem(item.id)
            } else {
                await updateBasketItemQuantity(item.id, nextQuantity)
            }
        } catch (basketError) {
            Alert.alert(
                t("chat.sendFailedTitle"),
                basketError instanceof Error ? basketError.message : t("chat.sendFailedMessage"),
            )
        } finally {
            setActiveBasketVariantId(null)
        }
    }, [activeActionId, activeBasketVariantId, removeBasketItem, t, updateBasketItemQuantity])

    const hasDraft = Boolean(draft.trim())
    const hasComposerContent = hasDraft || attachments.length > 0
    const reduceMotion = useChatReducedMotion()
    const composerDisabled = !aiAllowed || !aiContentReady || sending || voiceTranscribing
    const inputBackgroundColor = isDark ? "#263040" : "#F2FAF5"
    const handleComposerAction = () => {
        if (voiceRecording || !hasComposerContent) void handleVoiceButtonPress()
        else void handleSend()
    }
    const closeMentor = () => {
        companion.setEditor(null)
        setMentorOpen(false)
    }
    const finishMentorDismiss = () => {
        if (!mentorExitToShop.current) return
        mentorExitToShop.current = false
        router.replace(ROUTES.home)
    }
    const exitMentorToShop = () => {
        mentorExitToShop.current = true
        closeMentor()
        if (Platform.OS !== "ios") requestAnimationFrame(finishMentorDismiss)
    }
    const handleBack = () => {
        if (mentor) mentor.onBack()
        else if (chatMode === "community" && topicNavigation) topicNavigation.onBack()
        else router.push(ROUTES.discover)
    }
    const scrollInsets = { paddingTop: scrollTopInset + spacing.sm, paddingBottom: (iosChat ? spacing.sm : scrollBottomInset + spacing.sm) + (mentorAvailable ? MENTOR_SHORTCUT_HEIGHT + 8 : 0) }
    const scrollProps = {
        automaticallyAdjustKeyboardInsets: false,
        automaticallyAdjustContentInsets: false,
        automaticallyAdjustsScrollIndicatorInsets: overlaysChatChrome ? false : undefined,
        contentInsetAdjustmentBehavior: "never" as const,
        keyboardDismissMode: Platform.OS === "ios" ? "interactive" as const : "on-drag" as const,
        keyboardShouldPersistTaps: "handled" as const,
        scrollEventThrottle: 16,
        scrollIndicatorInsets: overlaysChatChrome ? { top: scrollTopInset, bottom: scrollBottomInset } : undefined,
    }
    const refreshControl = <RefreshControl
        onRefresh={() => { void refresh() }}
        refreshing={refreshing}
        tintColor={palette.primary}
    />

    return (
        <View style={chatScreenStyles.container}>
            <ChatBackdrop />
            <ChatKeyboardLayout style={chatScreenStyles.content}>
        <View
            testID="ai-chat-fixed-header"
            pointerEvents={overlaysChatChrome ? "box-none" : "auto"}
            style={[chatScreenStyles.fixedHeader, chatScreenStyles.mentorHeader, overlaysChatChrome && chatScreenStyles.headerOverlay, { paddingTop: topBarOffset }]}
        >
        <View pointerEvents={overlaysChatChrome ? "box-none" : "auto"} style={chatScreenStyles.topBarRow}>
            {nativeIosChat && NativeChatAction ? (
                <NativeChatAction action="back" dark={isDark} label={t("nav.back")} onAction={handleBack} style={chatScreenStyles.nativeChatButton} />
            ) : <Pressable
                accessibilityLabel={t("nav.back")}
                accessibilityRole="button"
                onPress={handleBack}
                style={({ pressed }) => [chatScreenStyles.topBackButton, chatScreenStyles.mentorBackButton, iosChat && [chatScreenStyles.privateChatButton, { backgroundColor: inputBackgroundColor }], iosChat && pressed && chatScreenStyles.circleButtonPressed]}
            >
                <Svg fill="none" height={20} viewBox="0 0 24 24" width={20}>
                    <Path
                        d="M15.5 5.5 9 12l6.5 6.5"
                        stroke={iosChat ? palette.text : "#12161A"}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.2}
                    />
                </Svg>
            </Pressable>}
            {mentorChat ? <ChatTopicTitle title={mt("Наставник")} /> : chatMode === "community" && topicNavigation ? <ChatTopicTitle title={topicNavigation.title} notifications={topicNavigation.notifications} /> : <ChatModeSwitcher mode={chatMode} solidStyle={simpleIosChat} nativeDark={nativeIosChat ? isDark : undefined} mentorStyle onChange={handleChatModeChange} supportUnreadCount={supportUnread} unreadCount={communityUnread} />}
        </View>
        </View>
            <ChatModeTransition mode={chatMode} style={overlaysChatChrome ? { zIndex: 1 } : undefined}>
            <ChatModePane mode="ai" active={chatMode === "ai"}>
                <ChatKeyboardPane style={chatScreenStyles.content}>
                <View testID="ai-chat-scroll-body" style={chatScreenStyles.chatBody}>
                {chatMode === "ai" && !aiContentReady ? <View style={overlaysChatChrome && { paddingTop: headerHeight }}>
                <QuietLoading loading={chatMode === "ai" && !aiContentReady} />
                </View> : null}
                {aiContentReady && error && !chat && chatMode === "ai" ? (
                    <View style={[chatScreenStyles.initialStateOverlay, overlaysChatChrome && { top: headerHeight }]}>
                        <EmptyState
                            title={t("chat.loadFailedTitle")}
                            description={error || t("chat.loadFailedMessage")}
                            actionLabel={t("chat.retry")}
                            onPressAction={() => {
                                void refresh()
                            }}
                            variant="plain"
                        />
                    </View>
                ) : null}

                        <ContentReveal ready={aiContentReady} style={{ flex: 1, minHeight: 0 }}>
                        <View style={chatScreenStyles.content}>
                        <ChatMessageScrollView
                            {...scrollProps}
                            testID="ai-chat-message-history"
                            contentContainerStyle={[chatScreenStyles.messagesContent, scrollInsets]}
                            ref={scrollRef}
                            onScroll={chatScroll.onScroll}
                            onScrollBeginDrag={chatScroll.onScrollBeginDrag}
                            onContentSizeChange={chatScroll.onContentSizeChange}
                            onLayout={chatScroll.onLayout}
                            refreshControl={refreshControl}
                            style={chatScreenStyles.messagesScroll}
                        >
                            {aiContentReady && messages.length ? (
                                <View style={chatScreenStyles.messageList}>
                                    {messages.map((message, messageIndex) => {
                                        const isUserMessage = message.sender === "user"
                                        const currentDayToken = getDayToken(message.created_at)
                                        const previousDayToken = messageIndex > 0 ? getDayToken(messages[messageIndex - 1].created_at) : ""
                                        const shouldShowDayChip = messageIndex === 0 || currentDayToken !== previousDayToken
                                        const hasImageAttachments = message.attachments.some(isImageAttachment)
                                        const displayText =
                                            message.attachments.length > 0 &&
                                            message.text.trim() === t("chat.attachmentFallbackMessage")
                                                ? ""
                                                : message.text

                                        return (
                                            <AnimatedMessageBlock key={message.client_id ?? message.id} animate={!initialMessageIds.current?.has(message.id)}>
                                                <View style={chatScreenStyles.messageBlock}>
                                                    {shouldShowDayChip ? (
                                                        <View style={chatScreenStyles.dayChip}>
                                                            <Text style={chatScreenStyles.dayChipText}>
                                                                {formatDayLabel(message.created_at)}
                                                            </Text>
                                                        </View>
                                                    ) : null}
                                                    <Pressable
                                                        accessibilityHint={displayText ? "Copies message text" : undefined}
                                                        accessibilityRole={displayText ? "button" : undefined}
                                                        disabled={!displayText}
                                                        onPress={() => {
                                                            void handleCopyMessage(displayText)
                                                        }}
                                                        style={({ pressed }) => [
                                                            chatScreenStyles.messageBubble,
                                                            isUserMessage
                                                                ? chatScreenStyles.userMessageBubble
                                                                : chatScreenStyles.aiMessageBubble,
                                                            hasImageAttachments
                                                                ? chatScreenStyles.messageBubbleWithMedia
                                                                : null,
                                                            message.delivery_status === "failed"
                                                                ? chatScreenStyles.failedMessageBubble
                                                                : null,
                                                            pressed ? chatScreenStyles.messageBubblePressed : null,
                                                        ]}
                                                    >
                                                        {message.attachments.length > 0 ? (
                                                            <MessageAttachmentList
                                                                attachments={message.attachments}
                                                                isUserMessage={isUserMessage}
                                                                mediaWidth={messageMediaWidth}
                                                            />
                                                        ) : null}
                                                        {displayText ? (
                                                            <MessageMarkdown
                                                                hasImageAttachments={hasImageAttachments}
                                                                isUserMessage={isUserMessage}
                                                                markdown={displayText}
                                                                onOpenLink={handleOpenMessageLink}
                                                                width={messageTextWidth}
                                                            />
                                                        ) : null}
                                                        <Text
                                                            style={[
                                                                chatScreenStyles.messageMeta,
                                                                isUserMessage ? chatScreenStyles.userMessageMeta : null,
                                                                message.delivery_status === "pending"
                                                                    ? chatScreenStyles.pendingMessageMeta
                                                                    : null,
                                                                message.delivery_status === "failed"
                                                                    ? chatScreenStyles.failedMessageMeta
                                                                    : null,
                                                            ]}
                                                        >
                                                            {getMessageMeta(message)}
                                                        </Text>
                                                    </Pressable>
                                                    {!isUserMessage && message.interactive ? (
                                                        <AIInteractiveContent
                                                            activeActionId={activeActionId}
                                                            activeBasketVariantId={activeBasketVariantId}
                                                            basket={basket}
                                                            onAddVariantToBasket={handleAddVariantToBasket}
                                                            onActionPress={(action, quantity) => {
                                                                void handleInteractiveAction(message, action, quantity)
                                                            }}
                                                            onBasketItemQuantityChange={handleBasketItemQuantityChange}
                                                            onOpenProduct={(productId) => {
                                                                void trackCustomerEvent("ai_action_clicked", {
                                                                    entityType: "ai_message",
                                                                    entityId: message.id,
                                                                    properties: { action_type: "open_product_card", product_id: productId },
                                                                }).catch(() => undefined)
                                                                router.push(getProductRoute(productId))
                                                            }}
                                                            payload={message.interactive}
                                                        />
                                                    ) : null}
                                                    {mentorChat && (message.dialogue_cards?.length || message.companion_cards?.length) ? <CompanionCards controller={companion} message={message} onChanged={refresh} /> : null}
                                                </View>
                                            </AnimatedMessageBlock>
                                        )
                                    })}
                                    {aiTyping ? (
                                        <AnimatedMessageBlock key="ai-typing">
                                            <View style={chatScreenStyles.messageBlock}>
                                                <AiTypingBubble />
                                            </View>
                                        </AnimatedMessageBlock>
                                    ) : null}
                                </View>
                            ) : null}
                        </ChatMessageScrollView>
                        </View>
                        {aiContentReady && !messages.length && !(loading && !chat) && !(error && !chat) ? (
                            <View pointerEvents="none" style={chatScreenStyles.emptyCenterOverlay}>
                                <View style={chatScreenStyles.emptyBubble}>
                                    <Text style={chatScreenStyles.emptyText}>{t("chat.emptyDescription")}</Text>
                                </View>
                            </View>
                        ) : null}

                        {error && chat && !overlaysChatChrome ? (
                            <View style={chatScreenStyles.composerError}>
                                <Text style={chatScreenStyles.inlineError}>{error}</Text>
                            </View>
                        ) : null}

                        </ContentReveal>

                        {iosChat && !followingLatest && aiContentReady && messages.length > 0 ? (
                            <ChatKeyboardFloating pointerEvents="box-none" style={{ position: "absolute", right: 8, bottom: composerDockHeight + 8, zIndex: 13 }}>
                            {nativeIosChat && NativeChatAction ? (
                                <NativeChatAction
                                    action="latest"
                                    dark={isDark}
                                    label={t("chat.jumpToLatest")}
                                    onAction={() => followLatest(!reduceMotion)}
                                    style={[chatScreenStyles.jumpToLatest, chatScreenStyles.nativeJumpToLatest, { bottom: 0, position: "relative" }]}
                                />
                            ) : <Pressable
                                accessibilityLabel={t("chat.jumpToLatest")}
                                accessibilityRole="button"
                                onPress={() => followLatest(!reduceMotion)}
                                style={({ pressed }) => [
                                    chatScreenStyles.jumpToLatest,
                                    { bottom: 0, position: "relative", backgroundColor: inputBackgroundColor },
                                    pressed && chatScreenStyles.circleButtonPressed,
                                ]}
                            >
                                <Svg fill="none" width={21} height={21} viewBox="0 0 24 24">
                                    <Path d="m5 9 7 7 7-7" stroke={palette.text} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
                                </Svg>
                            </Pressable>}
                            </ChatKeyboardFloating>
                        ) : null}

                        {mentorAvailable ? <ChatKeyboardFloating pointerEvents="box-none" style={{ position: "absolute", left: 8, right: iosChat && !followingLatest && aiContentReady && messages.length > 0 ? 60 : 8, bottom: composerDockHeight + 8, zIndex: 13 }}>
                            <MentorShortcut onPress={openMentor} disabled={voiceStatusVisible} goal={companion.state?.profile?.data.goal} />
                        </ChatKeyboardFloating> : null}

                        <ChatComposerDock
                            testID="ai-chat-composer-dock"
                            onLayout={event => setComposerDockHeight(event.nativeEvent.layout.height)}
                            pointerEvents={overlaysChatChrome ? "box-none" : "auto"}
                            style={[
                                chatScreenStyles.composerDock,
                                chatScreenStyles.composerDockInFlow,
                                overlaysChatChrome ? chatScreenStyles.composerDockOverlay : null,
                            ]}
                        >
                            {error && chat && overlaysChatChrome ? (
                                <View style={chatScreenStyles.composerError}>
                                    <Text style={chatScreenStyles.inlineError}>{error}</Text>
                                </View>
                            ) : null}
                            {voiceStatusVisible ? (
                                <View style={chatScreenStyles.voiceStatusPill}>
                                    {voiceTranscribing ? (
                                        <ActivityIndicator color={palette.primary} size="small" />
                                    ) : (
                                        <View style={chatScreenStyles.voiceStatusDot} />
                                    )}
                                    <Text style={chatScreenStyles.voiceStatusText}>
                                        {voiceTranscribing
                                            ? t("chat.voiceTranscribing")
                                            : `${t("chat.voiceRecording")} ${formatVoiceDuration(audioRecorderState.durationMillis)}`}
                                    </Text>
                                </View>
                            ) : null}
                            <QueuedAttachmentStrip attachments={attachments} onRemove={handleRemoveAttachment} />
                            <View pointerEvents={overlaysChatChrome ? "box-none" : "auto"} style={{ minHeight: 44 }}>
                                <ChatComposer
                                    value={draft}
                                    onChangeText={setDraft}
                                    inputRef={mentorInputRef}
                                    placeholder={voiceRecording ? t("chat.voiceRecording") : mentorChat ? mt("Спросите наставника") : t("chat.inputPlaceholder")}
                                    onAttachment={handleOpenAttachmentSheet}
                                    onAction={handleComposerAction}
                                    hasContent={hasComposerContent}
                                    disabled={composerDisabled}
                                    attachmentDisabled={voiceStatusVisible}
                                    recording={voiceRecording}
                                    busy={sending || voiceTranscribing}
                                    transcribing={voiceTranscribing}
                                />
                            </View>
                        </ChatComposerDock>
                </View>
                <AttachmentSheet
                    activeMode={attachmentMode}
                    bottomInset={bottomInset}
                    onClose={handleCloseAttachmentSheet}
                    onOpenCamera={() => {
                        void handleOpenCamera()
                    }}
                    onOpenNativeGallery={() => {
                        void handleOpenNativeGallery()
                    }}
                    onPickFiles={() => {
                        void handlePickFiles()
                    }}
                    onSelectMode={handleSelectAttachmentMode}
                    visible={attachmentSheetVisible}
                />
                </ChatKeyboardPane>
            </ChatModePane>
            {communityAvailable ? <ChatModePane mode="community" active={chatMode === "community"}>
            <CommunityChatScreen
                embedded
                headerInset={scrollTopInset}
                onTopicNavigationChange={setTopicNavigation}
                active={chatMode === "community"}
                mode={chatMode}
                onEnabledChange={handleCommunityEnabledChange}
                onModeChange={handleChatModeChange}
                onUnreadChange={handleCommunityUnreadChange}
                requestedTopicId={requestedTopicId}
                supportUnreadCount={supportUnread}
                unreadCount={communityUnread}
            />
            </ChatModePane> : null}
            {!mentorChat ? <ChatModePane mode="support" active={chatMode === "support"}>
            <SupportChatScreen
                embedded
                headerInset={scrollTopInset}
                active={chatMode === "support"}
                communityUnreadCount={communityUnread}
                mode={chatMode}
                onModeChange={handleChatModeChange}
                onUnreadChange={setSupportUnread}
                requestedConversationId={requestedConversationId}
                supportUnreadCount={supportUnread}
            />
            </ChatModePane> : null}
            </ChatModeTransition>
            {overlaysChatChrome ? <ChatEdgeBlur dark={isDark} topEdge style={[chatScreenStyles.dialogTopBlur, { height: headerHeight + 10 }]} /> : null}
            </ChatKeyboardLayout>
            {mentorAvailable && mentorVisited ? <MentorSetup controller={companion} visible={mentorOpen} onClose={closeMentor} onExitToShop={exitMentorToShop} onDismiss={finishMentorDismiss} initialTab={mentorInitialTab} renderChat={props => <MentorChatScreen {...props} controller={companion} />} /> : null}
        </View>
    )
}
