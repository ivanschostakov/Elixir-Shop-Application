import { Pressable, StyleSheet, Text, View } from "react-native"
import Animated, { LinearTransition, ReduceMotion } from "react-native-reanimated"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { NativeChatAction, NativeChatTitleMaterial, nativeChatMentorActionAvailable, nativeChatMentorGreetingAvailable } from "@/screens/chat/native-chat-controls"
import { MentorIcon } from "@/screens/chat/mentor-ui"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import type { ProfileData } from "@/services/api/companion"

export const MENTOR_SHORTCUT_HEIGHT = 58
export const MENTOR_SHORTCUT_COLLAPSED_SIZE = 44

export function MentorShortcut({ onPress, onCollapse, collapsed = false, disabled = false, goal }: { onPress: () => void; onCollapse: () => void; collapsed?: boolean; disabled?: boolean; goal?: ProfileData["goal"] }) {
    useLanguage()
    const { isDark, palette } = useTheme()
    const label = mt("Открыть наставника")
    const greeting = goal === "weight_loss" ? mt("Добрый день!\nЯ ваш наставник по похудению") : goal === "weight_gain" ? mt("Добрый день!\nЯ ваш наставник по набору веса") : mt("Добрый день!\nЯ ваш наставник по питанию")
    const accessibilityLabel = collapsed ? label : `${greeting.replace("\n", " ")}. ${label}`
    const buttonStyle = [styles.button, collapsed && styles.round]
    return <View pointerEvents="box-none" style={styles.host}><Animated.View layout={LinearTransition.duration(200).reduceMotion(ReduceMotion.System)} style={collapsed ? styles.collapsed : styles.expanded}>
        {NativeChatAction && (collapsed ? nativeChatMentorActionAvailable : nativeChatMentorGreetingAvailable) ? <NativeChatAction testID="mentor-open-shortcut" action="mentor" {...(nativeChatMentorGreetingAvailable ? { title: collapsed ? "" : greeting } : {})} dark={isDark} label={accessibilityLabel} disabled={disabled} onAction={onPress} style={buttonStyle} /> :
        <Pressable testID="mentor-open-shortcut" accessibilityRole="button" accessibilityLabel={accessibilityLabel} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [buttonStyle, { opacity: disabled ? 0.45 : pressed ? 0.7 : 1 }]}>
        {NativeChatTitleMaterial ? <NativeChatTitleMaterial dark={isDark} pointerEvents="none" style={StyleSheet.absoluteFill} /> : <View pointerEvents="none" style={[StyleSheet.absoluteFill, styles.fallback, { backgroundColor: palette.surface }]} />}
        <MentorIcon name="leaf" size={25} />
        {!collapsed ? <Text numberOfLines={2} style={[styles.greeting, { color: palette.text }]}>{greeting}</Text> : null}
    </Pressable>}
        {!collapsed ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Свернуть приветствие")} disabled={disabled} onPress={onCollapse} hitSlop={2} style={({ pressed }) => [styles.collapse, { opacity: disabled ? 0.45 : pressed ? 0.6 : 1 }]}><MentorQuestionIcon name="close" size={20} color={palette.text} /></Pressable> : null}
    </Animated.View></View>
}

const styles = StyleSheet.create({
    button: { width: "100%", height: MENTOR_SHORTCUT_HEIGHT, borderRadius: 29, flexDirection: "row", gap: 11, alignItems: "center", paddingHorizontal: 16 },
    host: { height: MENTOR_SHORTCUT_HEIGHT, justifyContent: "flex-end" },
    expanded: { width: "100%", height: MENTOR_SHORTCUT_HEIGHT },
    collapsed: { width: MENTOR_SHORTCUT_COLLAPSED_SIZE, height: MENTOR_SHORTCUT_COLLAPSED_SIZE },
    round: { height: MENTOR_SHORTCUT_COLLAPSED_SIZE, borderRadius: 22, paddingHorizontal: 0, justifyContent: "center" },
    collapse: { position: "absolute", right: 6, top: 7, width: 44, height: 44, alignItems: "center", justifyContent: "center" },
    greeting: { flex: 1, marginRight: 40, fontSize: 14, lineHeight: 19, fontWeight: "500" },
    fallback: { borderRadius: 29 },
})
