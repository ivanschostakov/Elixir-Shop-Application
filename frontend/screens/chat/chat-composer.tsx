import type { Ref } from "react"
import { Platform, StyleSheet, View, type TextInput } from "react-native"

import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { ChatComposerInput } from "@/screens/chat/chat-composer-input"
import { AppIconButton } from "@/components/platform/app-icon-button"
import { AppComposerSurface } from "@/components/platform/app-surface"

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
    const fill = Platform.OS === "android"
        ? (isDark ? "rgba(38,48,64,0.55)" : "rgba(242,250,245,0.55)")
        : (isDark ? "#263040" : "#F2FAF5")

    return <View testID="chat-composer" style={styles.row}>
        <AppIconButton action="attachment" dark={isDark} disabled={attachmentDisabled} label={t("chat.communityAddAttachment")} onPress={onAttachment} backgroundColor={fill} color={palette.text} style={styles.action} />
        <View style={styles.entry}>
            <AppComposerSurface dark={isDark} joined={joined} fallbackColor={fill} borderColor={palette.border} />
            <View style={styles.inputWrap}>
                <ChatComposerInput inputRef={inputRef} accessibilityLabel={placeholder} editable={!recording && !transcribing} onFocus={onFocus} onBlur={onBlur} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={palette.mutedText} selectionColor="#078AFF" style={[styles.input, { color: palette.text }]} value={value} keyboardAppearance={isDark ? "dark" : "light"} />
            </View>
            <AppIconButton action={action} dark={isDark} disabled={disabled} label={label} onPress={onAction} appearance="composer" backgroundColor={fill} transcribing={transcribing} style={styles.action} />
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
