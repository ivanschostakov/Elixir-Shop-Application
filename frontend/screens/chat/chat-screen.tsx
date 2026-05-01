import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
    ActivityIndicator,
    Alert,
    Animated,
    Image,
    ImageBackground,
    Keyboard,
    KeyboardAvoidingView,
    Linking,
    Modal,
    Platform,
    Pressable,
    RefreshControl,
    ScrollView,
    type StyleProp,
    Text,
    TextInput,
    useWindowDimensions,
    View,
    type ViewStyle,
} from "react-native"
import * as Clipboard from "expo-clipboard"
import { CameraView, useCameraPermissions } from "expo-camera"
import {
    RecordingPresets,
    requestRecordingPermissionsAsync,
    setAudioModeAsync,
    useAudioRecorder,
    useAudioRecorderState,
} from "expo-audio"
import * as DocumentPicker from "expo-document-picker"
import * as ImagePicker from "expo-image-picker"
import * as MediaLibrary from "expo-media-library"
import { useRouter } from "expo-router"
import RenderHtml from "react-native-render-html"
import Svg, { Path } from "react-native-svg"

import AttachmentSvgIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import CameraSvgIcon from "@/assets/icons/chat/camera-svgrepo-com.svg"
import MicrophoneSvgIcon from "@/assets/icons/chat/microphone-alt-svgrepo-com.svg"
import { EdgeBlur } from "@/components/effects/edge-blur"
import { EmptyState } from "@/components/content/empty-state"
import { useApplyScreenTemplate } from "@/components/templates/screen-template.hooks"
import { ROUTES, getProductRoute } from "@/constants/routes"
import { useAiChat, type ChatDisplayMessage } from "@/hooks/chat/use-ai-chat"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { API_BASE_URL } from "@/services/api/constants"
import { transcribeMyAiChatVoice } from "@/services/api/ai-chat"
import type {
    AIAttachmentRead,
    AIInteractiveAction,
    AIInteractivePayload,
    AIInteractiveProductCard,
    UploadableChatAttachment,
} from "@/services/api/ai-chat.types"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { colors } from "@/theme/colors"
import { motion } from "@/theme/motion"
import { spacing } from "@/theme/spacing"
import { chatScreenStyles } from "./chat-screen.styles"

const CHAT_BACKGROUND_DARK = require("../../assets/images/chat/chat-background-dark.png")
const CHAT_BACKGROUND_LIGHT = require("../../assets/images/chat/chat-background-light.png")

type AttachmentMode = "photo" | "file"

const RECENT_PHOTO_LIMIT = 60
const ATTACHMENT_ICON_COLOR = "#1597DF"
const MESSAGE_IMAGE_MAX_WIDTH = 286
const MESSAGE_IMAGE_MIN_ASPECT_RATIO = 0.64
const MESSAGE_IMAGE_MAX_ASPECT_RATIO = 1.7
const CHAT_IMAGE_ATTACHMENT_EXTENSIONS = new Set(["gif", "heic", "heif", "jpeg", "jpg", "png", "webp"])
const DIRECT_ATTACHMENT_URI_PATTERN = /^(asset|content|data|file|http|https|ph):/i
const SAFE_LINK_PROTOCOL_PATTERN = /^(https?:\/\/|mailto:)/i
const INTERNAL_PRODUCT_LINK_PATTERN = /^\/products\/(\d+)(?:[/?#].*)?$/
const CHAT_RECORDING_AUDIO_MODE = {
    allowsRecording: true,
    interruptionMode: "doNotMix",
    playsInSilentMode: true,
    shouldPlayInBackground: false,
    shouldRouteThroughEarpiece: false,
} as const
const CHAT_IDLE_AUDIO_MODE = {
    ...CHAT_RECORDING_AUDIO_MODE,
    allowsRecording: false,
} as const

function AnimatedMessageBlock({ children }: { children: ReactNode }) {
    const progress = useRef(new Animated.Value(0)).current

    useEffect(() => {
        Animated.timing(progress, {
            duration: motion.duration.enter,
            easing: motion.easing.enter,
            toValue: 1,
            useNativeDriver: true,
        }).start()
    }, [progress])

    return (
        <Animated.View
            style={{
                opacity: progress,
                transform: [
                    {
                        translateY: progress.interpolate({
                            inputRange: [0, 1],
                            outputRange: [8, 0],
                        }),
                    },
                ],
            }}
        >
            {children}
        </Animated.View>
    )
}

function AiTypingBubble() {
    const dotProgressValues = useRef([
        new Animated.Value(0),
        new Animated.Value(0),
        new Animated.Value(0),
    ]).current

    useEffect(() => {
        const animations = dotProgressValues.map((dotProgress, dotIndex) =>
            Animated.loop(
                Animated.sequence([
                    Animated.delay(dotIndex * 120),
                    Animated.timing(dotProgress, {
                        duration: 320,
                        easing: motion.easing.standard,
                        toValue: 1,
                        useNativeDriver: true,
                    }),
                    Animated.timing(dotProgress, {
                        duration: 320,
                        easing: motion.easing.standard,
                        toValue: 0,
                        useNativeDriver: true,
                    }),
                    Animated.delay((2 - dotIndex) * 120),
                ]),
            ),
        )

        animations.forEach((animation) => animation.start())

        return () => {
            animations.forEach((animation) => animation.stop())
        }
    }, [dotProgressValues])

    return (
        <View style={[chatScreenStyles.messageBubble, chatScreenStyles.aiMessageBubble, chatScreenStyles.typingBubble]}>
            <View style={chatScreenStyles.typingDotsRow}>
                {dotProgressValues.map((dotProgress, dotIndex) => (
                    <Animated.View
                        key={dotIndex}
                        style={[
                            chatScreenStyles.typingDot,
                            {
                                opacity: dotProgress.interpolate({
                                    inputRange: [0, 1],
                                    outputRange: [0.35, 1],
                                }),
                                transform: [
                                    {
                                        translateY: dotProgress.interpolate({
                                            inputRange: [0, 1],
                                            outputRange: [0, -3],
                                        }),
                                    },
                                ],
                            },
                        ]}
                    />
                ))}
            </View>
        </View>
    )
}

function MessageMarkdown({
    hasImageAttachments,
    isUserMessage,
    markdown,
    onOpenLink,
    width,
}: {
    hasImageAttachments: boolean
    isUserMessage: boolean
    markdown: string
    onOpenLink?: (href: string) => void
    width: number
}) {
    const htmlSource = useMemo(() => ({ html: markdownToHtml(markdown) }), [markdown])
    const textColor = isUserMessage ? "#17311C" : "#15191E"
    const markdownWrapStyle = hasImageAttachments ? chatScreenStyles.messageMarkdownWithMedia : null
    const messageBaseStyle = {
        ...chatScreenStyles.messageText,
        ...chatScreenStyles.messageMarkdownBaseText,
        ...(isUserMessage ? chatScreenStyles.userMessageText : {}),
    }

    return (
        <View style={markdownWrapStyle}>
            <RenderHtml
                baseStyle={messageBaseStyle}
                contentWidth={width}
                enableExperimentalMarginCollapsing
                renderersProps={{
                    a: {
                        onPress: (_event, href) => {
                            if (!href) {
                                return
                            }
                            if (onOpenLink) {
                                onOpenLink(href)
                                return
                            }
                            if (SAFE_LINK_PROTOCOL_PATTERN.test(href)) {
                                void Linking.openURL(href).catch(() => undefined)
                            }
                        },
                    },
                }}
                source={htmlSource}
                tagsStyles={{
                    a: {
                        color: "#0A84FF",
                        textDecorationLine: "underline",
                    },
                    blockquote: {
                        borderLeftColor: "rgba(95,115,128,0.45)",
                        borderLeftWidth: 3,
                        marginBottom: 0,
                        marginTop: 0,
                        paddingLeft: 10,
                    },
                    code: {
                        backgroundColor: "rgba(34,39,46,0.12)",
                        borderRadius: 4,
                        color: textColor,
                        paddingHorizontal: 4,
                        paddingVertical: 1,
                    },
                    h1: {
                        color: textColor,
                        fontSize: 22,
                        fontWeight: "700",
                        lineHeight: 28,
                        marginBottom: 6,
                        marginTop: 0,
                    },
                    h2: {
                        color: textColor,
                        fontSize: 20,
                        fontWeight: "700",
                        lineHeight: 26,
                        marginBottom: 6,
                        marginTop: 0,
                    },
                    h3: {
                        color: textColor,
                        fontSize: 18,
                        fontWeight: "700",
                        lineHeight: 24,
                        marginBottom: 6,
                        marginTop: 0,
                    },
                    li: {
                        color: textColor,
                        lineHeight: 22,
                        marginBottom: 1,
                    },
                    ol: {
                        marginBottom: 0,
                        marginTop: 0,
                        paddingLeft: 18,
                    },
                    p: {
                        color: textColor,
                        lineHeight: 22,
                        marginBottom: 0,
                        marginTop: 0,
                    },
                    pre: {
                        backgroundColor: "rgba(34,39,46,0.12)",
                        borderRadius: 8,
                        color: textColor,
                        marginBottom: 0,
                        marginTop: 0,
                        paddingHorizontal: 9,
                        paddingVertical: 8,
                    },
                    strong: {
                        color: textColor,
                        fontWeight: "700",
                    },
                    ul: {
                        marginBottom: 0,
                        marginTop: 0,
                        paddingLeft: 18,
                    },
                }}
            />
        </View>
    )
}

function formatCommerceMoney(value: string | number, currency = "RUB") {
    const numericValue = Number(value)
    if (!Number.isFinite(numericValue)) {
        return `${value} ${currency}`.trim()
    }

    try {
        return new Intl.NumberFormat([], {
            currency,
            maximumFractionDigits: Number.isInteger(numericValue) ? 0 : 2,
            style: "currency",
        }).format(numericValue)
    } catch {
        return `${numericValue.toLocaleString()} ${currency}`.trim()
    }
}

function AIInteractiveContent({
    activeActionId,
    onActionPress,
    payload,
}: {
    activeActionId: string | null
    onActionPress: (action: AIInteractiveAction, quantity?: number) => void
    payload: AIInteractivePayload
}) {
    const hasContent = payload.cards.length > 0
    if (!hasContent) {
        return null
    }

    return (
        <View style={chatScreenStyles.aiInteractiveWrap}>
            {payload.cards.map((card) => (
                <AIProductCard
                    activeActionId={activeActionId}
                    card={card}
                    key={card.id}
                    onActionPress={onActionPress}
                />
            ))}
        </View>
    )
}

function AIProductCard({
    activeActionId,
    card,
    onActionPress,
}: {
    activeActionId: string | null
    card: AIInteractiveProductCard
    onActionPress: (action: AIInteractiveAction, quantity?: number) => void
}) {
    const visibleVariants = card.variants.slice(0, 2)
    const [actionQuantities, setActionQuantities] = useState<Record<string, number>>({})
    const actionsById = useMemo(() => new Map(card.actions.map((action) => [action.id, action])), [card.actions])
    const fallbackActionRows = useMemo(() => {
        const rows: { action_ids: string[] }[] = []
        for (let index = 0; index < card.actions.length; index += 2) {
            rows.push({ action_ids: card.actions.slice(index, index + 2).map((action) => action.id) })
        }
        return rows
    }, [card.actions])
    const actionRows = card.action_rows?.length ? card.action_rows : fallbackActionRows
    const getActionQuantity = (action: AIInteractiveAction) => actionQuantities[action.id] ?? action.quantity ?? 1
    const getActionMaxQuantity = (action: AIInteractiveAction) => {
        const variantStock = card.variants.find((variant) => variant.id === action.variant_id)?.stock
        return Math.max(1, Math.min(variantStock ?? 100, 100))
    }
    const updateActionQuantity = (action: AIInteractiveAction, nextQuantity: number) => {
        const maxQuantity = getActionMaxQuantity(action)
        setActionQuantities((currentQuantities) => ({
            ...currentQuantities,
            [action.id]: Math.max(1, Math.min(maxQuantity, nextQuantity)),
        }))
    }
    const renderActionControl = (action: AIInteractiveAction) => {
        if (action.type === "add_to_basket" && action.variant_id && !action.completed) {
            const selectedQuantity = getActionQuantity(action)
            return (
                <>
                    <AIQuantityStepper
                        max={getActionMaxQuantity(action)}
                        onChange={(nextQuantity) => updateActionQuantity(action, nextQuantity)}
                        value={selectedQuantity}
                    />
                    <AIActionButton
                        action={action}
                        activeActionId={activeActionId}
                        containerStyle={chatScreenStyles.aiKeyboardActionButton}
                        onPress={() => onActionPress(action, selectedQuantity)}
                    />
                </>
            )
        }

        return (
            <AIActionButton
                action={action}
                activeActionId={activeActionId}
                containerStyle={chatScreenStyles.aiKeyboardActionButton}
                onPress={() => onActionPress(action)}
            />
        )
    }

    return (
        <View style={chatScreenStyles.aiProductCard}>
            <View style={chatScreenStyles.aiProductHeader}>
                <Image source={{ uri: card.image_url }} style={chatScreenStyles.aiProductImage} />
                <View style={chatScreenStyles.aiProductTextWrap}>
                    <Text numberOfLines={2} style={chatScreenStyles.aiProductTitle}>
                        {card.title}
                    </Text>
                    {card.reason ? (
                        <Text numberOfLines={2} style={chatScreenStyles.aiProductReason}>
                            {card.reason}
                        </Text>
                    ) : null}
                </View>
            </View>
            {visibleVariants.length > 0 ? (
                <View style={chatScreenStyles.aiVariantList}>
                    {visibleVariants.map((variant) => (
                        <View key={variant.id} style={chatScreenStyles.aiVariantRow}>
                            <Text numberOfLines={1} style={chatScreenStyles.aiVariantName}>
                                {variant.name}
                            </Text>
                            <Text style={chatScreenStyles.aiVariantPrice}>
                                {formatCommerceMoney(variant.price)}
                            </Text>
                        </View>
                    ))}
                </View>
            ) : null}
            <View style={chatScreenStyles.aiActionKeyboard}>
                {actionRows.map((row, rowIndex) => {
                    const rowActions = row.action_ids
                        .map((actionId) => actionsById.get(actionId))
                        .filter((action): action is AIInteractiveAction => Boolean(action))
                    if (!rowActions.length) {
                        return null
                    }

                    return (
                        <View key={`${card.id}-row-${rowIndex}`} style={chatScreenStyles.aiActionKeyboardRow}>
                            {rowActions.map((action) => (
                                <View key={action.id} style={chatScreenStyles.aiActionKeyboardCell}>
                                    {renderActionControl(action)}
                                </View>
                            ))}
                        </View>
                    )
                })}
            </View>
        </View>
    )
}

function AIQuantityStepper({
    max,
    onChange,
    value,
}: {
    max: number
    onChange: (quantity: number) => void
    value: number
}) {
    const decreaseDisabled = value <= 1
    const increaseDisabled = value >= max

    return (
        <View style={chatScreenStyles.aiQuantityStepper}>
            <Pressable
                accessibilityRole="button"
                disabled={decreaseDisabled}
                onPress={() => onChange(value - 1)}
                style={[
                    chatScreenStyles.aiQuantityButton,
                    decreaseDisabled ? chatScreenStyles.aiQuantityButtonDisabled : null,
                ]}
            >
                <Text style={chatScreenStyles.aiQuantityButtonText}>-</Text>
            </Pressable>
            <Text style={chatScreenStyles.aiQuantityValue}>{value} шт.</Text>
            <Pressable
                accessibilityRole="button"
                disabled={increaseDisabled}
                onPress={() => onChange(value + 1)}
                style={[
                    chatScreenStyles.aiQuantityButton,
                    increaseDisabled ? chatScreenStyles.aiQuantityButtonDisabled : null,
                ]}
            >
                <Text style={chatScreenStyles.aiQuantityButtonText}>+</Text>
            </Pressable>
        </View>
    )
}

function AIActionButton({
    action,
    activeActionId,
    containerStyle,
    onPress,
}: {
    action: AIInteractiveAction
    activeActionId: string | null
    containerStyle?: StyleProp<ViewStyle>
    onPress: () => void
}) {
    const busy = activeActionId === action.id
    const disabled = busy || (action.type === "add_to_basket" && !action.action_token && !action.created_basket_item_id)
    const isPrimary = action.style === "primary" && !action.completed

    return (
        <Pressable
            accessibilityRole="button"
            disabled={disabled}
            onPress={onPress}
            style={({ pressed }) => [
                chatScreenStyles.aiActionButton,
                isPrimary ? chatScreenStyles.aiActionButtonPrimary : chatScreenStyles.aiActionButtonSecondary,
                containerStyle,
                disabled ? chatScreenStyles.aiActionButtonDisabled : null,
                pressed ? chatScreenStyles.aiActionButtonPressed : null,
            ]}
        >
            {busy ? (
                <ActivityIndicator color={isPrimary ? colors.onPrimary : colors.primary} size="small" />
            ) : (
                <Text
                    numberOfLines={2}
                    style={[
                        chatScreenStyles.aiActionButtonText,
                        isPrimary ? chatScreenStyles.aiActionButtonPrimaryText : null,
                    ]}
                >
                    {action.label}
                </Text>
            )}
        </Pressable>
    )
}

function SendActionButton({
    disabled,
    isDark,
    isActive,
    onPress,
    recording,
    sending,
    transcribing,
}: {
    disabled: boolean
    isDark: boolean
    isActive: boolean
    onPress: () => void
    recording: boolean
    sending: boolean
    transcribing: boolean
}) {
    const activeProgress = useRef(new Animated.Value(isActive ? 1 : 0)).current
    const busyProgress = useRef(new Animated.Value(sending || transcribing ? 1 : 0)).current
    const recordingProgress = useRef(new Animated.Value(recording ? 1 : 0)).current

    useEffect(() => {
        Animated.timing(activeProgress, {
            duration: motion.duration.standard,
            easing: motion.easing.standard,
            toValue: isActive ? 1 : 0,
            useNativeDriver: false,
        }).start()
    }, [activeProgress, isActive])

    useEffect(() => {
        Animated.timing(busyProgress, {
            duration: motion.duration.enter,
            easing: motion.easing.standard,
            toValue: sending || transcribing ? 1 : 0,
            useNativeDriver: true,
        }).start()
    }, [busyProgress, sending, transcribing])

    useEffect(() => {
        Animated.timing(recordingProgress, {
            duration: motion.duration.standard,
            easing: motion.easing.standard,
            toValue: recording ? 1 : 0,
            useNativeDriver: false,
        }).start()
    }, [recording, recordingProgress])

    const backgroundColor = activeProgress.interpolate({
        inputRange: [0, 1],
        outputRange: ["rgba(255,255,255,0.94)", "#37C960"],
    })
    const iconOpacity = busyProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [1, 0],
    })
    const spinnerOpacity = busyProgress
    const iconScale = recordingProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [1, 1.08],
    })
    const sendScale = activeProgress.interpolate({
        inputRange: [0, 1],
        outputRange: [1, 1.04],
    })

    return (
        <Pressable
            accessibilityLabel={isActive ? "Send message" : recording ? "Stop voice recording" : "Record voice message"}
            disabled={disabled}
            onPress={onPress}
            style={({ pressed }) => [
                chatScreenStyles.circleButtonPressable,
                pressed && chatScreenStyles.circleButtonPressed,
                disabled && chatScreenStyles.sendButtonDisabled,
            ]}
        >
            <Animated.View
                style={[
                    chatScreenStyles.circleButton,
                    {
                        backgroundColor,
                        transform: [{ scale: isActive ? sendScale : iconScale }],
                    },
                ]}
            >
                <Animated.View
                    pointerEvents="none"
                    style={[
                        chatScreenStyles.sendButtonRecordingLayer,
                        { opacity: recordingProgress },
                    ]}
                />
                <Animated.View style={[chatScreenStyles.sendButtonIconLayer, { opacity: iconOpacity }]}>
                    {isActive ? (
                        <Svg fill="none" height={22} viewBox="0 0 24 24" width={22}>
                            <Path
                                d="M4 20 21 12 4 4l3.5 8L4 20Z"
                                stroke={colors.onPrimary}
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={1.9}
                            />
                        </Svg>
                    ) : (
                        <MicrophoneSvgIcon
                            color={recording ? colors.onPrimary : isDark ? "#E8F0F6" : "#0E0E0E"}
                            height={24}
                            width={24}
                        />
                    )}
                </Animated.View>
                <Animated.View
                    pointerEvents="none"
                    style={[chatScreenStyles.sendButtonSpinnerLayer, { opacity: spinnerOpacity }]}
                >
                    <ActivityIndicator color={isActive ? colors.onPrimary : isDark ? "#E8F0F6" : "#151515"} />
                </Animated.View>
            </Animated.View>
        </Pressable>
    )
}

function AttachmentSheet({
    activeMode,
    albumSelectorVisible,
    albums,
    bottomInset,
    loadingPhotos,
    onAddSelectedPhotos,
    onClose,
    onOpenCamera,
    onOpenNativeGallery,
    onPickFiles,
    onSelectPhotoAlbum,
    onSelectMode,
    onTogglePhoto,
    onToggleAlbumSelector,
    photoAssets,
    photoPermissionDenied,
    cameraPreviewActive,
    selectedPhotoAlbumId,
    selectedPhotoAlbumTitle,
    selectedPhotoIds,
    visible,
}: {
    activeMode: AttachmentMode
    albumSelectorVisible: boolean
    albums: MediaLibrary.Album[]
    bottomInset: number
    loadingPhotos: boolean
    onAddSelectedPhotos: () => void
    onClose: () => void
    onOpenCamera: () => void
    onOpenNativeGallery: () => void
    onPickFiles: () => void
    onSelectPhotoAlbum: (albumId: string | null) => void
    onSelectMode: (mode: AttachmentMode) => void
    onTogglePhoto: (assetId: string) => void
    onToggleAlbumSelector: () => void
    photoAssets: MediaLibrary.Asset[]
    photoPermissionDenied: boolean
    cameraPreviewActive: boolean
    selectedPhotoAlbumId: string | null
    selectedPhotoAlbumTitle: string
    selectedPhotoIds: string[]
    visible: boolean
}) {
    const { t } = useLanguage()
    const { height, width } = useWindowDimensions()
    const selectedCount = selectedPhotoIds.length
    const tileSize = width / 3
    const sheetHeight = Math.min(height * 0.72, 620)
    const selectedPhotoSet = useMemo(() => new Set(selectedPhotoIds), [selectedPhotoIds])
    const bottomControlOffset = Math.max(bottomInset, spacing.sm)
    const bottomOverlayHeight = bottomControlOffset + 108

    return (
        <Modal
            animationType="fade"
            onRequestClose={onClose}
            statusBarTranslucent
            transparent
            visible={visible}
        >
            <View style={chatScreenStyles.attachmentModalRoot}>
                <Pressable onPress={onClose} style={chatScreenStyles.attachmentBackdrop} />
                <View
                    style={[
                        chatScreenStyles.attachmentSheet,
                        {
                            height: sheetHeight,
                            paddingBottom: Math.max(bottomInset, spacing.sm),
                        },
                    ]}
                >
                    <View style={chatScreenStyles.attachmentSheetHeader}>
                        <Pressable
                            accessibilityLabel={t("nav.closeSearch")}
                            onPress={onClose}
                            style={chatScreenStyles.attachmentHeaderButton}
                        >
                            <Svg fill="none" height={24} viewBox="0 0 24 24" width={24}>
                                <Path
                                    d="m6 6 12 12M18 6 6 18"
                                    stroke="#0A0A0A"
                                    strokeLinecap="round"
                                    strokeWidth={2.2}
                                />
                            </Svg>
                        </Pressable>

                        <Pressable
                            disabled={activeMode !== "photo"}
                            onPress={onToggleAlbumSelector}
                            style={chatScreenStyles.attachmentTitleButton}
                        >
                            <Text numberOfLines={1} style={chatScreenStyles.attachmentSheetTitle}>
                                {activeMode === "photo" ? selectedPhotoAlbumTitle : t("chat.attachmentsFileTitle")}
                            </Text>
                            {activeMode === "photo" ? (
                                <Svg fill="none" height={18} viewBox="0 0 24 24" width={18}>
                                    <Path
                                        d="m7 10 5 5 5-5"
                                        stroke="#111"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2.2}
                                    />
                                </Svg>
                            ) : null}
                        </Pressable>

                        {activeMode === "photo" && selectedCount > 0 ? (
                            <Pressable onPress={onAddSelectedPhotos} style={chatScreenStyles.attachmentAddButton}>
                                <Text style={chatScreenStyles.attachmentAddButtonText}>
                                    {t("chat.attachmentsAddSelected").replace("{count}", String(selectedCount))}
                                </Text>
                            </Pressable>
                        ) : (
                            <View style={chatScreenStyles.attachmentHeaderSpacer} />
                        )}
                    </View>
                    <View style={chatScreenStyles.attachmentHandle} />

                    <View style={chatScreenStyles.attachmentSheetBody}>
                        {activeMode === "photo" ? (
                            <View style={chatScreenStyles.photoSheetBody}>
                                {loadingPhotos ? (
                                    <View style={chatScreenStyles.attachmentLoadingWrap}>
                                        <ActivityIndicator color={colors.primary} />
                                    </View>
                                ) : photoPermissionDenied ? (
                                    <View style={chatScreenStyles.attachmentPermissionWrap}>
                                        <Text style={chatScreenStyles.attachmentPermissionTitle}>
                                            {t("chat.attachmentsPhotoPermissionTitle")}
                                        </Text>
                                        <Text style={chatScreenStyles.attachmentPermissionText}>
                                            {t("chat.attachmentsPhotoPermissionMessage")}
                                        </Text>
                                        <Pressable
                                            onPress={onOpenNativeGallery}
                                            style={chatScreenStyles.attachmentPermissionButton}
                                        >
                                            <Text style={chatScreenStyles.attachmentPermissionButtonText}>
                                                {t("chat.attachmentsSelectGallery")}
                                            </Text>
                                        </Pressable>
                                    </View>
                                ) : photoAssets.length > 0 ? (
                                    <PhotoGalleryGrid
                                        bottomOverlayHeight={bottomOverlayHeight}
                                        cameraPreviewActive={cameraPreviewActive}
                                        onOpenCamera={onOpenCamera}
                                        onTogglePhoto={onTogglePhoto}
                                        photoAssets={photoAssets}
                                        selectedPhotoIds={selectedPhotoIds}
                                        selectedPhotoSet={selectedPhotoSet}
                                        tileSize={tileSize}
                                    />
                                ) : (
                                    <View style={chatScreenStyles.attachmentPermissionWrap}>
                                        <Text style={chatScreenStyles.attachmentPermissionTitle}>
                                            {t("chat.attachmentsNoPhotosTitle")}
                                        </Text>
                                        <Pressable
                                            onPress={onOpenNativeGallery}
                                            style={chatScreenStyles.attachmentPermissionButton}
                                        >
                                            <Text style={chatScreenStyles.attachmentPermissionButtonText}>
                                                {t("chat.attachmentsSelectGallery")}
                                            </Text>
                                        </Pressable>
                                    </View>
                                )}
                            </View>
                        ) : (
                            <View style={chatScreenStyles.fileSheetBody}>
                                <View style={chatScreenStyles.attachmentActionCard}>
                                    <Pressable
                                        onPress={onOpenNativeGallery}
                                        style={chatScreenStyles.attachmentActionRow}
                                    >
                                        <GalleryActionIcon />
                                        <Text style={chatScreenStyles.attachmentActionText}>
                                            {t("chat.attachmentsSelectGallery")}
                                        </Text>
                                    </Pressable>
                                    <View style={chatScreenStyles.attachmentActionDivider} />
                                    <Pressable onPress={onPickFiles} style={chatScreenStyles.attachmentActionRow}>
                                        <FileActionIcon />
                                        <Text style={chatScreenStyles.attachmentActionText}>
                                            {t("chat.attachmentsSelectFiles")}
                                        </Text>
                                    </Pressable>
                                </View>
                            </View>
                        )}
                    </View>

                    {activeMode === "photo" && albumSelectorVisible ? (
                        <AlbumSelector
                            albums={albums}
                            onSelectAlbum={onSelectPhotoAlbum}
                            selectedPhotoAlbumId={selectedPhotoAlbumId}
                        />
                    ) : null}

                    <View style={[chatScreenStyles.attachmentModeBar, { bottom: bottomControlOffset }]}>
                        <AttachmentModeButton
                            active={activeMode === "photo"}
                            icon={<GalleryActionIcon active={activeMode === "photo"} compact />}
                            label={t("chat.attachmentsPhotoTab")}
                            onPress={() => onSelectMode("photo")}
                        />
                        <AttachmentModeButton
                            active={activeMode === "file"}
                            icon={<FileActionIcon active={activeMode === "file"} compact />}
                            label={t("chat.attachmentsFileTab")}
                            onPress={() => onSelectMode("file")}
                        />
                    </View>
                </View>
            </View>
        </Modal>
    )
}

function PhotoGalleryGrid({
    bottomOverlayHeight,
    cameraPreviewActive,
    onOpenCamera,
    onTogglePhoto,
    photoAssets,
    selectedPhotoIds,
    selectedPhotoSet,
    tileSize,
}: {
    bottomOverlayHeight: number
    cameraPreviewActive: boolean
    onOpenCamera: () => void
    onTogglePhoto: (assetId: string) => void
    photoAssets: MediaLibrary.Asset[]
    selectedPhotoIds: string[]
    selectedPhotoSet: Set<string>
    tileSize: number
}) {
    const heroAssets = photoAssets.slice(0, 4)
    const remainingAssets = photoAssets.slice(4)

    return (
        <ScrollView
            contentContainerStyle={[
                chatScreenStyles.photoGridContent,
                { paddingBottom: bottomOverlayHeight },
            ]}
            scrollIndicatorInsets={{ bottom: bottomOverlayHeight }}
            showsVerticalScrollIndicator={false}
            style={chatScreenStyles.photoGrid}
        >
            <View style={chatScreenStyles.photoGridHeroRow}>
                <Pressable
                    accessibilityLabel="Open camera"
                    onPress={onOpenCamera}
                    style={[
                        chatScreenStyles.cameraTile,
                        { height: tileSize * 2, width: tileSize },
                    ]}
                >
                    {cameraPreviewActive ? (
                        <CameraView
                            animateShutter={false}
                            facing="back"
                            style={chatScreenStyles.cameraTilePreview}
                        />
                    ) : null}
                    <View style={chatScreenStyles.cameraTileScrim} />
                    <View style={chatScreenStyles.cameraTileIcon}>
                        <CameraSvgIcon height={44} width={44} />
                    </View>
                </Pressable>
                <View style={[chatScreenStyles.photoGridHeroPhotos, { width: tileSize * 2 }]}>
                    {heroAssets.map((item) => (
                        <PhotoGridTile
                            item={item}
                            key={item.id}
                            onTogglePhoto={onTogglePhoto}
                            selectedIndex={selectedPhotoIds.indexOf(item.id)}
                            selectedPhotoSet={selectedPhotoSet}
                            tileSize={tileSize}
                        />
                    ))}
                </View>
            </View>
            <View style={chatScreenStyles.photoGridWrap}>
                {remainingAssets.map((item) => (
                    <PhotoGridTile
                        item={item}
                        key={item.id}
                        onTogglePhoto={onTogglePhoto}
                        selectedIndex={selectedPhotoIds.indexOf(item.id)}
                        selectedPhotoSet={selectedPhotoSet}
                        tileSize={tileSize}
                    />
                ))}
            </View>
        </ScrollView>
    )
}

function PhotoGridTile({
    item,
    onTogglePhoto,
    selectedIndex,
    selectedPhotoSet,
    tileSize,
}: {
    item: MediaLibrary.Asset
    onTogglePhoto: (assetId: string) => void
    selectedIndex: number
    selectedPhotoSet: Set<string>
    tileSize: number
}) {
    const isSelected = selectedPhotoSet.has(item.id)

    return (
        <Pressable
            onPress={() => onTogglePhoto(item.id)}
            style={[
                chatScreenStyles.photoTile,
                { height: tileSize, width: tileSize },
            ]}
        >
            <Image source={{ uri: item.uri }} style={chatScreenStyles.photoTileImage} />
            <View
                style={[
                    chatScreenStyles.photoSelectionCircle,
                    isSelected ? chatScreenStyles.photoSelectionCircleActive : null,
                ]}
            >
                {isSelected ? (
                    <Text style={chatScreenStyles.photoSelectionText}>
                        {selectedIndex + 1}
                    </Text>
                ) : null}
            </View>
        </Pressable>
    )
}

function AlbumSelector({
    albums,
    onSelectAlbum,
    selectedPhotoAlbumId,
}: {
    albums: MediaLibrary.Album[]
    onSelectAlbum: (albumId: string | null) => void
    selectedPhotoAlbumId: string | null
}) {
    const { t } = useLanguage()

    return (
        <View style={chatScreenStyles.albumSelectorPopover}>
            <ScrollView showsVerticalScrollIndicator={false}>
                <Pressable
                    onPress={() => onSelectAlbum(null)}
                    style={[
                        chatScreenStyles.albumSelectorRow,
                        selectedPhotoAlbumId === null ? chatScreenStyles.albumSelectorRowActive : null,
                    ]}
                >
                    <Text
                        numberOfLines={1}
                        style={[
                            chatScreenStyles.albumSelectorText,
                            selectedPhotoAlbumId === null ? chatScreenStyles.albumSelectorTextActive : null,
                        ]}
                    >
                        {t("chat.attachmentsPhotoTitle")}
                    </Text>
                </Pressable>
                {albums.map((album) => (
                    <Pressable
                        key={album.id}
                        onPress={() => onSelectAlbum(album.id)}
                        style={[
                            chatScreenStyles.albumSelectorRow,
                            selectedPhotoAlbumId === album.id ? chatScreenStyles.albumSelectorRowActive : null,
                        ]}
                    >
                        <Text
                            numberOfLines={1}
                            style={[
                                chatScreenStyles.albumSelectorText,
                                selectedPhotoAlbumId === album.id ? chatScreenStyles.albumSelectorTextActive : null,
                            ]}
                        >
                            {album.title}
                        </Text>
                        <Text style={chatScreenStyles.albumSelectorCount}>{album.assetCount}</Text>
                    </Pressable>
                ))}
            </ScrollView>
        </View>
    )
}

function AttachmentModeButton({
    active,
    icon,
    label,
    onPress,
}: {
    active: boolean
    icon: ReactNode
    label: string
    onPress: () => void
}) {
    return (
        <Pressable
            onPress={onPress}
            style={[
                chatScreenStyles.attachmentModeButton,
                active ? chatScreenStyles.attachmentModeButtonActive : null,
            ]}
        >
            {icon}
            <Text
                style={[
                    chatScreenStyles.attachmentModeLabel,
                    active ? chatScreenStyles.attachmentModeLabelActive : null,
                ]}
            >
                {label}
            </Text>
        </Pressable>
    )
}

function QueuedAttachmentStrip({
    attachments,
    onRemove,
}: {
    attachments: UploadableChatAttachment[]
    onRemove: (attachmentIndex: number) => void
}) {
    if (!attachments.length) {
        return null
    }

    return (
        <ScrollView
            contentContainerStyle={chatScreenStyles.queuedAttachmentContent}
            horizontal
            showsHorizontalScrollIndicator={false}
            style={chatScreenStyles.queuedAttachmentScroll}
        >
            {attachments.map((attachment, attachmentIndex) => {
                const isImage = isUploadablePhotoAttachment(attachment)

                return (
                    <View key={`${attachment.uri}-${attachmentIndex}`} style={chatScreenStyles.queuedAttachmentChip}>
                        {isImage ? (
                            <Image
                                resizeMode="cover"
                                source={{ uri: attachment.uri }}
                                style={chatScreenStyles.queuedAttachmentThumbnail}
                            />
                        ) : (
                            <View style={chatScreenStyles.queuedAttachmentIcon}>
                                <FileActionIcon compact />
                            </View>
                        )}
                        <Text numberOfLines={1} style={chatScreenStyles.queuedAttachmentName}>
                            {getAttachmentDisplayName(attachment)}
                        </Text>
                        <Pressable
                            onPress={() => onRemove(attachmentIndex)}
                            style={chatScreenStyles.queuedAttachmentRemove}
                        >
                            <Svg fill="none" height={15} viewBox="0 0 24 24" width={15}>
                                <Path
                                    d="m7 7 10 10M17 7 7 17"
                                    stroke="#0A0A0A"
                                    strokeLinecap="round"
                                    strokeWidth={2.2}
                                />
                            </Svg>
                        </Pressable>
                    </View>
                )
            })}
        </ScrollView>
    )
}

function MessageAttachmentList({
    attachments,
    isUserMessage,
    mediaWidth,
}: {
    attachments: AIAttachmentRead[]
    isUserMessage: boolean
    mediaWidth: number
}) {
    const imageAttachments = attachments.filter(isImageAttachment)
    const documentAttachments = attachments.filter((attachment) => !isImageAttachment(attachment))

    if (!imageAttachments.length && !documentAttachments.length) {
        return null
    }

    return (
        <View style={chatScreenStyles.messageAttachmentStack}>
            {imageAttachments.length > 0 ? (
                <View style={chatScreenStyles.messageImageStack}>
                    {imageAttachments.map((attachment) => (
                        <MessageImageAttachment
                            attachment={attachment}
                            key={attachment.id}
                            mediaWidth={mediaWidth}
                        />
                    ))}
                </View>
            ) : null}
            {documentAttachments.length > 0 ? (
                <View style={chatScreenStyles.messageDocumentStack}>
                    {documentAttachments.map((attachment) => (
                        <View
                            key={attachment.id}
                            style={[
                                chatScreenStyles.messageDocumentAttachment,
                                isUserMessage ? chatScreenStyles.userMessageDocumentAttachment : null,
                            ]}
                        >
                            <View style={chatScreenStyles.messageDocumentIcon}>
                                <FileActionIcon compact />
                            </View>
                            <Text
                                numberOfLines={2}
                                style={[
                                    chatScreenStyles.messageDocumentName,
                                    isUserMessage ? chatScreenStyles.userMessageDocumentName : null,
                                ]}
                            >
                                {getReadAttachmentDisplayName(attachment)}
                            </Text>
                        </View>
                    ))}
                </View>
            ) : null}
        </View>
    )
}

function MessageImageAttachment({
    attachment,
    mediaWidth,
}: {
    attachment: AIAttachmentRead
    mediaWidth: number
}) {
    const uri = getReadAttachmentUri(attachment)
    const [aspectRatio, setAspectRatio] = useState(1)

    useEffect(() => {
        let isMounted = true

        Image.getSize(
            uri,
            (imageWidth, imageHeight) => {
                if (isMounted) {
                    setAspectRatio(normalizeImageAspectRatio(imageWidth, imageHeight))
                }
            },
            () => undefined,
        )

        return () => {
            isMounted = false
        }
    }, [uri])

    return (
        <Image
            onLoad={(event) => {
                const source = event.nativeEvent.source
                setAspectRatio(normalizeImageAspectRatio(source.width, source.height))
            }}
            resizeMode="cover"
            source={{ uri }}
            style={[
                chatScreenStyles.messageImageAttachment,
                {
                    aspectRatio,
                    width: mediaWidth,
                },
            ]}
        />
    )
}

function GalleryActionIcon({ active = false, compact = false }: { active?: boolean; compact?: boolean }) {
    const iconColor = active ? colors.primary : ATTACHMENT_ICON_COLOR
    const size = compact ? 22 : 30

    return (
        <Svg fill="none" height={size} viewBox="0 0 24 24" width={size}>
            <Path
                d="M4.5 7.2A2.7 2.7 0 0 1 7.2 4.5h9.6a2.7 2.7 0 0 1 2.7 2.7v9.6a2.7 2.7 0 0 1-2.7 2.7H7.2a2.7 2.7 0 0 1-2.7-2.7V7.2Z"
                stroke={iconColor}
                strokeLinejoin="round"
                strokeWidth={1.8}
            />
            <Path
                d="m5.1 16.6 3.7-3.8 2.6 2.4 3.5-4.1 4 4.8M9.1 8.6h.1"
                stroke={iconColor}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.8}
            />
        </Svg>
    )
}

function FileActionIcon({ active = false, compact = false }: { active?: boolean; compact?: boolean }) {
    const iconColor = active ? colors.primary : ATTACHMENT_ICON_COLOR
    const size = compact ? 22 : 30

    return (
        <Svg fill="none" height={size} viewBox="0 0 24 24" width={size}>
            <Path
                d="M7 3.8h6.2L18 8.6v11.6H7V3.8Z"
                stroke={iconColor}
                strokeLinejoin="round"
                strokeWidth={1.8}
            />
            <Path
                d="M13 4v5h5M9.5 13h5M9.5 16h5"
                stroke={iconColor}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.8}
            />
        </Svg>
    )
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
    const cameraPreviewActive =
        attachmentSheetVisible &&
        attachmentMode === "photo" &&
        cameraPermission?.granted === true
    const selectedPhotoAlbumTitle = useMemo(
        () => photoAlbums.find((album) => album.id === selectedPhotoAlbumId)?.title ?? t("chat.attachmentsPhotoTitle"),
        [photoAlbums, selectedPhotoAlbumId, t],
    )

    useApplyScreenTemplate("feed", {
        header: "none",
        footer: "none",
        mode: "fullscreen",
    })

    useEffect(() => {
        if (!messages.length && !aiTyping) {
            return
        }

        const animationFrameId = requestAnimationFrame(() => {
            scrollRef.current?.scrollToEnd({ animated: true })
        })

        return () => {
            cancelAnimationFrame(animationFrameId)
        }
    }, [aiTyping, messages.length])

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
                                stroke={isDark ? "#E7EEF5" : "#0A0A0A"}
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
                                                            onActionPress={(action, quantity) => {
                                                                void handleInteractiveAction(message, action, quantity)
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
                                    <AttachmentSvgIcon color={isDark ? "#E8F0F6" : "#0E0E0E"} height={28} width={28} />
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

function markdownToHtml(markdown: string) {
    const normalizedMarkdown = markdown.replace(/\r\n/g, "\n").trim()
    if (!normalizedMarkdown) {
        return ""
    }

    const htmlParts: string[] = []
    const paragraphLines: string[] = []
    const codeBlockLines: string[] = []
    const listItems: string[] = []
    let listType: "ol" | "ul" | null = null
    let insideCodeBlock = false

    const flushParagraph = () => {
        if (!paragraphLines.length) {
            return
        }
        const paragraphHtml = renderInlineMarkdown(paragraphLines.join("\n")).replace(/\n/g, "<br />")
        htmlParts.push(`<p>${paragraphHtml}</p>`)
        paragraphLines.length = 0
    }

    const flushList = () => {
        if (!listType || !listItems.length) {
            return
        }
        htmlParts.push(`<${listType}>${listItems.join("")}</${listType}>`)
        listItems.length = 0
        listType = null
    }

    const flushCodeBlock = () => {
        if (!insideCodeBlock) {
            return
        }
        const codeHtml = escapeHtml(codeBlockLines.join("\n"))
        htmlParts.push(`<pre><code>${codeHtml}</code></pre>`)
        codeBlockLines.length = 0
        insideCodeBlock = false
    }

    for (const line of normalizedMarkdown.split("\n")) {
        const trimmedLine = line.trim()

        if (trimmedLine.startsWith("```")) {
            flushParagraph()
            flushList()
            if (insideCodeBlock) {
                flushCodeBlock()
            } else {
                insideCodeBlock = true
                codeBlockLines.length = 0
            }
            continue
        }

        if (insideCodeBlock) {
            codeBlockLines.push(line)
            continue
        }

        if (!trimmedLine) {
            flushParagraph()
            flushList()
            continue
        }

        const headingMatch = trimmedLine.match(/^(#{1,6})\s+(.*)$/)
        if (headingMatch) {
            flushParagraph()
            flushList()
            const headingLevel = headingMatch[1].length
            htmlParts.push(`<h${headingLevel}>${renderInlineMarkdown(headingMatch[2])}</h${headingLevel}>`)
            continue
        }

        const orderedItemMatch = trimmedLine.match(/^\d+\.\s+(.*)$/)
        if (orderedItemMatch) {
            flushParagraph()
            if (listType && listType !== "ol") {
                flushList()
            }
            listType = "ol"
            listItems.push(`<li>${renderInlineMarkdown(orderedItemMatch[1])}</li>`)
            continue
        }

        const unorderedItemMatch = trimmedLine.match(/^[-*]\s+(.*)$/)
        if (unorderedItemMatch) {
            flushParagraph()
            if (listType && listType !== "ul") {
                flushList()
            }
            listType = "ul"
            listItems.push(`<li>${renderInlineMarkdown(unorderedItemMatch[1])}</li>`)
            continue
        }

        const quoteMatch = trimmedLine.match(/^>\s?(.*)$/)
        if (quoteMatch) {
            flushParagraph()
            flushList()
            htmlParts.push(`<blockquote><p>${renderInlineMarkdown(quoteMatch[1])}</p></blockquote>`)
            continue
        }

        paragraphLines.push(line)
    }

    flushParagraph()
    flushList()
    flushCodeBlock()

    return htmlParts.join("")
}

function renderInlineMarkdown(text: string) {
    const codeFragments: string[] = []
    let html = escapeHtml(text)

    html = html.replace(/`([^`\n]+)`/g, (_match, code) => {
        const token = `__CHAT_CODE_${codeFragments.length}__`
        codeFragments.push(`<code>${code}</code>`)
        return token
    })

    html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_match, label, href) => {
        const escapedLabel = label.trim() ? label.trim() : href
        const safeHref = escapeHtml(href)
        return `<a href="${safeHref}">${escapedLabel}</a>`
    })

    html = html.replace(/\*\*\*([^*]+)\*\*\*/g, "<strong><em>$1</em></strong>")
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>")
    html = html.replace(/~~([^~]+)~~/g, "<s>$1</s>")
    html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>")
    html = html.replace(/_([^_]+)_/g, "<em>$1</em>")

    for (let codeIndex = 0; codeIndex < codeFragments.length; codeIndex += 1) {
        html = html.split(`__CHAT_CODE_${codeIndex}__`).join(codeFragments[codeIndex])
    }

    return html
}

function escapeHtml(value: string) {
    return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;")
}

function createAttachmentFromImagePickerAsset(asset: ImagePicker.ImagePickerAsset): UploadableChatAttachment {
    return {
        fileName: asset.fileName ?? getFileNameFromUri(asset.uri, "photo.jpg"),
        mimeType: asset.mimeType ?? guessMimeTypeFromFilename(asset.fileName ?? asset.uri, "image/jpeg"),
        uri: asset.uri,
    }
}

async function createAttachmentFromMediaAsset(asset: MediaLibrary.Asset): Promise<UploadableChatAttachment> {
    const assetInfo = await MediaLibrary.getAssetInfoAsync(asset)
    const uri = assetInfo.localUri ?? assetInfo.uri ?? asset.uri

    return {
        fileName: assetInfo.filename ?? asset.filename ?? getFileNameFromUri(uri, "photo.jpg"),
        mimeType: guessMimeTypeFromFilename(assetInfo.filename ?? asset.filename, "image/jpeg"),
        uri,
    }
}

function getAttachmentDisplayName(attachment: UploadableChatAttachment) {
    return attachment.fileName ?? getFileNameFromUri(attachment.uri, "attachment")
}

function getReadAttachmentDisplayName(attachment: AIAttachmentRead) {
    return attachment.original_filename || attachment.filename || "attachment"
}

function isUploadablePhotoAttachment(attachment: UploadableChatAttachment) {
    if (attachment.mimeType?.toLowerCase().startsWith("image/")) {
        return true
    }
    return CHAT_IMAGE_ATTACHMENT_EXTENSIONS.has(getAttachmentExtension(attachment.fileName ?? attachment.uri))
}

function isImageAttachment(attachment: AIAttachmentRead) {
    if (attachment.type === "image" || attachment.mime_type?.toLowerCase().startsWith("image/")) {
        return true
    }
    return CHAT_IMAGE_ATTACHMENT_EXTENSIONS.has(
        getAttachmentExtension(attachment.original_filename || attachment.filename || String(attachment.relative_path)),
    )
}

function getReadAttachmentUri(attachment: AIAttachmentRead) {
    const rawPath = String(attachment.relative_path || "")

    if (DIRECT_ATTACHMENT_URI_PATTERN.test(rawPath)) {
        return rawPath
    }

    const normalizedPath = rawPath.replace(/^\/+/, "")
    const mediaPath = normalizedPath.startsWith("media/")
        ? normalizedPath
        : `media/attachments/${normalizedPath}`

    return `${getApiMediaBaseUrl()}/${encodePathSegments(mediaPath)}`
}

function getApiMediaBaseUrl() {
    const normalizedApiBaseUrl = API_BASE_URL.replace(/\/+$/, "")
    return normalizedApiBaseUrl.endsWith("/api")
        ? normalizedApiBaseUrl.slice(0, -4)
        : normalizedApiBaseUrl
}

function encodePathSegments(path: string) {
    return path
        .split("/")
        .filter(Boolean)
        .map((segment) => encodeURIComponent(segment))
        .join("/")
}

function normalizeImageAspectRatio(width: number | undefined, height: number | undefined) {
    if (!width || !height) {
        return 1
    }

    const ratio = width / height
    return Math.min(MESSAGE_IMAGE_MAX_ASPECT_RATIO, Math.max(MESSAGE_IMAGE_MIN_ASPECT_RATIO, ratio))
}

function formatVoiceDuration(durationMillis: number) {
    const totalSeconds = Math.max(0, Math.floor(durationMillis / 1000))
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}:${seconds.toString().padStart(2, "0")}`
}

function getAttachmentExtension(value: string | null | undefined) {
    const cleanValue = (value || "").split("?")[0] ?? ""
    return cleanValue.split(".").pop()?.toLowerCase() || ""
}

function getVoiceRecordingFilename(uri: string) {
    const fallbackFilename = Platform.OS === "web" ? "voice.webm" : "voice.m4a"
    const filename = getFileNameFromUri(uri, fallbackFilename)

    if (getAttachmentExtension(filename)) {
        return filename
    }

    return fallbackFilename
}

function getVoiceRecordingMimeType(uri: string) {
    const extension = getAttachmentExtension(uri)
    const mimeTypesByExtension: Record<string, string> = {
        "3gp": "audio/3gpp",
        aac: "audio/aac",
        caf: "audio/x-caf",
        m4a: "audio/m4a",
        mp3: "audio/mpeg",
        mp4: "audio/mp4",
        wav: "audio/wav",
        webm: "audio/webm",
    }

    return mimeTypesByExtension[extension] ?? (Platform.OS === "web" ? "audio/webm" : "audio/m4a")
}

function getFileNameFromUri(uri: string, fallbackFilename: string) {
    const cleanUri = uri.split("?")[0] ?? uri
    const filename = cleanUri.split("/").filter(Boolean).pop()
    return filename || fallbackFilename
}

function guessMimeTypeFromFilename(filename: string | null | undefined, fallbackMimeType: string) {
    if (!filename) {
        return fallbackMimeType
    }

    const extension = filename.split(".").pop()?.toLowerCase()
    if (!extension) {
        return fallbackMimeType
    }

    const mimeTypesByExtension: Record<string, string> = {
        gif: "image/gif",
        heic: "image/heic",
        heif: "image/heif",
        jpeg: "image/jpeg",
        jpg: "image/jpeg",
        png: "image/png",
        webp: "image/webp",
    }

    return mimeTypesByExtension[extension] ?? fallbackMimeType
}
