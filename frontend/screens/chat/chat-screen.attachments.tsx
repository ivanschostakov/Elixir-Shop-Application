import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
    ActivityIndicator,
    Image,
    Modal,
    Pressable,
    ScrollView,
    Text,
    useWindowDimensions,
    View,
} from "react-native"
import { CameraView } from "expo-camera"
import Svg, { Path } from "react-native-svg"
import * as MediaLibrary from "expo-media-library"

import { useLanguage } from "@/providers/language-provider"
import { colors } from "@/theme/colors"
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
import { chatScreenStyles } from "@/screens/chat/chat-screen.styles"
import CameraSvgIcon from "@/assets/icons/chat/camera-svgrepo-com.svg"

type AttachmentSheetProps = {
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
}

export function AttachmentSheet({
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
}: AttachmentSheetProps) {
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

export function QueuedAttachmentStrip({
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

export function MessageAttachmentList({
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
