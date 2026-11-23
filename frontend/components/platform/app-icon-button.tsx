import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native"
import Svg, { Path } from "react-native-svg"
import AttachmentIcon from "@/assets/icons/chat/attachment-svgrepo-com.svg"
import SettingsIcon from "@/assets/icons/mentor/settings.svg"
import { AdminComposerAction } from "@/components/platform/composer-action"
import { NativeChatAction } from "@/components/platform/native-controls"

export { nativeControlsAvailable as hasNativeControls } from "@/components/platform/native-controls"

export type AppIconAction = "back" | "settings" | "attachment" | "latest" | "mentor" | "microphone" | "send" | "stop" | "busy"
type Props = {
    action: AppIconAction; label: string; onPress: () => void; dark: boolean
    disabled?: boolean; title?: string; color?: string; backgroundColor?: string
    appearance?: "circle" | "plain" | "composer"; transcribing?: boolean
    style?: StyleProp<ViewStyle>
}
const paths: Partial<Record<AppIconAction, string>> = {
    back: "m15 5-7 7 7 7", latest: "m5 9 7 7 7-7",
    microphone: "M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5ZM5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8",
    send: "m3 11 18-8-8 18-2-8-8-2ZM11 13l10-10", stop: "M6 6h12v12H6Z",
    mentor: "M5 20C1 11 8 3 21 3c0 13-8 20-16 17ZM5 20 16 9",
}

export function AppIconButton({ action, label, onPress, dark, disabled = false, title, color, backgroundColor, appearance = "circle", transcribing = false, style }: Props) {
    if (NativeChatAction) return <NativeChatAction action={action} dark={dark} disabled={disabled} label={label} title={title} onAction={onPress} style={[styles.size, style]} />
    const fill = backgroundColor ?? (dark ? "#263040" : "#F2FAF5")
    const ink = color ?? (dark ? "#FFFFFF" : "#12161A")
    if (appearance === "composer") return <View style={[styles.size, style]}><AdminComposerAction active={action === "send"} backgroundColor={fill} busy={action === "busy"} disabled={disabled} onPress={onPress} recording={action === "stop"} transcribing={transcribing} /></View>
    return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled, busy: action === "busy" }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [styles.size, styles.button, appearance === "circle" && { backgroundColor: fill }, style, { opacity: disabled ? 0.5 : pressed ? 0.7 : 1 }]}>
        {action === "busy" ? <ActivityIndicator color={ink} /> : action === "attachment" ? <AttachmentIcon width={24} height={24} color={ink} /> : action === "settings" ? <SettingsIcon width={23} height={23} stroke={ink} color={ink} /> :
            <Svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke={ink} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" accessible={false}><Path d={paths[action] ?? ""} /></Svg>}
        {title ? <Text style={{ color: ink }}>{title}</Text> : null}
    </Pressable>
}
const styles = StyleSheet.create({ size: { width: 44, height: 44 }, button: { borderRadius: 22, alignItems: "center", justifyContent: "center" } })
