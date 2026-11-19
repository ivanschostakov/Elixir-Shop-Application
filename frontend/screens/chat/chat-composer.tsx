import type { Ref } from "react"
import { Pressable, StyleSheet, View, type TextInput } from "react-native"

import AttachmentIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { AdminComposerAction } from "@/screens/chat/admin-composer-action"
import { ChatComposerInput } from "@/screens/chat/chat-composer-input"
import { NativeChatAction, NativeChatInputMaterial } from "@/screens/chat/native-chat-controls"

/** One composer and recording affordance for every conversation. */
export function ChatComposer({ value, onChangeText, placeholder, inputRef, onFocus, onBlur, onAttachment, onAction, hasContent, disabled = false, attachmentDisabled = false, recording = false, busy = false, transcribing = false }: {
    value: string
    onChangeText: (value: string) => void
    placeholder: string
    inputRef?: Ref<TextInput>
    onFocus?: () => void
    onBlur?: () => void
    onAttachment: () => void
    onAction: () => void
    hasContent: boolean
    disabled?: boolean
    attachmentDisabled?: boolean
    recording?: boolean
    busy?: boolean
    transcribing?: boolean
}) {
    const { t } = useLanguage()
    const { isDark, palette } = useTheme()
    const joined = hasContent && !recording
    const action = busy ? "busy" : recording ? "stop" : joined ? "send" : "microphone"
    const label = t(busy ? transcribing ? "chat.voiceTranscribing" : "chat.sending" : recording ? "chat.voiceStopAction" : joined ? "chat.sendAction" : "chat.voiceRecordAction")
    const fill = isDark ? "#263040" : "#F2FAF5"

    return <View testID="chat-composer" style={styles.row}>
        {NativeChatAction ? <NativeChatAction action="attachment" dark={isDark} disabled={attachmentDisabled} label={t("chat.communityAddAttachment")} onAction={onAttachment} style={styles.action} /> : <Pressable accessibilityRole="button" accessibilityLabel={t("chat.communityAddAttachment")} disabled={attachmentDisabled} onPress={onAttachment} style={({ pressed }) => [styles.action, styles.fallbackAttachment, { backgroundColor: fill, opacity: attachmentDisabled ? 0.5 : pressed ? 0.75 : 1 }]}><AttachmentIcon width={24} height={24} color={palette.text} /></Pressable>}
        <View style={styles.entry}>
            {NativeChatInputMaterial ? <NativeChatInputMaterial dark={isDark} joined={joined} pointerEvents="none" style={StyleSheet.absoluteFill} /> : <View pointerEvents="none" style={[styles.surface, { right: joined ? 0 : 50, backgroundColor: fill, borderColor: palette.border }]} />}
            <View style={styles.inputWrap}>
                <ChatComposerInput inputRef={inputRef} accessibilityLabel={placeholder} editable={!recording && !transcribing} onFocus={onFocus} onBlur={onBlur} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={palette.mutedText} selectionColor="#078AFF" style={[styles.input, { color: palette.text }]} value={value} keyboardAppearance={isDark ? "dark" : "light"} />
            </View>
            {NativeChatAction ? <NativeChatAction action={action} dark={isDark} disabled={disabled} label={label} onAction={onAction} style={styles.action} /> : <AdminComposerAction active={joined} backgroundColor={fill} busy={busy} disabled={disabled} onPress={onAction} recording={recording} transcribing={transcribing} />}
        </View>
    </View>
}

const styles = StyleSheet.create({
    row: { flexDirection: "row", alignItems: "flex-end", gap: 6 },
    action: { width: 44, height: 44, flexShrink: 0 },
    fallbackAttachment: { borderRadius: 22, alignItems: "center", justifyContent: "center" },
    entry: { flex: 1, minWidth: 0, flexDirection: "row", alignItems: "flex-end", gap: 6 },
    surface: { ...StyleSheet.absoluteFillObject, borderRadius: 22, borderWidth: StyleSheet.hairlineWidth },
    inputWrap: { flex: 1, minWidth: 0, minHeight: 44, borderRadius: 22, overflow: "hidden", justifyContent: "center" },
    input: { fontSize: 17, lineHeight: 22, paddingHorizontal: 13, paddingTop: 11, paddingBottom: 11, includeFontPadding: false, backgroundColor: "transparent" },
})
