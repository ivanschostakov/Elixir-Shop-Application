import { useEffect, useRef, useState, type ReactNode } from "react"
import { ActivityIndicator, Animated, Easing, Keyboard, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { mentorStepError, type MentorForm } from "@/screens/chat/mentor-onboarding-data"
import { MentorIcon, useMentorPalette } from "@/screens/chat/mentor-ui"

type Props = {
    visible: boolean; value: MentorForm; onChange: (value: MentorForm) => void
    onClose: () => void; onSave: () => Promise<void>; saving: boolean; error: string
    children?: ReactNode
}

export function MentorOnboarding({ visible, value, onChange, onClose, onSave, saving, error, children }: Props) {
    useLanguage()
    const colors = useMentorPalette()
    const insets = useSafeAreaInsets()
    const reducedMotion = useChatReducedMotion()
    const [step, setStep] = useState(0)
    const [width, setWidth] = useState(0)
    const [validation, setValidation] = useState("")
    const progress = useRef(new Animated.Value(0)).current
    const mentorStepTitles = [mt("Какая у вас цель?"), mt("Немного о вас"), mt("Рост и текущий вес"), mt("Как проходит ваш день?")]
    const mentorGoalChoices = [
        { value: "weight_loss" as const, label: mt("Снизить вес"), icon: "progress" as const },
        { value: "weight_gain" as const, label: mt("Набрать вес"), icon: "workout" as const },
        { value: "maintain" as const, label: mt("Поддерживать форму"), icon: "smile" as const },
        { value: "custom" as const, label: mt("Своя цель"), icon: "adjust" as const },
    ]
    const mentorActivityChoices = [
        { value: "low" as const, label: mt("Низкая активность") }, { value: "light" as const, label: mt("Лёгкая активность") },
        { value: "moderate" as const, label: mt("Умеренная активность") }, { value: "high" as const, label: mt("Высокая активность") },
    ]

    useEffect(() => {
        if (!visible || reducedMotion || !width) { progress.setValue(step); return }
        const animation = Animated.timing(progress, { toValue: step, duration: 320, easing: Easing.bezier(0.22, 1, 0.36, 1), useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [progress, reducedMotion, step, visible, width])

    const change = (patch: Partial<MentorForm>) => { setValidation(""); onChange({ ...value, ...patch }) }
    const go = (next: number) => { Keyboard.dismiss(); setValidation(""); setStep(next) }
    const back = () => { if (!saving) { if (step) go(step - 1); else onClose() } }
    const next = () => {
        const problem = mentorStepError(value, step)
        if (problem) { setValidation(problem); return }
        if (step < 3) go(step + 1)
        else { Keyboard.dismiss(); void onSave() }
    }

    const field = (label: string, fieldName: "age" | "height" | "weight", unit: string, active: boolean) => <View style={styles.field}>
        <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
        <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <TextInput accessibilityLabel={label} value={value[fieldName]} onChangeText={text => change({ [fieldName]: text })}
                editable={active && !saving} keyboardType={fieldName === "age" ? "number-pad" : "decimal-pad"} maxLength={7}
                keyboardAppearance={colors.surface === "#FFFFFF" ? "light" : "dark"} selectionColor={colors.greenBright}
                style={[styles.input, { color: colors.text }]} />
            <Text style={[styles.unit, { color: colors.muted }]}>{unit}</Text>
        </View>
    </View>
    const choice = (label: string, selected: boolean, onPress: () => void, disabled: boolean, icon?: "progress" | "workout" | "smile" | "adjust") => <Pressable
        key={label} accessibilityRole="radio" accessibilityLabel={label} accessibilityState={{ checked: selected, disabled }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [styles.choice, { borderColor: selected ? colors.greenBright : colors.border, backgroundColor: selected ? colors.mint : colors.surface, opacity: pressed ? 0.72 : 1 }]}>
        {icon ? <MentorIcon name={icon} size={26} color={colors.green} /> : null}
        <Text style={[styles.choiceLabel, { color: colors.text }]}>{label}</Text>
        <View style={[styles.radio, { borderColor: selected ? colors.greenBright : colors.border }]}>{selected ? <View style={[styles.radioDot, { backgroundColor: colors.greenBright }]} /> : null}</View>
    </Pressable>

    return <Modal visible={visible} animationType={reducedMotion ? "none" : "fade"} presentationStyle="fullScreen" onRequestClose={children ? onClose : back}>
        {children ? <View style={[styles.screen, { backgroundColor: colors.surface, paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, 12) }]}>{children}</View> :
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={[styles.screen, { backgroundColor: colors.surface, paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, 12) }]}>
            <View style={styles.header}>
                <View style={styles.brand}><MentorIcon name="leaf" size={29} /><Text style={[styles.brandText, { color: colors.text }]}>ElixirPeptide</Text></View>
                <Pressable accessibilityRole="button" accessibilityLabel={mt("Закрыть")} disabled={saving} onPress={() => { Keyboard.dismiss(); onClose() }} style={styles.iconButton}>
                    <Text style={[styles.close, { color: colors.text }]}>×</Text>
                </Pressable>
            </View>
            <View style={styles.stepHeader}>
                <Pressable accessibilityRole="button" accessibilityLabel={mt("Назад")} accessible={step > 0} aria-hidden={step === 0} disabled={saving || step === 0} onPress={back} style={[styles.iconButton, step === 0 && styles.hidden]}><MentorIcon name="back" color={colors.text} /></Pressable>
                <Text accessibilityLiveRegion="polite" style={[styles.stepCount, { color: colors.muted }]}>{mt("Шаг {0} из {1}", [step + 1, 4])}</Text>
            </View>
            <View style={styles.progress}>{[0, 1, 2, 3].map(index => <View key={index} style={[styles.segment, { backgroundColor: colors.border }]}>
                <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: colors.greenBright, opacity: index === 0 ? 1 : progress.interpolate({ inputRange: [index - 1, index], outputRange: [0, 1], extrapolate: "clamp" }) }]} />
            </View>)}</View>
            <View testID="mentor-onboarding-transition" onLayout={event => setWidth(event.nativeEvent.layout.width)} style={styles.viewport}>
                {[0, 1, 2, 3].map(index => {
                    const active = step === index
                    const disabled = !active || saving
                    return <Animated.View key={index} testID={`mentor-onboarding-step-${index + 1}`} pointerEvents={active ? "auto" : "none"}
                        accessibilityElementsHidden={!active} importantForAccessibility={active ? "auto" : "no-hide-descendants"} aria-hidden={!active}
                        style={[styles.pane, { opacity: width ? progress.interpolate({ inputRange: [index - 1, index, index + 1], outputRange: [0.25, 1, 0.25], extrapolate: "clamp" }) : active ? 1 : 0,
                            transform: [{ translateX: progress.interpolate({ inputRange: [0, 3], outputRange: [index * width, (index - 3) * width] }) }] }]}>
                        <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={styles.stepBody}>
                            <Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>{mentorStepTitles[index]}</Text>
                            {index === 0 ? <View accessibilityRole="radiogroup" style={styles.choices}>{mentorGoalChoices.map(item => choice(item.label, value.goal === item.value, () => change({ goal: item.value }), disabled, item.icon))}
                                {value.goal === "custom" ? <TextInput accessibilityLabel={mt("Своя цель")} value={value.customGoal} onChangeText={customGoal => change({ customGoal })} editable={!disabled} maxLength={500} multiline style={[styles.customInput, { color: colors.text, borderColor: colors.border }]} /> : null}
                            </View> : null}
                            {index === 1 ? <View style={styles.groups}>{field(mt("Возраст"), "age", mt("лет"), active)}<View style={styles.field}><Text style={[styles.label, { color: colors.text }]}>{mt("Пол")}</Text><View accessibilityRole="radiogroup" style={styles.sexChoices}>
                                {choice(mt("Женский"), value.sex === "female", () => change({ sex: "female" }), disabled)}
                                {choice(mt("Мужской"), value.sex === "male", () => change({ sex: "male" }), disabled)}
                            </View></View></View> : null}
                            {index === 2 ? <View style={styles.groups}>{field(mt("Рост"), "height", mt("см"), active)}{field(mt("Текущий вес"), "weight", mt("кг"), active)}</View> : null}
                            {index === 3 ? <View accessibilityRole="radiogroup" style={styles.choices}>{mentorActivityChoices.map(item => choice(item.label, value.activity === item.value, () => change({ activity: item.value }), disabled))}</View> : null}
                        </ScrollView>
                    </Animated.View>
                })}
            </View>
            <View style={styles.footer}>
                {validation || error ? <Text accessibilityRole="alert" style={styles.error}>{validation || error}</Text> : null}
                <Pressable testID="mentor-onboarding-next" accessibilityRole="button" accessibilityState={{ disabled: saving, busy: saving }} disabled={saving} onPress={next}
                    style={({ pressed }) => [styles.next, { backgroundColor: colors.greenBright, opacity: saving ? 0.6 : pressed ? 0.8 : 1 }]}>
                    {saving ? <ActivityIndicator color="#FFFFFF" /> : <><Text style={styles.nextText}>{mt(step === 3 ? "Открыть наставника" : "Дальше")}</Text><Text style={styles.arrow}>→</Text></>}
                </Pressable>
            </View>
        </KeyboardAvoidingView>}
    </Modal>
}

const styles = StyleSheet.create({
    screen: { flex: 1 }, header: { paddingHorizontal: 24, paddingTop: 12, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    brand: { flexDirection: "row", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }, brandText: { fontSize: 21, fontWeight: "700", flexShrink: 1 },
    iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" }, close: { fontSize: 35, lineHeight: 39, fontWeight: "300" }, hidden: { opacity: 0 },
    stepHeader: { paddingHorizontal: 15, marginTop: 12, flexDirection: "row", alignItems: "center" }, stepCount: { fontSize: 15, fontWeight: "500" },
    progress: { flexDirection: "row", gap: 6, marginHorizontal: 24, marginTop: 8, marginBottom: 4 }, segment: { flex: 1, height: 5, borderRadius: 3, overflow: "hidden" },
    viewport: { flex: 1, minHeight: 0, overflow: "hidden" }, pane: { ...StyleSheet.absoluteFillObject },
    stepBody: { paddingHorizontal: 24, paddingTop: 28, paddingBottom: 24, width: "100%", maxWidth: 560, alignSelf: "center" },
    title: { fontSize: 29, lineHeight: 36, fontWeight: "700", marginBottom: 28 }, choices: { gap: 13 }, groups: { gap: 28 }, field: { gap: 10 }, label: { fontSize: 17, fontWeight: "600" },
    choice: { flexGrow: 1, flexBasis: 0, minHeight: 76, paddingHorizontal: 18, paddingVertical: 18, borderWidth: 1.5, borderRadius: 18, flexDirection: "row", alignItems: "center", gap: 14 },
    choiceLabel: { fontSize: 17, lineHeight: 24, fontWeight: "600", flex: 1, flexShrink: 1 }, radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: "center", justifyContent: "center" }, radioDot: { width: 12, height: 12, borderRadius: 6 },
    inputWrap: { borderWidth: 1.5, borderRadius: 16, minHeight: 74, flexDirection: "row", alignItems: "center", paddingHorizontal: 18 }, input: { flex: 1, minWidth: 0, fontSize: 28, paddingVertical: 15 }, unit: { fontSize: 18, paddingLeft: 10 },
    customInput: { minHeight: 100, borderWidth: 1.5, borderRadius: 16, padding: 16, fontSize: 17, textAlignVertical: "top" }, sexChoices: { flexDirection: "row", gap: 10 },
    footer: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, paddingTop: 12, paddingBottom: 12, gap: 12 },
    next: { minHeight: 56, borderRadius: 17, paddingHorizontal: 18, paddingVertical: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 12 }, nextText: { color: "#FFFFFF", fontSize: 18, fontWeight: "600", flexShrink: 1, textAlign: "center" }, arrow: { color: "#FFFFFF", fontSize: 25, lineHeight: 28 },
    error: { color: "#B55353", fontSize: 14, lineHeight: 20 },
})
