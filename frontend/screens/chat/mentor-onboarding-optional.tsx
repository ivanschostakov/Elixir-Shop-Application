import { useEffect, useRef, useState } from "react"
import { Animated, Easing, Keyboard, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native"
import { Picker } from "@react-native-picker/picker"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { optionalMentorFields, type MentorOptionalForm } from "@/screens/chat/mentor-onboarding-data"
import { MentorFlowButton, MentorFlowHeader, flowStyles } from "@/screens/chat/mentor-onboarding-layout"
import { MentorIcon, useMentorPalette, type MentorIconName } from "@/screens/chat/mentor-ui"

type Props = {
    value: MentorOptionalForm; onChange: (value: MentorOptionalForm) => void; step: number
    onBack: () => void; onClose: () => void; onNext: (skipped: boolean) => void; saving: boolean; error: string
}

function ReminderTime({ label, value, onChange, disabled }: { label: string; value: string; onChange: (value: string) => void; disabled: boolean }) {
    const colors = useMentorPalette()
    const [open, setOpen] = useState(false)
    const [hour, minute] = value.split(":")
    return <View style={styles.timeContainer}>
        <Pressable accessibilityRole="button" accessibilityLabel={`${label}: ${value}`} accessibilityState={{ expanded: open, disabled }} disabled={disabled} onPress={() => setOpen(!open)} style={[styles.timeButton, { borderColor: colors.border, backgroundColor: colors.surface }]}>
            <Text style={[styles.time, { color: colors.text }]}>{value}</Text><Text style={{ color: colors.muted }}>⌄</Text>
        </Pressable>
        {open ? <View style={[styles.pickers, { backgroundColor: colors.soft, borderColor: colors.border }]}>
            <Picker accessibilityLabel={mt("Часы")} enabled={!disabled} selectedValue={hour} onValueChange={next => onChange(`${next}:${minute}`)} style={styles.picker} itemStyle={[styles.pickerItem, { color: colors.text }]}>
                {Array.from({ length: 24 }, (_, i) => String(i).padStart(2, "0")).map(item => <Picker.Item key={item} label={item} value={item} color={colors.text} />)}
            </Picker>
            <Text style={[styles.time, { color: colors.text }]}>:</Text>
            <Picker accessibilityLabel={mt("Минуты")} enabled={!disabled} selectedValue={minute} onValueChange={next => onChange(`${hour}:${next}`)} style={styles.picker} itemStyle={[styles.pickerItem, { color: colors.text }]}>
                {Array.from({ length: 60 }, (_, i) => String(i).padStart(2, "0")).map(item => <Picker.Item key={item} label={item} value={item} color={colors.text} />)}
            </Picker>
        </View> : null}
    </View>
}

function ReminderRow({ label, icon, enabled, time, busy, onToggle, onTime, children }: { label: string; icon: MentorIconName; enabled: boolean; time: string; busy: boolean; onToggle: (value: boolean) => void; onTime: (value: string) => void; children?: React.ReactNode }) {
    const colors = useMentorPalette()
    return <View style={[styles.reminder, { borderBottomColor: colors.border }]}>
        <View style={[styles.reminderIcon, { backgroundColor: enabled ? colors.mint : colors.soft }]}><MentorIcon name={icon} size={24} color={enabled ? colors.green : colors.muted} /></View>
        <View style={styles.reminderCopy}>
            <View style={styles.reminderHeader}><Text style={[styles.reminderLabel, { color: colors.text }]}>{label}</Text>
                <Switch accessibilityLabel={label} disabled={busy} value={enabled} onValueChange={onToggle} trackColor={{ false: colors.border, true: colors.greenBright }} thumbColor="#FFFFFF" ios_backgroundColor={colors.border} />
            </View>
            {enabled ? <><ReminderTime label={label} value={time} onChange={onTime} disabled={busy} />{children}</> : null}
        </View>
    </View>
}

export function MentorOptionalOnboarding({ value, onChange, step, onBack, onClose, onNext, saving, error }: Props) {
    useLanguage()
    const colors = useMentorPalette()
    const reduced = useChatReducedMotion()
    const [width, setWidth] = useState(0)
    const progress = useRef(new Animated.Value(step)).current
    const titles = [mt("Как проходит ваш день?"), mt("Что вы любите есть?"), mt("Есть ли ограничения в питании?"), mt("Как вы тренируетесь?"), mt("Где вам удобно тренироваться?"), mt("Когда вам напоминать?")]
    const placeholders = [mt("Работа, режим дня, сон и привычки"), mt("Любимые продукты и привычные блюда"), mt("Аллергии, непереносимости, исключённые продукты"), mt("Чем занимаетесь и как часто"), mt("Дом или зал, оборудование и доступное время")]
    const weekdays = [mt("Пн"), mt("Вт"), mt("Ср"), mt("Чт"), mt("Пт"), mt("Сб"), mt("Вс")]
    useEffect(() => {
        Keyboard.dismiss()
        if (reduced || !width) { progress.setValue(step); return }
        const animation = Animated.timing(progress, { toValue: step, duration: 320, easing: Easing.bezier(0.22, 1, 0.36, 1), useNativeDriver: true })
        animation.start()
        return () => animation.stop()
    }, [step, width, reduced, progress])
    const change = (patch: Partial<MentorOptionalForm>) => onChange({ ...value, ...patch })
    const shortcuts = (index: number) => index === 2 ? [mt("Нет ограничений")] : index === 3 ? [mt("Начинаю"), mt("Иногда"), mt("Регулярно")] : index === 4 ? [mt("Дома"), mt("В зале"), mt("Дома и в зале")] : []
    return <View testID="mentor-optional-onboarding" style={flowStyles.fill}>
        <MentorFlowHeader section={mt("Дополнительно")} step={step} total={6} onBack={onBack} onClose={onClose} busy={saving} />
        <View style={[flowStyles.fill, { overflow: "hidden" }]} onLayout={event => setWidth(event.nativeEvent.layout.width)}>
            {[0, 1, 2, 3, 4, 5].map(index => <Animated.View key={index} testID={`mentor-optional-step-${index + 1}`} pointerEvents={step === index ? "auto" : "none"} accessibilityElementsHidden={step !== index} importantForAccessibility={step === index ? "auto" : "no-hide-descendants"}
                style={[StyleSheet.absoluteFillObject, { opacity: !width ? step === index ? 1 : 0 : progress.interpolate({ inputRange: [index - 1, index, index + 1], outputRange: [0.2, 1, 0.2], extrapolate: "clamp" }), transform: [{ translateX: progress.interpolate({ inputRange: [0, 5], outputRange: [index * width, (index - 5) * width] }) }] }]}>
                <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={flowStyles.body}>
                    <Text accessibilityRole="header" style={[flowStyles.title, { color: colors.text }]}>{titles[index]}</Text>
                    {index < 5 ? <>
                        {shortcuts(index).length ? <View style={styles.shortcuts}>{shortcuts(index).map(text => <Pressable key={text} accessibilityRole="button" accessibilityState={{ selected: value[optionalMentorFields[index]] === text, disabled: saving || step !== index }} disabled={saving || step !== index} onPress={() => change({ [optionalMentorFields[index]]: text })} style={[styles.shortcut, { borderColor: value[optionalMentorFields[index]] === text ? colors.greenBright : colors.border, backgroundColor: value[optionalMentorFields[index]] === text ? colors.mint : colors.surface }]}><Text style={{ color: colors.green, fontSize: 14, fontWeight: "500" }}>{text}</Text></Pressable>)}</View> : null}
                        <TextInput accessibilityLabel={titles[index]} placeholder={placeholders[index]} placeholderTextColor={colors.muted} value={value[optionalMentorFields[index]]} onChangeText={text => change({ [optionalMentorFields[index]]: text })} multiline textAlignVertical="top" maxLength={2000} editable={!saving && step === index} selectionColor={colors.greenBright} style={[styles.textarea, { color: colors.text, backgroundColor: colors.soft, borderColor: colors.border }]} />
                    </> : <View>
                        <ReminderRow label={mt("Утром отметить вес")} icon="scale" enabled={value.weightEnabled} time={value.weightTime} busy={saving || step !== index} onToggle={weightEnabled => change({ weightEnabled })} onTime={weightTime => change({ weightTime })} />
                        <ReminderRow label={mt("Вечером подвести итог")} icon="book" enabled={value.dailyEnabled} time={value.dailyTime} busy={saving || step !== index} onToggle={dailyEnabled => change({ dailyEnabled })} onTime={dailyTime => change({ dailyTime })} />
                        <ReminderRow label={mt("Итоги недели")} icon="calendar" enabled={value.weeklyEnabled} time={value.weeklyTime} busy={saving || step !== index} onToggle={weeklyEnabled => change({ weeklyEnabled })} onTime={weeklyTime => change({ weeklyTime })}>
                            <View accessibilityRole="radiogroup" style={styles.weekdays}>{weekdays.map((day, dayIndex) => <Pressable key={dayIndex} accessibilityRole="radio" accessibilityLabel={day} accessibilityState={{ checked: value.weeklyDay === dayIndex, disabled: saving || step !== index }} disabled={saving || step !== index} onPress={() => change({ weeklyDay: dayIndex })} style={[styles.weekday, { backgroundColor: value.weeklyDay === dayIndex ? colors.greenBright : colors.soft }]}><Text style={{ fontSize: 12, fontWeight: "600", color: value.weeklyDay === dayIndex ? "#FFFFFF" : colors.muted }}>{day}</Text></Pressable>)}</View>
                        </ReminderRow>
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
    shortcuts: { flexDirection: "row", flexWrap: "wrap", gap: 8 }, shortcut: { minHeight: 44, borderRadius: 22, borderWidth: 1, paddingHorizontal: 16, paddingVertical: 11 },
    reminder: { flexDirection: "row", alignItems: "flex-start", gap: 12, paddingVertical: 20, borderBottomWidth: StyleSheet.hairlineWidth }, reminderIcon: { width: 42, height: 42, borderRadius: 15, alignItems: "center", justifyContent: "center" },
    reminderCopy: { flex: 1, gap: 13 }, reminderHeader: { flexDirection: "row", alignItems: "center", gap: 10, minHeight: 36 }, reminderLabel: { flex: 1, fontSize: 17, lineHeight: 24, fontWeight: "600" },
    timeContainer: { gap: 10 }, timeButton: { alignSelf: "flex-start", minWidth: 136, minHeight: 48, paddingHorizontal: 16, borderWidth: 1, borderRadius: 14, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 20 }, time: { fontSize: 22, fontWeight: "600", fontVariant: ["tabular-nums"] },
    pickers: { flexDirection: "row", alignItems: "center", borderRadius: 16, borderWidth: 1, overflow: "hidden" }, picker: { flex: 1, minWidth: 0 }, pickerItem: { fontSize: 22, height: 130 },
    weekdays: { flexDirection: "row", flexWrap: "wrap", gap: 4 }, weekday: { minWidth: 32, minHeight: 40, borderRadius: 11, alignItems: "center", justifyContent: "center", paddingHorizontal: 7 },
})
