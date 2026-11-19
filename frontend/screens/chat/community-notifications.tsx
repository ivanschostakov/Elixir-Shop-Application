import { Pressable, StyleSheet, Switch, Text, View } from "react-native"
import Svg, { Path } from "react-native-svg"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"

export type TopicNotificationAction = { muted: boolean; disabled: boolean; onPress: () => void }

function Bell({ muted, color }: { muted: boolean; color: string }) {
    return <Svg width={21} height={21} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" accessible={false}>
        <Path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
        {muted ? <Path d="m3 3 18 18" /> : null}
    </Svg>
}

export function CommunityNotificationButton({ muted, disabled, onPress }: TopicNotificationAction) {
    const { t } = useLanguage()
    const { palette } = useTheme()
    return <Pressable accessibilityRole="button" accessibilityLabel={t(muted ? "chat.communityUnmuteTopic" : "chat.communityMuteTopic")} accessibilityState={{ disabled }} disabled={disabled} onPress={event => { event.stopPropagation(); onPress() }}
        style={({ pressed }) => [styles.icon, { opacity: disabled ? 0.4 : pressed ? 0.65 : 1 }]}>
        <Bell muted={muted} color={muted ? palette.mutedText : palette.primary} />
    </Pressable>
}

export function CommunityGroupNotificationSwitch({ muted, busy, onChange }: { muted: boolean; busy: boolean; onChange: (muted: boolean) => void }) {
    const { t } = useLanguage()
    const { palette } = useTheme()
    return <View style={[styles.row, { backgroundColor: palette.surfaceOverlay, borderColor: palette.borderSoft }]}>
        <Bell muted={muted} color={palette.text} />
        <Text style={[styles.label, { color: palette.text }]}>{t("chat.communityGroupNotifications")}</Text>
        <Switch accessibilityLabel={t("chat.communityGroupNotifications")} disabled={busy} value={!muted} onValueChange={enabled => onChange(!enabled)} trackColor={{ true: palette.primary }} />
    </View>
}

const styles = StyleSheet.create({
    icon: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", flexShrink: 0 },
    row: { minHeight: 62, flexDirection: "row", alignItems: "center", gap: 12, paddingHorizontal: 14, paddingVertical: 10, borderRadius: 18, borderWidth: StyleSheet.hairlineWidth },
    label: { flex: 1, fontSize: 15, lineHeight: 21, fontWeight: "600" },
})
