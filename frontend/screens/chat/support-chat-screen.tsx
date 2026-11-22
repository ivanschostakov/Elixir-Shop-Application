import { useCallback, useEffect, useRef, useState } from "react"
import {
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
    View,
} from "react-native"
import { useCameraPermissions } from "expo-camera"
import * as ImagePicker from "expo-image-picker"
import { useRouter } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { ChatKeyboardPane, ChatMessageScrollView, ChatComposerDock } from "@/screens/chat/chat-keyboard-motion"
import { ChatEdgeBlur } from "@/screens/chat/chat-edge-blur"
import { ROUTES } from "@/constants/routes"
import { useChatScroll } from "@/hooks/chat/use-chat-scroll"
import { useSupportChat } from "@/hooks/chat/use-support-chat"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import type { SupportConversationStatus, UploadableSupportAttachment } from "@/services/api/support.types"
import { API_BASE_URL } from "@/services/api/constants"
import { getAuthTokens } from "@/services/auth/session"
import {
    createAttachmentFromImagePickerAsset,
} from "@/screens/chat/chat-attachments"
import { AttachmentSheet, QueuedAttachmentStrip } from "@/screens/chat/chat-screen.attachments"
import {
    CHAT_BACKGROUND_DARK,
    CHAT_BACKGROUND_LIGHT,
} from "@/screens/chat/chat-screen.constants"
import { ChatComposer } from "@/screens/chat/chat-composer"
import { NativeChatAction, NativeChatMenu, NativeChatTitleMaterial } from "@/screens/chat/native-chat-controls"
import { createChatScreenStyles } from "@/screens/chat/chat-screen.styles"
import { createSupportChatStyles } from "@/screens/chat/support-chat-screen.styles"
import { QuietLoading } from "@/components/ui/quiet-loading"
import { spacing } from "@/theme/spacing"
import { createUuid } from "@/utils/uuid"

type SupportChatScreenProps = {
    requestedConversationId: number | null
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


export function SupportChatScreen({ requestedConversationId }: SupportChatScreenProps) {
    const styles = useThemeStyles(createSupportChatStyles)
    const chatStyles = useThemeStyles(createChatScreenStyles)
    const { isDark, palette, themeName } = useTheme()
    const { t } = useLanguage()
    const router = useRouter()
    const { top, bottom } = useSafeAreaInsets()
    const [cameraPermission, requestCameraPermission] = useCameraPermissions()
    const scrollRef = useRef<ScrollView | null>(null)
    const chatScroll = useChatScroll(scrollRef, null)
    const [draft, setDraft] = useState("")
    const [attachments, setAttachments] = useState<UploadableSupportAttachment[]>([])
    const [attachmentSheetVisible, setAttachmentSheetVisible] = useState(false)
    const [composerHeight, setComposerHeight] = useState(74)
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
    } = useSupportChat()
    const headerTop = top + 8
    const contentTop = headerTop + 52
    const iosChat = Platform.OS === "ios"
    const isHistorical = Boolean(conversation && conversation.id !== inbox?.active?.id)
    const contentBottom = isHistorical ? 0 : composerHeight
    const hasComposerContent = Boolean(draft.trim()) || attachments.length > 0

    useEffect(() => {
        if (!requestedConversationId || conversation?.id === requestedConversationId) return
        if (inbox?.active?.id === requestedConversationId) {
            closePrevious()
            return
        }
        if (inbox?.previous.some((item) => item.id === requestedConversationId)) {
            void openPrevious(requestedConversationId)
        }
    }, [closePrevious, conversation?.id, inbox?.active?.id, inbox?.previous, openPrevious, requestedConversationId])




    const appendAttachments = useCallback((items: UploadableSupportAttachment[]) => {
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
        pendingAttachments: UploadableSupportAttachment[],
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
        if (!hasComposerContent || sending || isHistorical) return
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
    ])

    const statusLabels: Record<SupportConversationStatus, string> = {
        new: t("chat.supportStatusNew"),
        open: t("chat.supportStatusOpen"),
        waiting_customer: t("chat.supportStatusWaitingCustomer"),
        waiting_team: t("chat.supportStatusWaitingTeam"),
        resolved: t("chat.supportStatusResolved"),
        spam: t("chat.supportStatusSpam"),
    }

    const historyItems = [...(inbox?.active ? [inbox.active] : []), ...(inbox?.previous ?? [])]


    return (
        <ChatKeyboardPane style={styles.overlay}>
            <View style={styles.screen}>
                <>
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_LIGHT} style={[chatStyles.backgroundImage, themeName === "dark" ? chatStyles.backgroundImageHidden : null]} />
                <ImageBackground imageStyle={chatStyles.backgroundImageAsset} resizeMode="cover" source={CHAT_BACKGROUND_DARK} style={[chatStyles.backgroundImage, themeName === "dark" ? null : chatStyles.backgroundImageHidden]} />
                <View pointerEvents="none" style={[chatStyles.backgroundScrim, isDark ? chatStyles.backgroundScrimDark : chatStyles.backgroundScrimLight]} />
                </>
                <View style={[styles.header, { top: headerTop }]}>
                    <View style={styles.backControl}>
                        {NativeChatAction ? <NativeChatAction
                            action="back" dark={isDark} label={t("nav.back")}
                            onAction={() => router.canGoBack() ? router.back() : router.replace(ROUTES.discover)}
                            style={styles.nativeBackButton}
                        /> : <Pressable accessibilityLabel={t("nav.back")} accessibilityRole="button"
                            onPress={() => router.canGoBack() ? router.back() : router.replace(ROUTES.discover)}
                            style={styles.backButton}><Text style={styles.backText}>‹</Text></Pressable>}
                    </View>
                    <View style={styles.titlePill}>
                        {NativeChatTitleMaterial ? <NativeChatTitleMaterial dark={isDark} pointerEvents="none" style={styles.titleMaterial} /> : <View pointerEvents="none" style={styles.titleFallback} />}
                        <Text accessibilityRole="header" numberOfLines={1} style={styles.headerTitle}>{t("chat.supportTitle")}</Text>
                    </View>
                </View>

                <KeyboardAvoidingView
                    enabled={!iosChat}
                    behavior={iosChat ? "padding" : "height"}
                    contentContainerStyle={chatStyles.keyboardContent}
                    keyboardVerticalOffset={0}
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
                        {NativeChatMenu && inbox?.previous.length ? (
                            <NativeChatMenu
                                dark={isDark}
                                label={t("chat.supportHistory")}
                                labels={historyItems.map(item => item.id === inbox.active?.id ? t("chat.supportCurrent") : item.subject || `#${item.id}`)}
                                details={historyItems.map(item => `${statusLabels[item.status]} · ${historyDate(item.last_message_at)}`)}
                                selectedIndex={historyItems.findIndex(item => item.id === conversation?.id)}
                                onSelect={({ nativeEvent: { index } }) => {
                                    const item = historyItems[index]
                                    if (!item) return
                                    if (item.id === inbox.active?.id) closePrevious()
                                    else void openPrevious(item.id)
                                }}
                                style={{ height: 44, marginBottom: spacing.md }}
                            />
                        ) : inbox?.previous.length ? (
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
                                <QueuedAttachmentStrip
                                    attachments={attachments}
                                    onRemove={(index) => {
                                        setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))
                                    }}
                                />
                                <ChatComposer
                                    value={draft}
                                    onChangeText={setDraft}
                                    placeholder={t("chat.supportInputPlaceholder")}
                                    onAttachment={openAttachmentSheet}
                                    onAction={() => { void handleSend() }}
                                    hasContent={hasComposerContent}
                                    disabled={sending || !hasComposerContent}
                                    busy={sending}
                                />
                            </ChatComposerDock>
                        ) : null}
                    </View>
                </KeyboardAvoidingView>
                {iosChat ? <ChatEdgeBlur dark={isDark} topEdge style={[chatStyles.dialogTopBlur, { height: contentTop + 10 }]} /> : null}
                <AttachmentSheet
                    bottomInset={bottom}
                    onClose={closeAttachmentSheet}
                    onOpenCamera={() => { void openCamera() }}
                    onOpenNativeGallery={() => { void openGallery() }}
                    visible={attachmentSheetVisible}
                />
            </View>
        </ChatKeyboardPane>
    )
}
