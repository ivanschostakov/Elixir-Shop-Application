import { useEffect, useState, type ReactNode } from "react"
import {
    Image,
    Modal,
    Pressable,
    ScrollView,
    Text,
    useWindowDimensions,
    View,
} from "react-native"
import Svg, { Path } from "react-native-svg"

import { useLanguage } from "@/providers/language-provider"
import { spacing } from "@/theme/spacing"
import type { AIAttachmentRead, UploadableChatAttachment } from "@/services/api/ai-chat.types"
import {
    getAttachmentDisplayName,
    getReadAttachmentDisplayName,
    getReadAttachmentUri,
    isImageAttachment,
    isUploadablePhotoAttachment,
    normalizeImageAspectRatio,
} from "@/screens/chat/chat-attachments"
import { ATTACHMENT_ICON_COLOR, type AttachmentMode } from "@/screens/chat/chat-screen.constants"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"
import CameraSvgIcon from "@/assets/icons/chat/camera-svgrepo-com.svg"

type AttachmentSheetProps = {
    activeMode: AttachmentMode
    bottomInset: number
    onClose: () => void
    onOpenCamera: () => void
    onOpenNativeGallery: () => void
    onPickFiles: () => void
    onSelectMode: (mode: AttachmentMode) => void
    visible: boolean
}

export function AttachmentSheet({
    activeMode,
    bottomInset,
    onClose,
    onOpenCamera,
    onOpenNativeGallery,
    onPickFiles,
    onSelectMode,
    visible,
}: AttachmentSheetProps) {
    const chatScreenStyles = useThemeStyles(createChatScreenStyles)
    const { t } = useLanguage()
    const { height } = useWindowDimensions()
    const sheetHeight = Math.min(height * 0.72, 620)
    const bottomControlOffset = Math.max(bottomInset, spacing.sm)

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

                        <View style={chatScreenStyles.attachmentTitleButton}>
                            <Text numberOfLines={1} style={chatScreenStyles.attachmentSheetTitle}>
                                {activeMode === "photo" ? t("chat.attachmentsPhotoTitle") : t("chat.attachmentsFileTitle")}
                            </Text>
                        </View>

                        <View style={chatScreenStyles.attachmentHeaderSpacer} />
                    </View>
                    <View style={chatScreenStyles.attachmentHandle} />

                    <View style={chatScreenStyles.attachmentSheetBody}>
                        {activeMode === "photo" ? (
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
                                    <Pressable onPress={onOpenCamera} style={chatScreenStyles.attachmentActionRow}>
                                        <CameraActionIcon />
                                        <Text style={chatScreenStyles.attachmentActionText}>
                                            {t("chat.attachmentsCameraTitle")}
                                        </Text>
                                    </Pressable>
                                </View>
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
    const chatScreenStyles = useThemeStyles(createChatScreenStyles)
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

export function QueuedAttachmentStrip({
    attachments,
    onRemove,
}: {
    attachments: UploadableChatAttachment[]
    onRemove: (attachmentIndex: number) => void
}) {
    const chatScreenStyles = useThemeStyles(createChatScreenStyles)
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

export function MessageAttachmentList({
    attachments,
    isUserMessage,
    mediaWidth,
}: {
    attachments: AIAttachmentRead[]
    isUserMessage: boolean
    mediaWidth: number
}) {
    const chatScreenStyles = useThemeStyles(createChatScreenStyles)
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
    const chatScreenStyles = useThemeStyles(createChatScreenStyles)
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
    const { palette } = useTheme()
    const iconColor = active ? palette.primary : ATTACHMENT_ICON_COLOR
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

function CameraActionIcon({ active = false, compact = false }: { active?: boolean; compact?: boolean }) {
    const { palette } = useTheme()
    const iconColor = active ? palette.primary : ATTACHMENT_ICON_COLOR
    const size = compact ? 22 : 30

    return <CameraSvgIcon color={iconColor} height={size} width={size} />
}

function FileActionIcon({ active = false, compact = false }: { active?: boolean; compact?: boolean }) {
    const { palette } = useTheme()
    const iconColor = active ? palette.primary : ATTACHMENT_ICON_COLOR
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
