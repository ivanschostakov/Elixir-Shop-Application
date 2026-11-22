import { ActivityIndicator, Pressable, StyleSheet, View } from "react-native"
import Svg, { Path } from "react-native-svg"
import AttachmentIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { ChatComposerInput } from "@/screens/chat/chat-composer-input"
import { NativeChatAction, NativeChatInputMaterial } from "@/screens/chat/native-chat-controls"

export function ChatComposer({ value, onChangeText, placeholder, onAttachment, onAction, hasContent, disabled, busy }: {
    value: string
    onChangeText: (value: string) => void
    placeholder: string
    onAttachment: () => void
    onAction: () => void
    hasContent: boolean
    disabled: boolean
    busy: boolean
}) {
    const { t } = useLanguage()
    const { isDark, palette } = useTheme()
    const fill = isDark ? "#263040" : "#F2FAF5"
    const label = t(busy ? "chat.sending" : "chat.sendAction")
    return <View testID="chat-composer" style={styles.row}>
        {NativeChatAction ? <NativeChatAction action="attachment" dark={isDark} label={t("chat.addAttachment")} onAction={onAttachment} style={styles.action} /> : <Pressable accessibilityRole="button" accessibilityLabel={t("chat.addAttachment")} onPress={onAttachment} style={[styles.action, styles.fallbackAttachment, { backgroundColor: fill }]}><AttachmentIcon width={24} height={24} color={palette.text} /></Pressable>}
        <View style={styles.entry}>
            {NativeChatInputMaterial ? <NativeChatInputMaterial dark={isDark} joined={hasContent} pointerEvents="none" style={StyleSheet.absoluteFill} /> : <View pointerEvents="none" style={[styles.surface, { right: hasContent ? 0 : 50, backgroundColor: fill, borderColor: palette.border }]} />}
            <View style={styles.inputWrap}>
                <ChatComposerInput accessibilityLabel={placeholder} editable={!busy} onChangeText={onChangeText} placeholder={placeholder} placeholderTextColor={palette.mutedText} selectionColor="#078AFF" style={[styles.input, { color: palette.text }]} value={value} keyboardAppearance={isDark ? "dark" : "light"} />
            </View>
            {NativeChatAction ? <NativeChatAction action={busy ? "busy" : "send"} dark={isDark} disabled={disabled} label={label} onAction={onAction} style={styles.action} /> : <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ busy, disabled }} disabled={disabled} onPress={onAction} style={[styles.action, styles.fallbackAttachment, { backgroundColor: hasContent ? palette.primary : fill, opacity: disabled ? 0.5 : 1 }]}>{busy ? <ActivityIndicator color={palette.text} /> : <Svg width={24} height={24} viewBox="0 0 24 24"><Path d="m12 4 7 7-1.5 1.5-4.5-4.5V21h-2V8l-4.5 4.5L5 11Z" fill={hasContent ? "#FFFFFF" : palette.text} /></Svg>}</Pressable>}
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
