import { useRef, useState } from "react"
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"

import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { reportCommunityMessage, type CommunityReportReason } from "@/services/api/community"
import type { CommunityMessage } from "@/services/api/community.types"

const reasons = ["spam", "harassment", "dangerous_content", "inappropriate_content", "other"] as const

export function CommunityReportForm({ message, onClose, onBusyChange }: { message: CommunityMessage; onClose: () => void; onBusyChange: (busy: boolean) => void }) {
    const { t } = useLanguage()
    const { palette } = useTheme()
    const insets = useSafeAreaInsets()
    const [reason, setReason] = useState<CommunityReportReason>("spam")
    const [details, setDetails] = useState("")
    const [sending, setSending] = useState(false)
    const [sent, setSent] = useState(false)
    const [failed, setFailed] = useState(false)
    const inFlight = useRef(false)
    const close = () => { if (!inFlight.current) onClose() }
    const submit = async () => {
        if (inFlight.current) return
        inFlight.current = true
        setSending(true)
        setFailed(false)
        onBusyChange(true)
        try {
            await reportCommunityMessage(message.topic_id, message.id, reason, details.trim())
            setSent(true)
        } catch {
            setFailed(true)
        } finally { inFlight.current = false; setSending(false); onBusyChange(false) }
    }
    if (sent) return <View style={{ flex: 1, justifyContent: "center", padding: 24, gap: 20, backgroundColor: palette.background }}>
        <Text accessibilityRole="header" style={{ color: palette.text, fontSize: 22, fontWeight: "600" }}>{t("chat.communityReportSent")}</Text>
        <Text style={{ color: palette.text }}>{t("chat.communityReportSentBody")}</Text>
        <Pressable accessibilityRole="button" onPress={close} style={{ padding: 16, backgroundColor: palette.primary, borderRadius: 12, alignItems: "center" }}><Text style={{ color: "#fff" }}>{t("common.done")}</Text></Pressable>
    </View>
    return <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={{ flex: 1, backgroundColor: palette.background }}>
            <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: 24, paddingTop: Math.max(insets.top, 24), paddingBottom: Math.max(insets.bottom, 24), gap: 16 }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
                    <Text accessibilityRole="header" style={{ flex: 1, color: palette.text, fontSize: 22, fontWeight: "600" }}>{t("chat.communityReportAction")}</Text>
                    <Pressable accessibilityRole="button" disabled={sending} onPress={close} style={{ padding: 12 }}><Text style={{ color: palette.primary }}>{t("common.cancel")}</Text></Pressable>
                </View>
                <Text numberOfLines={3} style={{ color: palette.text }}>{message.author.full_name}: {message.text || t("chat.communityReportAttachment")}</Text>
                <Text style={{ color: palette.text }}>{t("chat.communityReportReason")}</Text>
                {reasons.map(value => <Pressable key={value} accessibilityRole="radio" accessibilityState={{ checked: reason === value }} disabled={sending} onPress={() => setReason(value)} style={{ padding: 14, borderRadius: 12, borderWidth: 1, borderColor: reason === value ? palette.primary : palette.text }}>
                    <Text style={{ color: palette.text }}>{reason === value ? "●  " : "○  "}{t(`chat.communityReportReason_${value}`)}</Text>
                </Pressable>)}
                <TextInput accessibilityLabel={t("chat.communityReportComment")} placeholder={t("chat.communityReportComment")} placeholderTextColor={palette.text} value={details} onChangeText={setDetails} editable={!sending} multiline maxLength={1000} textAlignVertical="top" style={{ minHeight: 110, padding: 14, color: palette.text, borderColor: palette.text, borderWidth: 1, borderRadius: 12 }} />
                <Text style={{ color: palette.text }}>{t("chat.communityReportPrivacy")}</Text>
                {failed ? <Text accessibilityRole="alert" style={{ color: palette.danger }}>{t("chat.communityReportFailed")}. {t("chat.communityReportRetry")}</Text> : null}
                <Pressable accessibilityRole="button" disabled={sending} onPress={() => void submit()} style={{ padding: 16, backgroundColor: palette.primary, borderRadius: 12, alignItems: "center", opacity: sending ? 0.6 : 1 }}>
                    {sending ? <ActivityIndicator color="#fff" /> : <Text style={{ color: "#fff", fontWeight: "600" }}>{t("chat.communityReportSend")}</Text>}
                </Pressable>
            </ScrollView>
        </KeyboardAvoidingView>
}
