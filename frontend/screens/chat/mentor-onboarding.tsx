import { useEffect, useRef, useState, type ReactNode } from "react"
import { Animated, Easing, Keyboard, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { mentorStepError, type MentorForm } from "@/screens/chat/mentor-onboarding-data"
import { MentorFlowButton, MentorFlowHeader, flowStyles } from "@/screens/chat/mentor-onboarding-layout"
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
    const showingForm = useRef(false)
    const mentorStepTitles = [mt("Какая у вас цель?"), mt("Немного о вас"), mt("Рост и текущий вес"), mt("Как проходит ваш день?"), mt("Какого веса хотите достичь?")]
    const mentorGoalChoices = [
        { value: "weight_loss" as const, label: mt("Снизить вес"), icon: "progress" as const },
        { value: "weight_gain" as const, label: mt("Набрать вес"), icon: "workout" as const },
        { value: "maintain" as const, label: mt("Поддерживать форму"), icon: "smile" as const },
        { value: "custom" as const, label: mt("Своя цель"), icon: "adjust" as const },
    ]
    const mentorActivityChoices = [
        { value: "low" as const, label: mt("Низкая активность"), example: mt("Сидячая работа, мало прогулок") },
        { value: "light" as const, label: mt("Лёгкая активность"), example: mt("Прогулки, тренировки 1–2 раза в неделю") },
        { value: "moderate" as const, label: mt("Умеренная активность"), example: mt("Много ходьбы, тренировки 3–4 раза в неделю") },
        { value: "high" as const, label: mt("Высокая активность"), example: mt("Работа на ногах, частые тренировки") },
    ]

    useEffect(() => {
        if (!visible || children) { showingForm.current = false; return }
        if (showingForm.current) return
        showingForm.current = true
        const firstMissing = [0, 1, 2, 3, 4].find(index => !!mentorStepError(value, index)) ?? 4
        setStep(firstMissing); progress.setValue(firstMissing)
    }, [visible, children, value, progress])
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
        const missing = [0, 1, 2, 3, 4].find(index => index > step && !!mentorStepError(value, index))
        if (missing !== undefined) go(missing)
        else { Keyboard.dismiss(); void onSave() }
    }

    const field = (label: string, fieldName: "age" | "height" | "weight" | "targetWeight", unit: string, active: boolean) => <View style={styles.field}>
        <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
        <View style={[styles.inputWrap, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <TextInput accessibilityLabel={label} value={value[fieldName]} onChangeText={text => change({ [fieldName]: text })}
                editable={active && !saving} keyboardType={fieldName === "age" ? "number-pad" : "decimal-pad"} maxLength={7}
                keyboardAppearance={colors.surface === "#FFFFFF" ? "light" : "dark"} selectionColor={colors.greenBright}
                style={[styles.input, { color: colors.text }]} />
            <Text style={[styles.unit, { color: colors.muted }]}>{unit}</Text>
        </View>
    </View>
    const choice = (label: string, selected: boolean, onPress: () => void, disabled: boolean, icon?: "progress" | "workout" | "smile" | "adjust", example?: string) => <Pressable
        key={label} accessibilityRole="radio" accessibilityLabel={label} accessibilityState={{ checked: selected, disabled }} disabled={disabled} onPress={onPress}
        style={({ pressed }) => [styles.choice, { borderColor: selected ? colors.greenBright : colors.border, backgroundColor: selected ? colors.mint : colors.surface, opacity: pressed ? 0.72 : 1 }]}>
        {icon ? <MentorIcon name={icon} size={26} color={colors.green} /> : null}
        <View style={{ flex: 1, gap: 4 }}><Text style={[styles.choiceLabel, { color: colors.text }]}>{label}</Text>{example ? <Text style={[styles.example, { color: colors.muted }]}>{example}</Text> : null}</View>
        <View style={[styles.radio, { borderColor: selected ? colors.greenBright : colors.border }]}>{selected ? <View style={[styles.radioDot, { backgroundColor: colors.greenBright }]} /> : null}</View>
    </Pressable>

    return <Modal visible={visible} animationType={reducedMotion ? "none" : "fade"} presentationStyle="fullScreen" onRequestClose={children ? onClose : back}>
        {children ? <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={[styles.screen, { backgroundColor: colors.surface, paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, 12) }]}>{children}</KeyboardAvoidingView> :
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={[styles.screen, { backgroundColor: colors.surface, paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, 12) }]}>
            <MentorFlowHeader section={mt("Обязательная часть")} step={step} total={5} onBack={step ? back : undefined} onClose={onClose} busy={saving} />
            <View testID="mentor-onboarding-transition" onLayout={event => setWidth(event.nativeEvent.layout.width)} style={styles.viewport}>
                {[0, 1, 2, 3, 4].map(index => {
                    const active = step === index
                    const disabled = !active || saving
                    return <Animated.View key={index} testID={`mentor-onboarding-step-${index + 1}`} pointerEvents={active ? "auto" : "none"}
                        accessibilityElementsHidden={!active} importantForAccessibility={active ? "auto" : "no-hide-descendants"} aria-hidden={!active}
                        style={[styles.pane, { opacity: width ? progress.interpolate({ inputRange: [index - 1, index, index + 1], outputRange: [0.25, 1, 0.25], extrapolate: "clamp" }) : active ? 1 : 0,
                            transform: [{ translateX: progress.interpolate({ inputRange: [0, 4], outputRange: [index * width, (index - 4) * width] }) }] }]}>
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
                            {index === 3 ? <View accessibilityRole="radiogroup" style={styles.choices}>{mentorActivityChoices.map(item => choice(item.label, value.activity === item.value, () => change({ activity: item.value }), disabled, undefined, item.example))}</View> : null}
                            {index === 4 ? <View style={styles.groups}>
                                <View style={[styles.targetCard, { backgroundColor: colors.soft, borderColor: colors.border }]}>
                                    <TextInput accessibilityLabel={mt("Желаемый вес")} value={value.targetWeight} onChangeText={targetWeight => change({ targetWeight })} editable={!disabled} placeholder="—" placeholderTextColor={colors.muted} keyboardType="decimal-pad" maxLength={7} selectionColor={colors.greenBright} style={[styles.targetInput, { color: colors.green }]} />
                                    <Text style={[styles.targetUnit, { color: colors.muted }]}>{mt("кг")}</Text>
                                </View>
                            </View> : null}
                        </ScrollView>
                    </Animated.View>
                })}
            </View>
            <View style={styles.footer}>
                {validation || error ? <Text accessibilityRole="alert" style={styles.error}>{validation || error}</Text> : null}
                <MentorFlowButton testID="mentor-onboarding-next" label={mt(step === 4 ? "Рассчитать КБЖУ" : "Дальше")} onPress={next} busy={saving} />
            </View>
        </KeyboardAvoidingView>}
    </Modal>
}

const styles = StyleSheet.create({
    screen: { flex: 1 },
    viewport: { flex: 1, minHeight: 0, overflow: "hidden" }, pane: { ...StyleSheet.absoluteFillObject },
    stepBody: { paddingHorizontal: 24, paddingTop: 28, paddingBottom: 24, width: "100%", maxWidth: 560, alignSelf: "center" },
    title: { ...flowStyles.title, marginBottom: 28 }, choices: { gap: 13 }, groups: { gap: 28 }, field: { gap: 10 }, label: { fontSize: 17, fontWeight: "600" },
    choice: { flexGrow: 1, flexBasis: 0, minHeight: 76, paddingHorizontal: 18, paddingVertical: 18, borderWidth: 1.5, borderRadius: 18, flexDirection: "row", alignItems: "center", gap: 14 },
    choiceLabel: { fontSize: 17, lineHeight: 24, fontWeight: "600", flexShrink: 1 }, radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: "center", justifyContent: "center" }, radioDot: { width: 12, height: 12, borderRadius: 6 },
    example: { fontSize: 13, lineHeight: 19 }, targetCard: { minHeight: 160, borderRadius: 28, borderWidth: 1, padding: 24, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 12 }, targetInput: { minWidth: 120, maxWidth: "80%", fontSize: 62, fontWeight: "600", textAlign: "center", paddingVertical: 12, fontVariant: ["tabular-nums"] }, targetUnit: { fontSize: 22, alignSelf: "center" },
    inputWrap: { borderWidth: 1.5, borderRadius: 16, minHeight: 74, flexDirection: "row", alignItems: "center", paddingHorizontal: 18 }, input: { flex: 1, minWidth: 0, fontSize: 28, paddingVertical: 15 }, unit: { fontSize: 18, paddingLeft: 10 },
    customInput: { minHeight: 100, borderWidth: 1.5, borderRadius: 16, padding: 16, fontSize: 17, textAlignVertical: "top" }, sexChoices: { flexDirection: "row", gap: 10 },
    footer: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, paddingTop: 12, paddingBottom: 12, gap: 12 },
    error: { color: "#B55353", fontSize: 14, lineHeight: 20 },
})
