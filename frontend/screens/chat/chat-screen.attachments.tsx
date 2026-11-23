import { ATTACHMENT_ICON_COLOR } from "@/screens/chat/chat-screen.constants"
import { AppActionSheet } from "@/components/platform/app-action-sheet"
import { getAuthTokens } from "@/services/auth/session"
import { useEffect, useState } from "react"
import {
    Image,
    Pressable,
    ScrollView,
    Text,
    View,
} from "react-native"
import Svg, { Path } from "react-native-svg"

import { useLanguage } from "@/providers/language-provider"
import type { AIAttachmentRead, UploadableChatAttachment } from "@/services/api/ai-chat.types"
import {
    getAttachmentDisplayName,
    getReadAttachmentDisplayName,
    getReadAttachmentUri,
    isImageAttachment,
    isUploadablePhotoAttachment,
    normalizeImageAspectRatio,
} from "@/screens/chat/chat-attachments"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useTheme } from "@/providers/theme-provider"

type AttachmentSheetProps = {
    allowFiles?: boolean
    onClose: () => void
    onOpenCamera: () => void
    onOpenNativeGallery: () => void
    onPickFiles: () => void
    visible: boolean
}

export function AttachmentSheet({ allowFiles = true, onClose, onOpenCamera, onOpenNativeGallery, onPickFiles, visible }: AttachmentSheetProps) {
    const { t } = useLanguage()
    return <AppActionSheet visible={visible} onClose={onClose} actions={[
        { id: "gallery", label: t("chat.attachmentsSelectGallery"), onPress: onOpenNativeGallery },
        { id: "camera", label: t("chat.attachmentsCameraTitle"), onPress: onOpenCamera },
        ...(allowFiles ? [{ id: "file", label: t("chat.attachmentsFileTitle"), onPress: onPickFiles }] : []),
    ]} />
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

        if (attachment.is_private) return () => { isMounted = false }
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
    }, [uri, attachment.is_private])

    return (
        <Image
            onLoad={(event) => {
                const source = event.nativeEvent.source
                setAspectRatio(normalizeImageAspectRatio(source.width, source.height))
            }}
            resizeMode="cover"
            source={{ uri, ...(attachment.is_private ? { headers: { Authorization: `Bearer ${getAuthTokens()?.accessToken ?? ""}` }, cache: "reload" as const } : {}) }}
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
