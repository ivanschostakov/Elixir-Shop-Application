import { useLayoutEffect, useRef, type ReactNode } from "react"
import { ActivityIndicator, Animated, Easing, Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"

export function MentorStageTransition({ children }: { children: ReactNode }) {
    const reduced = useChatReducedMotion()
    const opacity = useRef(new Animated.Value(reduced ? 1 : 0)).current
    useLayoutEffect(() => {
        if (reduced) { opacity.setValue(1); return }
        const animation = Animated.timing(opacity, { toValue: 1, duration: 170, easing: Easing.bezier(0.2, 0, 0, 1), useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [opacity, reduced])
    return <Animated.View style={[flowStyles.fill, { opacity, transform: [{ translateY: opacity.interpolate({ inputRange: [0, 1], outputRange: [8, 0] }) }] }]}>{children}</Animated.View>
}

export function MentorFlowHeader({ section, step, total, onBack, onClose, busy = false }: { section?: string; step?: number; total?: number; onBack?: () => void; onClose: () => void; busy?: boolean }) {
    const colors = useMentorPalette()
    return <>
        <View style={flowStyles.header}>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Назад")} disabled={!onBack || busy} onPress={onBack} style={[flowStyles.iconButton, !onBack && { opacity: 0 }]} accessibilityElementsHidden={!onBack}>
                <MentorQuestionIcon name="back" size={26} color={colors.text} />
            </Pressable>
            <View style={flowStyles.headerCenter}>
                {section ? <Text style={[flowStyles.section, { color: colors.green }]}>{section}</Text> : <MentorQuestionIcon name="leaf" size={25} color={colors.green} />}
                {step !== undefined && total ? <Text style={[flowStyles.count, { color: colors.muted }]}>{mt("Шаг {0} из {1}", [step + 1, total])}</Text> : null}
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Закрыть")} disabled={busy} onPress={onClose} style={flowStyles.iconButton}><MentorQuestionIcon name="close" size={24} color={colors.muted} /></Pressable>
        </View>
        {step !== undefined && total ? <View testID="mentor-section-progress" accessibilityRole="progressbar" accessibilityValue={{ min: 0, max: total, now: step + 1 }} style={flowStyles.progress}>
            {Array.from({ length: total }, (_, index) => <View key={index} style={[flowStyles.segment, { backgroundColor: index <= step ? colors.greenBright : colors.border }]} />)}
        </View> : null}
    </>
}

export function MentorFlowButton({ label, onPress, secondary = false, busy = false, disabled = false, testID }: { label: string; onPress: () => void; secondary?: boolean; busy?: boolean; disabled?: boolean; testID?: string }) {
    const colors = useMentorPalette()
    return <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: disabled || busy, busy }} disabled={disabled || busy} onPress={onPress}
        style={({ pressed }) => [flowStyles.button, { backgroundColor: secondary ? colors.surface : colors.greenBright, borderColor: secondary ? colors.border : colors.greenBright, opacity: disabled || busy ? 0.55 : pressed ? 0.75 : 1 }]}>
        {busy ? <ActivityIndicator color={secondary ? colors.green : "#FFFFFF"} /> : <Text style={[flowStyles.buttonText, { color: secondary ? colors.text : "#FFFFFF" }]}>{label}</Text>}
    </Pressable>
}

export function MentorFlowBody({ children }: { children: ReactNode }) {
    return <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={flowStyles.body}>{children}</ScrollView>
}

export const flowStyles = StyleSheet.create({
    fill: { flex: 1, minHeight: 0 },
    header: { paddingHorizontal: 16, paddingTop: 8, minHeight: 64, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    headerCenter: { flex: 1, alignItems: "center", gap: 4 }, section: { fontSize: 12, fontWeight: "700", letterSpacing: 0.8, textTransform: "uppercase" }, count: { fontSize: 12, fontWeight: "500" },
    iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" }, close: { fontSize: 32, lineHeight: 36, fontWeight: "300" },
    progress: { flexDirection: "row", gap: 5, marginHorizontal: 24, marginTop: 12, marginBottom: 4 }, segment: { flex: 1, height: 4, borderRadius: 4 },
    body: { paddingHorizontal: 24, paddingTop: 30, paddingBottom: 24, gap: 24, width: "100%", maxWidth: 560, alignSelf: "center", flexGrow: 1 },
    title: { fontSize: 31, lineHeight: 38, fontWeight: "700", letterSpacing: -0.7 },
    footer: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, paddingTop: 12, paddingBottom: 12, gap: 10 },
    button: { minHeight: 56, borderRadius: 18, paddingHorizontal: 20, paddingVertical: 15, borderWidth: 1, alignItems: "center", justifyContent: "center" },
    buttonText: { fontSize: 17, lineHeight: 24, fontWeight: "600", textAlign: "center" }, error: { color: "#B55353", fontSize: 14, lineHeight: 21 },
})
