import { useEffect, useState } from "react"
import { ActivityIndicator, Alert, Image, Platform, Pressable, Text } from "react-native"
import { Directory } from "expo-file-system"
import type { Directory as NativeDirectory } from "expo-file-system/build/ExpoFileSystem.types"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useLanguage } from "@/providers/language-provider"
import { downloadSupportAttachment } from "@/services/api/support"
import type { SupportAttachment } from "@/services/api/support.types"
import { createSupportChatStyles } from "./support-chat-screen.styles"

function asDataUrl(blob: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(blob)
    })
}

export function SupportMessageAttachment({ attachment }: { attachment: SupportAttachment }) {
    const { t } = useLanguage()
    const styles = useThemeStyles(createSupportChatStyles)
    const [uri, setUri] = useState("")
    const [failed, setFailed] = useState(false)
    const [attempt, setAttempt] = useState(0)
    const [saving, setSaving] = useState(false)
    const isImage = attachment.mime_type.startsWith("image/")
    useEffect(() => {
        if (!isImage) return
        let active = true
        setFailed(false)
        void downloadSupportAttachment(attachment.id).then(asDataUrl).then(value => {
            if (active) setUri(value)
        }).catch(() => { if (active) setFailed(true) })
        return () => { active = false }
    }, [attachment.id, isImage, attempt])

    async function save() {
        setSaving(true)
        try {
            const name = Array.from(attachment.original_filename, c => c.charCodeAt(0) < 32 || "/\\:".includes(c) ? "_" : c).join("")
            const file = await downloadSupportAttachment(attachment.id)
            if (Platform.OS === "web") {
                const url = URL.createObjectURL(file)
                const link = document.createElement("a")
                link.href = url; link.download = name; link.click()
                setTimeout(() => URL.revokeObjectURL(url), 30000)
            } else {
                const data = await asDataUrl(file)
                // Shared TypeScript config also resolves Expo's web declarations, which omit the native picker.
                const picker = Directory as typeof Directory & Pick<typeof NativeDirectory, "pickDirectoryAsync">
                const directory = await picker.pickDirectoryAsync()
                const output = directory.createFile(name, attachment.mime_type)
                output.write(data.slice(data.indexOf(",") + 1), { encoding: "base64" })
            }
        } catch (error) {
            if (!/cancel/i.test(String(error))) Alert.alert(t("common.errorTitle"), t("chat.attachmentsLoadFailedTitle"))
        } finally { setSaving(false) }
    }
    if (isImage && !failed) return uri
        ? <Image source={{ uri }} style={styles.attachmentImage} resizeMode="cover" onError={() => setFailed(true)} />
        : <ActivityIndicator />
    return <Pressable accessibilityRole="button" disabled={saving} onPress={isImage
        ? () => { setUri(""); setAttempt(n => n + 1) }
        : () => void save()}>
        {saving ? <ActivityIndicator /> : <Text style={styles.attachmentName}>
            {isImage ? t("common.retry") : t("chat.saveAttachment")} · {attachment.original_filename}
        </Text>}
    </Pressable>
}
