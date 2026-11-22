import { useEffect, useRef } from "react"
import { ActionSheetIOS, Image, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import type { UploadableSupportAttachment } from "@/services/api/support.types"

export function AttachmentSheet({ bottomInset, onClose, onOpenCamera, onOpenNativeGallery, visible }: {
    bottomInset: number
    onClose: () => void
    onOpenCamera: () => void
    onOpenNativeGallery: () => void
    visible: boolean
}) {
    const { t } = useLanguage()
    const { isDark, palette } = useTheme()
    const nativeSheetOpen = useRef(false)
    useEffect(() => {
        if (Platform.OS !== "ios" || !visible || nativeSheetOpen.current) return
        nativeSheetOpen.current = true
        ActionSheetIOS.showActionSheetWithOptions({
            options: [t("chat.attachmentsSelectGallery"), t("chat.attachmentsCameraTitle"), t("common.cancel")],
            cancelButtonIndex: 2,
            userInterfaceStyle: isDark ? "dark" : "light",
        }, index => {
            nativeSheetOpen.current = false
            onClose()
            if (index === 0) onOpenNativeGallery()
            if (index === 1) onOpenCamera()
        })
    }, [isDark, onClose, onOpenCamera, onOpenNativeGallery, t, visible])
    if (Platform.OS === "ios") return null
    return <Modal animationType="fade" onRequestClose={onClose} transparent visible={visible}>
        <View style={styles.modal}>
            <Pressable accessibilityLabel={t("common.cancel")} onPress={onClose} style={StyleSheet.absoluteFill} />
            <View style={[styles.sheet, { backgroundColor: palette.surface, paddingBottom: Math.max(bottomInset, 16) }]}>
                <Pressable onPress={() => { onClose(); onOpenNativeGallery() }} style={styles.option}><Text style={{ color: palette.text }}>{t("chat.attachmentsSelectGallery")}</Text></Pressable>
                <Pressable onPress={() => { onClose(); onOpenCamera() }} style={styles.option}><Text style={{ color: palette.text }}>{t("chat.attachmentsCameraTitle")}</Text></Pressable>
                <Pressable onPress={onClose} style={styles.option}><Text style={{ color: palette.primary }}>{t("common.cancel")}</Text></Pressable>
            </View>
        </View>
    </Modal>
}
export function QueuedAttachmentStrip({ attachments, onRemove }: {
    attachments: UploadableSupportAttachment[]
    onRemove: (index: number) => void
}) {
    const { t } = useLanguage()
    const { palette } = useTheme()
    if (!attachments.length) return null
    return <ScrollView horizontal contentContainerStyle={styles.queued} showsHorizontalScrollIndicator={false}>
        {attachments.map((attachment, index) => <View key={`${attachment.uri}-${index}`} style={[styles.preview, { backgroundColor: palette.surface }]}>
            <Image source={{ uri: attachment.uri }} style={styles.image} />
            <Pressable accessibilityLabel={t("chat.removeAttachment")} onPress={() => onRemove(index)} style={styles.remove}><Text style={{ color: palette.text }}>×</Text></Pressable>
        </View>)}
    </ScrollView>
}
const styles = StyleSheet.create({
    modal: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.35)" },
    sheet: { borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 16 },
    option: { padding: 16, alignItems: "center" },
    queued: { gap: 8, paddingBottom: 8 },
    preview: { width: 76, height: 76, borderRadius: 12, overflow: "hidden" },
    image: { width: "100%", height: "100%" },
    remove: { position: "absolute", right: 0, top: 0, padding: 6, backgroundColor: "rgba(255,255,255,0.85)", borderRadius: 12 },
})
