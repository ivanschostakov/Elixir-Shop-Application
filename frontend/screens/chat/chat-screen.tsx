import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    ImageBackground,
    Keyboard,
    KeyboardAvoidingView,
    Linking,
    Platform,
    Pressable,
    RefreshControl,
    ScrollView,
    Text,
    TextInput,
    type NativeScrollEvent,
    type NativeSyntheticEvent,
    useWindowDimensions,
    View,
} from "react-native"
import * as Clipboard from "expo-clipboard"
import { useCameraPermissions } from "expo-camera"
import {
    RecordingPresets,
    requestRecordingPermissionsAsync,
    setAudioModeAsync,
    useAudioRecorder,
    useAudioRecorderState,
} from "expo-audio"
import * as Application from "expo-application"
import * as DocumentPicker from "expo-document-picker"
import * as ImagePicker from "expo-image-picker"
import * as MediaLibrary from "expo-media-library"
import { useRouter } from "expo-router"
import Svg, { Path } from "react-native-svg"

import AttachmentSvgIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import { EdgeBlur } from "@/components/effects/edge-blur"
import { EmptyState } from "@/components/content/empty-state"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { ROUTES, getProductRoute } from "@/constants/routes"
import { useBasket } from "@/hooks/basket/use-basket"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { useAiChat, type ChatDisplayMessage } from "@/hooks/chat/use-ai-chat"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { transcribeMyAiChatVoice } from "@/services/api/ai-chat"
import type {
    AIInteractiveAction,
    AIInteractiveVariant,
    UploadableChatAttachment,
} from "@/services/api/ai-chat.types"
import type { BasketItemRead } from "@/types/basket"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { colors } from "@/theme/colors"
import { spacing } from "@/theme/spacing"
import { chatScreenStyles } from "./chat-screen.styles"
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
    SendActionButton,
} from "@/screens/chat/chat-screen.core-components"
import {
    createAttachmentFromImagePickerAsset,
    createAttachmentFromMediaAsset,
    formatVoiceDuration,
    getVoiceRecordingFilename,
    getVoiceRecordingMimeType,
    isImageAttachment,
} from "@/screens/chat/chat-attachments"
import {
    type AttachmentMode,
    CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD,
    CHAT_BACKGROUND_DARK,
    CHAT_BACKGROUND_LIGHT,
    CHAT_IDLE_AUDIO_MODE,
    CHAT_RECORDING_AUDIO_MODE,
    IOS_MINIMUM_VOICE_RECORDING_BUILD,
    INTERNAL_PRODUCT_LINK_PATTERN,
    MESSAGE_IMAGE_MAX_WIDTH,
    RECENT_PHOTO_LIMIT,
    SAFE_LINK_PROTOCOL_PATTERN,
} from "@/screens/chat/chat-screen.constants"

function nativeBuildNumber() {
    const parsedBuild = Number(Application.nativeBuildVersion)
    return Number.isFinite(parsedBuild) ? parsedBuild : 0
}

export default function ChatScreen() {
    const router = useRouter()
    const { t } = useLanguage()
    const { isDark, themeName } = useTheme()
    const { width: screenWidth } = useWindowDimensions()
    const { top: topInset, bottom: bottomInset } = useSafeAreaInsets()
    const [cameraPermission, requestCameraPermission] = useCameraPermissions()
    const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY)
    const audioRecorderState = useAudioRecorderState(audioRecorder, 200)
    const { aiTyping, chat, error, loading, messages, performAction, refresh, refreshing, sending, sendMessage } = useAiChat()
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableChatAttachment[]>([])
    const [activeActionId, setActiveActionId] = useState<string | null>(null)
    const [activeBasketVariantId, setActiveBasketVariantId] = useState<number | null>(null)
    const [attachmentMode, setAttachmentMode] = useState<AttachmentMode>("photo")
    const [attachmentSheetVisible, setAttachmentSheetVisible] = useState(false)
    const [albumSelectorVisible, setAlbumSelectorVisible] = useState(false)
    const [photoAlbums, setPhotoAlbums] = useState<MediaLibrary.Album[]>([])
    const [photoAssets, setPhotoAssets] = useState<MediaLibrary.Asset[]>([])
    const [photoAssetsLoading, setPhotoAssetsLoading] = useState(false)
    const [photoPermissionDenied, setPhotoPermissionDenied] = useState(false)
    const [selectedPhotoAlbumId, setSelectedPhotoAlbumId] = useState<string | null>(null)
    const [selectedPhotoIds, setSelectedPhotoIds] = useState<string[]>([])
    const [keyboardVisible, setKeyboardVisible] = useState(false)
    const [voiceRecording, setVoiceRecording] = useState(false)
    const [voiceTranscribing, setVoiceTranscribing] = useState(false)
    const scrollRef = useRef<ScrollView | null>(null)
    const shouldAutoScrollRef = useRef(true)
    const cameraPermissionPromptedRef = useRef(false)
    const topBarOffset = topInset + 8
    const composerBottomInset = keyboardVisible ? spacing.sm : Math.max(bottomInset, spacing.sm)
    const topEdgeFadeHeight = Math.max(topInset + 86, 112)
    const bottomEdgeFadeHeight = composerBottomInset + (keyboardVisible ? 72 : 96)
    const edgeFadeColor = isDark ? "#07121C" : "#E8F7DF"
    const voiceStatusVisible = voiceRecording || voiceTranscribing
    const composerOffset = composerBottomInset + 72 + (attachments.length > 0 ? 50 : 0) + (voiceStatusVisible ? 40 : 0)
    const messageMediaWidth = Math.min(screenWidth * 0.68, MESSAGE_IMAGE_MAX_WIDTH)
    const messageTextWidth = Math.max(180, Math.min(screenWidth * 0.74, 330))
    const voiceRecordingSupported =
        __DEV__ || Platform.OS !== "ios" || nativeBuildNumber() >= IOS_MINIMUM_VOICE_RECORDING_BUILD
    const cameraPreviewActive =
        attachmentSheetVisible &&
        attachmentMode === "photo" &&
        cameraPermission?.granted === true
    const selectedPhotoAlbumTitle = useMemo(
        () => photoAlbums.find((album) => album.id === selectedPhotoAlbumId)?.title ?? t("chat.attachmentsPhotoTitle"),
        [photoAlbums, selectedPhotoAlbumId, t],
    )
    const { basket } = useBasket()
    const {
        addItem: addBasketItem,
        removeItem: removeBasketItem,
        updateItemQuantity: updateBasketItemQuantity,
    } = useBasketMutations()

    useApplyScreenTemplate("feed", {
        header: "none",
        footer: "none",
        mode: "fullscreen",
    })

    useEffect(() => {
        if (!messages.length && !aiTyping) {
            return
        }

        if (!shouldAutoScrollRef.current) {
            return
        }

        const animationFrameId = requestAnimationFrame(() => {
            scrollRef.current?.scrollToEnd({ animated: true })
        })

        return () => {
            cancelAnimationFrame(animationFrameId)
        }
    }, [aiTyping, messages.length])

    const handleMessagesScroll = useCallback((event: NativeSyntheticEvent<NativeScrollEvent>) => {
        const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent
        const distanceFromBottom = contentSize.height - (contentOffset.y + layoutMeasurement.height)
        shouldAutoScrollRef.current = distanceFromBottom <= CHAT_AUTO_SCROLL_BOTTOM_THRESHOLD
    }, [])

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
            // Ignore cleanup failures when the recorder native object is already released.
        }
    }, [audioRecorder])

    const loadRecentPhotos = useCallback(async () => {
        setPhotoAssetsLoading(true)
        try {
            const permission = await MediaLibrary.requestPermissionsAsync(false, ["photo"])
            if (!permission.granted) {
                setPhotoPermissionDenied(true)
                setPhotoAssets([])
                return
            }

            setPhotoPermissionDenied(false)
            const [result, albums] = await Promise.all([
                MediaLibrary.getAssetsAsync({
                    album: selectedPhotoAlbumId ?? undefined,
                    first: RECENT_PHOTO_LIMIT,
                    mediaType: MediaLibrary.MediaType.photo,
                    sortBy: [[MediaLibrary.SortBy.creationTime, false]],
                }),
                MediaLibrary.getAlbumsAsync({ includeSmartAlbums: true }),
            ])
            setPhotoAlbums(albums.filter((album) => album.assetCount > 0))
            setPhotoAssets(result.assets)
        } catch {
            Alert.alert(t("chat.attachmentsLoadFailedTitle"), t("chat.attachmentsLoadFailedMessage"))
        } finally {
            setPhotoAssetsLoading(false)
        }
    }, [selectedPhotoAlbumId, t])

    useEffect(() => {
        if (!attachmentSheetVisible || attachmentMode !== "photo" || photoPermissionDenied) {
            return
        }

        void loadRecentPhotos()
    }, [attachmentMode, attachmentSheetVisible, loadRecentPhotos, photoPermissionDenied])

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
        setSelectedPhotoIds([])
        setAlbumSelectorVisible(false)
    }, [])

    const handleSelectPhotoAlbum = useCallback((albumId: string | null) => {
        setSelectedPhotoAlbumId(albumId)
        setSelectedPhotoIds([])
        setAlbumSelectorVisible(false)
        setPhotoAssets([])
    }, [])

    const handleSelectAttachmentMode = useCallback((mode: AttachmentMode) => {
        setAttachmentMode(mode)
        setAlbumSelectorVisible(false)
    }, [])

    const handleToggleAlbumSelector = useCallback(() => {
        setAlbumSelectorVisible((currentValue) => !currentValue)
    }, [])

    const handleOpenNativeGallery = useCallback(async () => {
        try {
            const permission = await ImagePicker.requestMediaLibraryPermissionsAsync()
            if (!permission.granted) {
                Alert.alert(t("chat.attachmentsPhotoPermissionTitle"), t("chat.attachmentsPhotoPermissionMessage"))
                return
            }

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

    const handleTogglePhoto = useCallback((assetId: string) => {
        setSelectedPhotoIds((currentSelectedIds) =>
            currentSelectedIds.includes(assetId)
                ? currentSelectedIds.filter((currentAssetId) => currentAssetId !== assetId)
                : [...currentSelectedIds, assetId],
        )
    }, [])

    const handleAddSelectedPhotos = useCallback(async () => {
        const selectedPhotoAssets = photoAssets.filter((asset) => selectedPhotoIds.includes(asset.id))
        if (!selectedPhotoAssets.length) {
            return
        }

        try {
            const nextAttachments = await Promise.all(selectedPhotoAssets.map(createAttachmentFromMediaAsset))
            appendAttachments(nextAttachments)
            handleCloseAttachmentSheet()
        } catch {
            Alert.alert(t("chat.attachmentsLoadFailedTitle"), t("chat.attachmentsLoadFailedMessage"))
        }
    }, [appendAttachments, handleCloseAttachmentSheet, photoAssets, selectedPhotoIds, t])

    const handleRemoveAttachment = useCallback((attachmentIndex: number) => {
        setAttachments((currentAttachments) => currentAttachments.filter((_, index) => index !== attachmentIndex))
    }, [])

    const startVoiceRecording = useCallback(async () => {
        if (sending || voiceTranscribing) {
            return
        }

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
            await sendMessage(transcribedText)
        } catch (sendError) {
            Alert.alert(
                t("chat.sendFailedTitle"),
                sendError instanceof Error ? sendError.message : t("chat.sendFailedMessage"),
            )
        }
    }, [audioRecorder, sendMessage, t, voiceRecording, voiceTranscribing])

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

        const text = draftText || t("chat.attachmentFallbackMessage")
        setDraft("")
        setAttachments([])

        try {
            await sendMessage(text, queuedAttachments)
        } catch (sendError) {
            setDraft(draftText)
            setAttachments(queuedAttachments)
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
            router.push(getProductRoute(action.product_id))
            return
        }

        if (action.type === "open_checkout") {
            router.push(ROUTES.checkout)
            return
        }

        if (action.type === "ask_ai") {
            const prompt = action.prompt?.trim()
            if (!prompt || sending) {
                return
            }

            try {
                await sendMessage(prompt)
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
    if (loading && !chat) {
        return (
            <View style={chatScreenStyles.loadingWrap}>
                <ActivityIndicator color={colors.primary} />
            </View>
        )
    }

    if (error && !chat) {
        return (
            <View style={chatScreenStyles.stateWrap}>
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
        )
    }

    return (
        <View style={chatScreenStyles.container}>
            <View style={chatScreenStyles.content}>
                <ImageBackground
                    imageStyle={chatScreenStyles.backgroundImageAsset}
                    resizeMode="cover"
                    source={CHAT_BACKGROUND_LIGHT}
                    style={[
                        chatScreenStyles.backgroundImage,
                        themeName === "dark" ? chatScreenStyles.backgroundImageHidden : null,
                    ]}
                />
                <ImageBackground
                    imageStyle={chatScreenStyles.backgroundImageAsset}
                    resizeMode="cover"
                    source={CHAT_BACKGROUND_DARK}
                    style={[
                        chatScreenStyles.backgroundImage,
                        themeName === "dark" ? null : chatScreenStyles.backgroundImageHidden,
                    ]}
                />
                <View
                    pointerEvents="none"
                    style={[
                        chatScreenStyles.backgroundScrim,
                        isDark ? chatScreenStyles.backgroundScrimDark : chatScreenStyles.backgroundScrimLight,
                    ]}
                />
                <EdgeBlur
                    color={edgeFadeColor}
                    dark={isDark}
                    height={Math.round(topEdgeFadeHeight)}
                    intensity={isDark ? 10 : 7}
                    opacity={isDark ? 0.16 : 0.07}
                    position="top"
                    zIndex={6}
                />
                <EdgeBlur
                    color={edgeFadeColor}
                    dark={isDark}
                    height={Math.round(bottomEdgeFadeHeight)}
                    intensity={isDark ? 11 : 8}
                    opacity={isDark ? 0.18 : 0.08}
                    position="bottom"
                    zIndex={6}
                />

                <View style={[chatScreenStyles.topBarRow, { top: topBarOffset }]}>
                    <Pressable
                        onPress={() => {
                            router.push(ROUTES.discover)
                        }}
                        style={chatScreenStyles.topBackButton}
                    >
                        <Svg fill="none" height={20} viewBox="0 0 24 24" width={20}>
                            <Path
                                d="M15.5 5.5 9 12l6.5 6.5"
                                stroke="#12161A"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2.2}
                            />
                        </Svg>
                    </Pressable>
                </View>

                <KeyboardAvoidingView
                    behavior={Platform.OS === "ios" ? "position" : "height"}
                    contentContainerStyle={chatScreenStyles.keyboardContent}
                    keyboardVerticalOffset={0}
                    style={chatScreenStyles.keyboardLayer}
                >
                    <View style={chatScreenStyles.keyboardContent}>
                        <ScrollView
                            contentContainerStyle={[
                                chatScreenStyles.messagesContent,
                                {
                                    paddingTop: topBarOffset + 56,
                                    paddingBottom: composerOffset,
                                },
                            ]}
                            ref={scrollRef}
                            keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
                            keyboardShouldPersistTaps="handled"
                            onScroll={handleMessagesScroll}
                            scrollEventThrottle={16}
                            refreshControl={(
                                <RefreshControl
                                    onRefresh={() => {
                                        void refresh()
                                    }}
                                    refreshing={refreshing}
                                    tintColor={colors.primary}
                                />
                            )}
                            style={chatScreenStyles.messagesScroll}
                        >
                            {messages.length ? (
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
                                            <AnimatedMessageBlock key={message.client_id ?? message.id}>
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
                                                                router.push(getProductRoute(productId))
                                                            }}
                                                            payload={message.interactive}
                                                        />
                                                    ) : null}
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
                        </ScrollView>
                        {!messages.length ? (
                            <View pointerEvents="none" style={chatScreenStyles.emptyCenterOverlay}>
                                <View style={chatScreenStyles.emptyBubble}>
                                    <Text style={chatScreenStyles.emptyText}>{t("chat.emptyDescription")}</Text>
                                </View>
                            </View>
                        ) : null}

                        {error ? (
                            <View style={[chatScreenStyles.inlineErrorWrap, { bottom: composerOffset + spacing.sm }]}>
                                <Text style={chatScreenStyles.inlineError}>{error}</Text>
                            </View>
                        ) : null}

                        <View
                            style={[
                                chatScreenStyles.composerDock,
                                {
                                    paddingBottom: composerBottomInset,
                                },
                            ]}
                        >
                            {voiceStatusVisible ? (
                                <View style={chatScreenStyles.voiceStatusPill}>
                                    {voiceTranscribing ? (
                                        <ActivityIndicator color={colors.primary} size="small" />
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
                            <View style={chatScreenStyles.composerRow}>
                                <Pressable
                                    disabled={voiceRecording || voiceTranscribing}
                                    onPress={handleOpenAttachmentSheet}
                                    style={[
                                        chatScreenStyles.circleButton,
                                        voiceStatusVisible ? chatScreenStyles.sendButtonDisabled : null,
                                    ]}
                                >
                                    <AttachmentSvgIcon color="#12161A" height={28} width={28} />
                                </Pressable>

                                <View style={chatScreenStyles.composerInputWrap}>
                                    <TextInput
                                        editable={!voiceRecording && !voiceTranscribing}
                                        multiline
                                        onChangeText={setDraft}
                                        placeholder={voiceRecording ? t("chat.voiceRecording") : t("chat.inputPlaceholder")}
                                        placeholderTextColor={isDark ? "#9BB0BF" : "#8B9092"}
                                        style={chatScreenStyles.composerInput}
                                        textAlignVertical="top"
                                        value={draft}
                                    />
                                    <Pressable style={chatScreenStyles.stickerButton}>
                                        <Svg fill="none" height={24} viewBox="0 0 24 24" width={24}>
                                            <Path
                                                d="M12 3.8a8.2 8.2 0 1 0 8.2 8.2v0A8.2 8.2 0 0 0 12 3.8ZM8.8 11.6h.1m6.2 0h.1M8.5 15.2c.8 1 2 1.6 3.5 1.6s2.7-.6 3.5-1.6"
                                                stroke="#778085"
                                                strokeLinecap="round"
                                                strokeLinejoin="round"
                                                strokeWidth={1.8}
                                            />
                                        </Svg>
                                    </Pressable>
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
                    </View>
                </KeyboardAvoidingView>
                <AttachmentSheet
                    activeMode={attachmentMode}
                    albumSelectorVisible={albumSelectorVisible}
                    albums={photoAlbums}
                    bottomInset={bottomInset}
                    loadingPhotos={photoAssetsLoading}
                    onAddSelectedPhotos={() => {
                        void handleAddSelectedPhotos()
                    }}
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
                    onSelectPhotoAlbum={handleSelectPhotoAlbum}
                    onToggleAlbumSelector={handleToggleAlbumSelector}
                    onTogglePhoto={handleTogglePhoto}
                    cameraPreviewActive={cameraPreviewActive}
                    photoAssets={photoAssets}
                    photoPermissionDenied={photoPermissionDenied}
                    selectedPhotoAlbumId={selectedPhotoAlbumId}
                    selectedPhotoAlbumTitle={selectedPhotoAlbumTitle}
                    selectedPhotoIds={selectedPhotoIds}
                    visible={attachmentSheetVisible}
                />
            </View>
        </View>
    )
}
