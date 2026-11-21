import { useLayoutEffect, useRef, useState, type ReactNode } from "react"
import { Animated, Easing, Keyboard, KeyboardAvoidingView, Modal, Platform, ScrollView, StyleSheet, Text, TextInput, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { mentorStepError, type MentorForm } from "@/screens/chat/mentor-onboarding-data"
import { MentorFlowButton, MentorFlowHeader, flowStyles } from "@/screens/chat/mentor-onboarding-layout"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { MentorChoiceCard } from "@/screens/chat/mentor-choice-card"
import { MentorCustomAnswer } from "@/screens/chat/mentor-custom-answer"
import type { MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"

type Props = {
    visible: boolean; value: MentorForm; onChange: (value: MentorForm) => void
    onClose: () => void; onSave: () => Promise<void>; saving: boolean; error: string
    children?: ReactNode
    onDismiss?: () => void
    contentSafeBottom?: boolean
    contentSafeTop?: boolean
}

export function MentorOnboarding({ visible, value, onChange, onClose, onSave, saving, error, children, onDismiss, contentSafeBottom = true, contentSafeTop = true }: Props) {
    useLanguage()
    const colors = useMentorPalette()
    const insets = useSafeAreaInsets()
    const reducedMotion = useChatReducedMotion()
    const [step, setStep] = useState(0)
    const [validation, setValidation] = useState("")
    const progress = useRef(new Animated.Value(0)).current
    const showingForm = useRef(false)
    const mentorStepTitles = [mt("Какая у вас цель?"), mt("Немного о вас"), mt("Рост и текущий вес"), mt("Как проходит ваш день?"), mt("Какого веса хотите достичь?")]
    const mentorGoalChoices = [
        { value: "weight_loss" as const, label: mt("Снизить вес"), icon: "loss" as const },
        { value: "weight_gain" as const, label: mt("Набрать вес"), icon: "gain" as const },
        { value: "maintain" as const, label: mt("Поддерживать форму"), icon: "maintain" as const },
        { value: "custom" as const, label: mt("Своя цель"), icon: "custom" as const },
    ]
    const mentorActivityChoices = [
        { value: "low" as const, label: mt("Низкая активность"), icon: "sedentary" as const, example: mt("Сидячая работа или учёба, мало ходьбы. Регулярных тренировок нет.") },
        { value: "light" as const, label: mt("Лёгкая активность"), icon: "light" as const, example: mt("Ежедневные прогулки и лёгкие занятия 1–2 раза в неделю.") },
        { value: "moderate" as const, label: mt("Умеренная активность"), icon: "moderate" as const, example: mt("Много ходьбы в течение дня и тренировки 3–4 раза в неделю.") },
        { value: "high" as const, label: mt("Высокая активность"), icon: "high" as const, example: mt("Физическая работа или интенсивные тренировки почти каждый день.") },
    ]

    useLayoutEffect(() => {
        if (!visible || children) { showingForm.current = false; return }
        if (showingForm.current) return
        showingForm.current = true
        const firstMissing = [0, 1, 2, 3, 4].find(index => !!mentorStepError(value, index)) ?? 4
        setStep(firstMissing); progress.setValue(firstMissing)
    }, [visible, children, value, progress])
    const showingChildren = !!children
    useLayoutEffect(() => {
        if (!visible || reducedMotion || showingChildren) { progress.setValue(step); return }
        const animation = Animated.timing(progress, { toValue: step, duration: 170, easing: Easing.bezier(0.2, 0, 0, 1), useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [progress, reducedMotion, step, visible, showingChildren])

    const change = (patch: Partial<MentorForm>) => { setValidation(""); onChange({ ...value, ...patch }) }
    const go = (next: number) => { Keyboard.dismiss(); setValidation(""); setStep(next) }
    const back = () => { if (!saving) { if (step) go(step - 1); else onClose() } }
    const next = () => {
        const problem = mentorStepError(value, step)
        if (problem) { setValidation(problem); return }
        if (step < 4) go(step + 1)
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
    const choice = (label: string, selected: boolean, onPress: () => void, disabled: boolean, icon?: MentorQuestionIconName, example?: string) => <MentorChoiceCard key={label} title={label} description={example} selected={selected} onPress={onPress} disabled={disabled} icon={icon} />

    return <Modal visible={visible} onDismiss={onDismiss} animationType={reducedMotion ? "none" : "fade"} presentationStyle="fullScreen" onRequestClose={children ? onClose : back}>
        {children ? <View style={[styles.screen, { backgroundColor: colors.surface, paddingTop: contentSafeTop ? insets.top : 0, paddingBottom: contentSafeBottom ? Math.max(insets.bottom, 12) : 0 }]}>{children}</View> :
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={[styles.screen, { backgroundColor: colors.surface, paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, 12) }]}>
            <MentorFlowHeader section={mt("Обязательная часть")} step={step} total={5} onBack={step ? back : undefined} onClose={onClose} busy={saving} />
            <View testID="mentor-onboarding-transition" style={styles.viewport}>
                {[0, 1, 2, 3, 4].map(index => {
                    const active = step === index
                    const disabled = !active || saving
                    return <Animated.View key={index} testID={`mentor-onboarding-step-${index + 1}`} pointerEvents={active ? "auto" : "none"}
                        accessibilityElementsHidden={!active} importantForAccessibility={active ? "auto" : "no-hide-descendants"} aria-hidden={!active}
                        style={[styles.pane, { opacity: progress.interpolate({ inputRange: [index - 1, index, index + 1], outputRange: [0, 1, 0], extrapolate: "clamp" }),
                            transform: [{ translateX: progress.interpolate({ inputRange: [index - 1, index, index + 1], outputRange: [18, 0, -18], extrapolate: "clamp" }) }] }]}>
                        <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={styles.stepBody}>
                            <Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>{mentorStepTitles[index]}</Text>
                            {index === 0 ? value.goal === "custom" ? <MentorCustomAnswer label={mt("Своя цель")} placeholder={mt("Расскажите о своей цели.")} value={value.customGoal}
                                onChange={customGoal => change({ customGoal })} onCancel={() => change({ goal: null })} disabled={disabled} maxLength={500} /> :
                                <View accessibilityRole="radiogroup" style={styles.choices}>{mentorGoalChoices.map(item => choice(item.label, value.goal === item.value, () => change({ goal: item.value }), disabled, item.icon))}</View> : null}
                            {index === 1 ? <View style={styles.groups}>{field(mt("Возраст"), "age", mt("лет"), active)}<View style={styles.field}><Text style={[styles.label, { color: colors.text }]}>{mt("Пол")}</Text><View accessibilityRole="radiogroup" style={styles.sexChoices}>
                                {choice(mt("Женский"), value.sex === "female", () => change({ sex: "female" }), disabled)}
                                {choice(mt("Мужской"), value.sex === "male", () => change({ sex: "male" }), disabled)}
                            </View></View></View> : null}
                            {index === 2 ? <View style={styles.groups}>{field(mt("Рост"), "height", mt("см"), active)}{field(mt("Текущий вес"), "weight", mt("кг"), active)}</View> : null}
                            {index === 3 ? <View accessibilityRole="radiogroup" style={styles.choices}>{mentorActivityChoices.map(item => choice(item.label, value.activity === item.value, () => change({ activity: item.value }), disabled, item.icon, item.example))}</View> : null}
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
    targetCard: { minHeight: 160, borderRadius: 28, borderWidth: 1, padding: 24, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 12 }, targetInput: { minWidth: 120, maxWidth: "80%", fontSize: 62, fontWeight: "600", textAlign: "center", paddingVertical: 12, fontVariant: ["tabular-nums"] }, targetUnit: { fontSize: 22, alignSelf: "center" },
    inputWrap: { borderWidth: 1.5, borderRadius: 16, minHeight: 74, flexDirection: "row", alignItems: "center", paddingHorizontal: 18 }, input: { flex: 1, minWidth: 0, fontSize: 28, paddingVertical: 15 }, unit: { fontSize: 18, paddingLeft: 10 },
    sexChoices: { flexDirection: "row", gap: 10 },
    footer: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 24, paddingTop: 12, paddingBottom: 12, gap: 12 },
    error: { color: "#B55353", fontSize: 14, lineHeight: 20 },
})
