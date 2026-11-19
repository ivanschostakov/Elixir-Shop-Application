import { useLayoutEffect, useRef } from "react"
import { Animated, Easing, Keyboard, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { optionalMentorFields, type MentorOptionalForm } from "@/screens/chat/mentor-onboarding-data"
import { MentorFlowButton, MentorFlowHeader, flowStyles } from "@/screens/chat/mentor-onboarding-layout"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { MentorChoiceCard } from "@/screens/chat/mentor-choice-card"
import { MentorCustomAnswer } from "@/screens/chat/mentor-custom-answer"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { MentorReminderTime } from "@/screens/chat/mentor-reminder-time"

type Props = {
    value: MentorOptionalForm; onChange: (value: MentorOptionalForm) => void; step: number
    onBack: () => void; onClose: () => void; onNext: (skipped: boolean) => void; saving: boolean; editingLocked?: boolean; error: string
}

export function MentorReminderRow({ label, icon, enabled, time, busy, onToggle, onTime, detail }: { label: string; icon: MentorQuestionIconName; enabled: boolean; time: string; busy: boolean; onToggle: (value: boolean) => void; onTime: (value: string) => void; detail?: string }) {
    const colors = useMentorPalette()
    return <View style={[styles.reminder, { borderBottomColor: colors.border }]}>
        <View style={[styles.reminderIcon, { backgroundColor: enabled ? colors.mint : colors.soft }]}><MentorQuestionIcon name={icon} size={24} color={enabled ? colors.green : colors.muted} /></View>
        <View style={styles.reminderCopy}>
            <Text style={[styles.reminderLabel, { color: colors.text }]}>{label}</Text>
            {detail ? <Text style={[styles.reminderDetail, { color: colors.muted }]}>{detail}</Text> : null}
        </View>
        <View style={styles.reminderControls}>
            <Switch accessibilityLabel={label} disabled={busy} value={enabled} onValueChange={onToggle} trackColor={{ false: colors.border, true: colors.greenBright }} thumbColor="#FFFFFF" ios_backgroundColor={colors.border} style={styles.reminderSwitch} />
            <MentorReminderTime label={label} value={time} onChange={onTime} disabled={busy} />
        </View>
    </View>
}

export function MentorOptionalOnboarding({ value, onChange, step, onBack, onClose, onNext, saving, editingLocked = saving, error }: Props) {
    useLanguage()
    const colors = useMentorPalette()
    const reduced = useChatReducedMotion()
    const progress = useRef(new Animated.Value(step)).current
    const titles = [mt("Расскажите о своих привычках"), mt("Что вы любите есть?"), mt("Есть ли ограничения в питании?"), mt("Как вы тренируетесь?"), mt("Где вам удобно тренироваться?"), mt("Когда вам напоминать?")]
    const placeholders = [mt("Работа, режим дня, сон и привычки"), mt("Любимые продукты и привычные блюда"), mt("Аллергии, непереносимости, исключённые продукты"), mt("Чем занимаетесь и как часто"), mt("Дом или зал, оборудование и доступное время")]
    const experienceChoices = [
        { id: "beginner" as const, title: mt("Начинаю"), description: mt("Регулярного опыта пока нет или возвращаюсь после перерыва."), icon: "beginner" as const },
        { id: "occasional" as const, title: mt("Время от времени"), description: mt("Занимаюсь без постоянного графика, обычно 1–2 раза в неделю."), icon: "occasional" as const },
        { id: "regular" as const, title: mt("Тренируюсь регулярно"), description: mt("Есть привычный режим и опыт нескольких тренировок в неделю."), icon: "regular" as const },
        { id: "custom" as const, title: mt("Свой вариант"), description: mt("Расскажу о своих занятиях и частоте тренировок."), icon: "custom" as const },
    ]
    const conditionsChoices = [
        { id: "home" as const, title: mt("Дома"), description: mt("С весом тела или своим оборудованием."), icon: "home" as const },
        { id: "gym" as const, title: mt("В зале"), description: mt("Доступны тренажёры, свободные веса и инвентарь."), icon: "gym" as const },
        { id: "mixed" as const, title: mt("Дома и в зале"), description: mt("Чередую домашние занятия и походы в зал."), icon: "mixed" as const },
        { id: "custom" as const, title: mt("Свой вариант"), description: mt("Улица, бассейн, студия или другое место."), icon: "custom" as const },
    ]
    useLayoutEffect(() => {
        Keyboard.dismiss()
        if (reduced) { progress.setValue(step); return }
        const animation = Animated.timing(progress, { toValue: step, duration: 170, easing: Easing.bezier(0.2, 0, 0, 1), useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [step, reduced, progress])
    const change = (patch: Partial<MentorOptionalForm>) => onChange({ ...value, ...patch })
    return <View testID="mentor-optional-onboarding" style={flowStyles.fill}>
        <MentorFlowHeader section={mt("Дополнительно")} step={step} total={6} onBack={onBack} onClose={onClose} busy={saving} />
        <View style={[flowStyles.fill, { overflow: "hidden" }]}>
            {[0, 1, 2, 3, 4, 5].map(index => <Animated.View key={index} testID={`mentor-optional-step-${index + 1}`} pointerEvents={step === index ? "auto" : "none"} accessibilityElementsHidden={step !== index} importantForAccessibility={step === index ? "auto" : "no-hide-descendants"}
                style={[StyleSheet.absoluteFillObject, { opacity: progress.interpolate({ inputRange: [index - 1, index, index + 1], outputRange: [0, 1, 0], extrapolate: "clamp" }), transform: [{ translateX: progress.interpolate({ inputRange: [index - 1, index, index + 1], outputRange: [18, 0, -18], extrapolate: "clamp" }) }] }]}>
                <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={flowStyles.body}>
                    <Text accessibilityRole="header" style={[flowStyles.title, { color: colors.text }]}>{titles[index]}</Text>
                    {index < 3 ? <>
                        <TextInput accessibilityLabel={titles[index]} placeholder={placeholders[index]} placeholderTextColor={colors.muted} value={value[optionalMentorFields[index]]} onChangeText={text => change({ [optionalMentorFields[index]]: text })} multiline textAlignVertical="top" maxLength={2000} editable={!editingLocked && step === index} selectionColor={colors.greenBright} style={[styles.textarea, { color: colors.text, backgroundColor: colors.soft, borderColor: colors.border }]} />
                    </> : index === 3 || index === 4 ? (index === 3 ? value.experienceChoice : value.conditionsChoice) === "custom" ?
                        <MentorCustomAnswer label={mt("Свой вариант")} placeholder={placeholders[index]} value={index === 3 ? value.experienceCustom : value.conditionsCustom}
                            onChange={text => index === 3 ? change({ experienceCustom: text }) : change({ conditionsCustom: text })}
                            onCancel={() => index === 3 ? change({ experienceChoice: null }) : change({ conditionsChoice: null })} disabled={editingLocked || step !== index} /> :
                        <View accessibilityRole="radiogroup" style={styles.choices}>
                            {(index === 3 ? experienceChoices : conditionsChoices).map(item => <MentorChoiceCard key={item.id} title={item.title} description={item.description} icon={item.icon} selected={(index === 3 ? value.experienceChoice : value.conditionsChoice) === item.id} disabled={editingLocked || step !== index}
                                onPress={() => index === 3 ? change({ experienceChoice: item.id as MentorOptionalForm["experienceChoice"] }) : change({ conditionsChoice: item.id as MentorOptionalForm["conditionsChoice"] })} />)}
                        </View>
                    : <View>
                        <MentorReminderRow label={mt("Отметить вес")} detail={mt("Следите за динамикой веса.")} icon="weight" enabled={value.weightEnabled} time={value.weightTime} busy={editingLocked || step !== index} onToggle={weightEnabled => change({ weightEnabled })} onTime={weightTime => change({ weightTime })} />
                        <MentorReminderRow label={mt("Подвести итог дня")} detail={mt("Питание, активность и самочувствие.")} icon="summary" enabled={value.dailyEnabled} time={value.dailyTime} busy={editingLocked || step !== index} onToggle={dailyEnabled => change({ dailyEnabled })} onTime={dailyTime => change({ dailyTime })} />
                        <MentorReminderRow label={mt("Итоги недели")} detail={mt("Обзор прогресса каждый понедельник.")} icon="weekly" enabled={value.weeklyEnabled} time={value.weeklyTime} busy={editingLocked || step !== index} onToggle={weeklyEnabled => change({ weeklyEnabled })} onTime={weeklyTime => change({ weeklyTime })} />
                    </View>}
                </ScrollView>
            </Animated.View>)}
        </View>
        <View style={flowStyles.footer}>
            {error ? <Text accessibilityRole="alert" style={flowStyles.error}>{error}</Text> : null}
            <MentorFlowButton label={mt(step === 5 ? "Готово" : "Дальше")} onPress={() => onNext(false)} busy={saving} />
            <MentorFlowButton label={mt("Пропустить")} onPress={() => onNext(true)} secondary disabled={saving} />
        </View>
    </View>
}

const styles = StyleSheet.create({
    textarea: { minHeight: 196, borderRadius: 22, borderWidth: 1, padding: 19, fontSize: 18, lineHeight: 28 },
    choices: { gap: 12 },
    reminder: { flexDirection: "row", alignItems: "flex-start", gap: 12, paddingVertical: 20, borderBottomWidth: StyleSheet.hairlineWidth }, reminderIcon: { width: 38, height: 38, borderRadius: 13, alignItems: "center", justifyContent: "center" },
    reminderCopy: { flex: 1, minWidth: 0, gap: 6, paddingTop: 6 }, reminderLabel: { fontSize: 17, lineHeight: 24, fontWeight: "600" },
    reminderControls: { alignItems: "flex-end", gap: 10 }, reminderSwitch: { alignSelf: "flex-end" }, reminderDetail: { fontSize: 13, lineHeight: 19 },
})
