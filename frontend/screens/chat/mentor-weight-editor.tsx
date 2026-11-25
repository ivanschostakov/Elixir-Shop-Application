import { useRef, useState } from "react"
import { ActivityIndicator, Keyboard, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorNumber, mentorText as mt } from "@/i18n/mentor-translations"
import { useTheme } from "@/providers/theme-provider"
import type { useCompanion } from "@/screens/chat/companion"
import { CompanionActionCancelled } from "@/screens/chat/companion-consent"
import { companionCalendarDay } from "@/screens/chat/companion-timezones"
import { weightPoints } from "@/screens/chat/mentor-data"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { mentorHomeData } from "@/screens/chat/mentor-home-data"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { wellbeingDateLabel } from "@/screens/chat/mentor-wellbeing-data"
import { requestKey, type CompanionAction } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"

const ticks = Array.from({ length: 21 }, (_, index) => index - 10)
const validWeight = (text: string) => /^(?:\d+[.,]?\d*|[.,]\d+)$/.test(text.trim()) && Number(text.replace(",", ".")) > 0 && Number(text.replace(",", ".")) <= 500
const steppedWeight = (kg: number, steps: number) => Math.max(1, Math.min(5000, Math.round(kg * 10) + steps)) / 10

function WeightRuler({ value, onChange, disabled }: { value: number | null; onChange: (kg: number) => void; disabled: boolean }) {
    const colors = useMentorPalette()
    const drag = useRef({ x: 0, kg: 0 }), width = useRef(280)
    const active = value !== null && !disabled
    const center = Math.round((value ?? 0) * 10)
    return <View style={styles.ruler} onLayout={e => { width.current = e.nativeEvent.layout.width }}
        accessible accessibilityRole="adjustable" accessibilityLabel={mt("Вес, кг")} accessibilityState={{ disabled: !active }}
        accessibilityValue={value === null ? undefined : { text: mt("{0} кг", [value]) }}
        accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
        onAccessibilityAction={e => { if (active) onChange(steppedWeight(value, e.nativeEvent.actionName === "increment" ? 1 : -1)) }}
        onStartShouldSetResponder={() => active} onResponderGrant={e => { drag.current = { x: e.nativeEvent.pageX, kg: value ?? 0 } }}
        onResponderMove={e => { if (active) onChange(steppedWeight(drag.current.kg, Math.round((drag.current.x - e.nativeEvent.pageX) / (width.current / ticks.length)))) }}>
        {ticks.map(offset => {
            const major = (center + offset) % 5 === 0
            const outside = value !== null && (center + offset <= 0 || center + offset > 5000)
            const labeled = value !== null && !outside && (offset === 0 || (major && Math.abs(offset) >= 3 && Math.abs(offset) <= 8))
            return <View key={offset} style={styles.tickCell}>
                <View style={[styles.tick, { height: offset === 0 ? 32 : major ? 22 : 12, width: offset === 0 ? 3 : 1.5, backgroundColor: offset === 0 ? colors.green : colors.muted, opacity: outside ? 0 : offset === 0 ? 1 : major ? 0.65 : 0.35 }]} />
                {labeled ? <Text allowFontScaling={false} style={[styles.tickLabel, { color: offset === 0 ? colors.green : colors.muted }]}>{mentorNumber((center + offset) / 10)}</Text> : null}
            </View>
        })}
    </View>
}

export function MentorWeightEditor({ controller: c, onClose, onSaved }: { controller: ReturnType<typeof useCompanion>; onClose: () => void; onSaved: () => void }) {
    const colors = useMentorPalette(), { isDark } = useTheme(), insets = useSafeAreaInsets()
    const original = c.editor?.entry, source = original?.data ?? c.editor?.proposal?.entry
    const last = c.state?.mentor?.latest_weight
    const entries = c.state?.entries ?? []
    const history = weightPoints(last ? [...entries.filter(entry => entry.id !== last.id), last] : entries).reverse().slice(0, 3)
    const [weight, setWeight] = useState(() => String(source?.weight_kg ?? history[0]?.value ?? ""))
    const [note, setNote] = useState(source?.note ?? ""), [showNote, setShowNote] = useState(!!source?.note)
    const [saving, setSaving] = useState(false), [error, setError] = useState("")
    const input = useRef<TextInput>(null), locked = useRef(false)
    const pending = useRef<{ signature: string; action: CompanionAction } | null>(null)
    const valid = validWeight(weight), kg = valid ? Number(weight.replace(",", ".")) : null
    const busy = saving || c.busy
    const edit = (text: string) => { setWeight(text); setError("") }
    const step = (delta: number) => { if (kg != null) edit(String(steppedWeight(kg, delta))) }
    const dayOf = (at: string) => wellbeingDateLabel(companionCalendarDay(at, c.clock))
    const instant = () => mentorHomeData(c.state, c.clock).instant
    const save = async () => {
        if (locked.current || c.busy || !valid) return
        locked.current = true; setSaving(true); setError(""); Keyboard.dismiss()
        try {
            const normalized = weight.trim().replace(",", ".")
            const signature = JSON.stringify([normalized, note])
            if (pending.current?.signature !== signature) {
                pending.current = { signature, action: { kind: "entry", request_key: requestKey(), resource_id: original?.id, expected_version: original?.version,
                    entry: { ...source, kind: "weight", occurred_at: original?.occurred_at ?? instant(), weight_kg: normalized, note } } }
            }
            await c.perform(pending.current.action)
            onSaved()
        } catch (failure) {
            if (!(failure instanceof CompanionActionCancelled)) setError(getErrorMessage(failure))
        } finally { locked.current = false; setSaving(false) }
    }
    const tint = isDark ? "#21392E" : "#EBF4ED"
    const validation = weight.trim() && !valid ? mt("Укажите текущий вес больше 0 и не больше 500 кг.") : ""
    return <View style={[styles.screen, { paddingTop: insets.top, backgroundColor: colors.surface }]}>
        <MentorHomeHeader title={mt(original ? "Изменить запись" : "Новое взвешивание")} onBack={() => { if (!busy) onClose() }} />
        <ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={styles.content}>
            <Text style={[styles.date, { color: colors.muted }]}>{original ? dayOf(original.occurred_at) : mt("Сегодня, {0}", [dayOf(instant())])}</Text>
            <View style={[styles.panel, { backgroundColor: tint }]}>
                <View style={styles.panelHeader}><MentorQuestionIcon name="weight" color={colors.green} size={24} /><Text style={[styles.heading, { color: colors.text }]}>{mt("Вес тела")}</Text>
                    <Pressable accessibilityRole="button" accessibilityLabel={mt("Ввести вес вручную")} disabled={busy} style={styles.iconButton} onPress={() => input.current?.focus()}><MentorQuestionIcon name="custom" color={colors.green} size={21} /></Pressable>
                </View>
                <View style={styles.valueRow}>
                    <Pressable accessibilityRole="button" accessibilityLabel={mt("Уменьшить вес на 0,1 кг")} disabled={busy || kg == null || kg <= 0.1} onPress={() => step(-1)} style={[styles.step, { backgroundColor: colors.surface, opacity: busy || kg == null || kg <= 0.1 ? 0.45 : 1 }]}><Text style={[styles.sign, { color: colors.green }]}>−</Text></Pressable>
                    <View style={styles.reading}>
                        <TextInput ref={input} accessibilityLabel={mt("Вес, кг")} keyboardType="decimal-pad" selectTextOnFocus editable={!busy} value={weight}
                            placeholder="—" onChangeText={edit} maxLength={20}
                            selectionColor={colors.greenBright} placeholderTextColor={colors.muted} style={[styles.number, { color: colors.text, fontSize: weight.length > 5 ? 32 : 46 }]} />
                        <Text style={[styles.unit, { color: colors.green }]}>{mt("кг")}</Text>
                    </View>
                    <Pressable accessibilityRole="button" accessibilityLabel={mt("Увеличить вес на 0,1 кг")} disabled={busy || kg == null || kg >= 500} onPress={() => step(1)} style={[styles.step, { backgroundColor: colors.surface, opacity: busy || kg == null || kg >= 500 ? 0.45 : 1 }]}><Text style={[styles.sign, { color: colors.green }]}>+</Text></Pressable>
                </View>
                <WeightRuler value={kg} onChange={value => edit(String(value))} disabled={busy} />
                {kg == null ? <Pressable accessibilityRole="button" disabled={busy} onPress={() => input.current?.focus()} style={styles.manualAction}>
                    <Text style={[styles.hint, { color: colors.green }]}>{mt("Ввести вес вручную")}</Text>
                </Pressable> : <Text style={[styles.hint, { color: colors.muted }]}>{mt("Шаг 0,1 кг")}</Text>}
            </View>
            {validation ? <Text accessibilityRole="alert" style={{ color: colors.text }}>{validation}</Text> : null}
            {history.length > 0 ? <View><Text accessibilityRole="header" style={[styles.historyTitle, { color: colors.text }]}>{mt("Последние измерения")}</Text>
                {history.map(item => <View key={item.id} style={[styles.historyRow, { borderBottomColor: colors.border }]}><Text style={[styles.label, { color: colors.muted }]}>{dayOf(item.date)}</Text><Text style={[styles.historyWeight, { color: colors.text }]}>{mt("{0} кг", [mentorNumber(item.value, { maximumFractionDigits: 3 })])}</Text></View>)}
            </View> : null}
            {showNote ? <TextInput accessibilityLabel={mt("Заметка по желанию")} placeholder={mt("Заметка по желанию")} placeholderTextColor={colors.muted} multiline editable={!busy} maxLength={4000}
                value={note} onChangeText={setNote} style={[styles.note, { backgroundColor: colors.input, color: colors.text }]} /> :
                <Pressable accessibilityRole="button" disabled={busy} onPress={() => setShowNote(true)} style={[styles.noteAction, { backgroundColor: colors.input }]}><MentorQuestionIcon name="custom" size={18} color={colors.green} /><Text style={[styles.label, { color: colors.text }]}>{mt("Добавить заметку")}</Text></Pressable>}
            {error ? <Text accessibilityRole="alert" style={[styles.label, { color: colors.text }]}>{error}</Text> : null}
        </ScrollView>
        <View style={[styles.footer, { paddingBottom: Math.max(12, insets.bottom) }]}>
            <Pressable accessibilityRole="button" accessibilityState={{ disabled: busy || !valid, busy }} disabled={busy || !valid} onPress={() => void save()}
                style={({ pressed }) => [styles.save, { backgroundColor: isDark ? "#2B7552" : "#206647", opacity: busy || !valid ? 0.5 : pressed ? 0.75 : 1 }]}>
                {saving ? <ActivityIndicator color="#FFFFFF" /> : null}<Text style={styles.saveLabel}>{mt("Сохранить вес")}</Text>
            </Pressable>
        </View>
    </View>
}

const styles = StyleSheet.create({
    screen: { flex: 1 }, content: { width: "100%", maxWidth: 560, alignSelf: "center", padding: 20, gap: 20 },
    date: { fontSize: 16, fontWeight: "500" }, panel: { borderRadius: 24, padding: 18, gap: 10 },
    panelHeader: { flexDirection: "row", alignItems: "center", gap: 9 }, heading: { flex: 1, fontSize: 18, fontWeight: "700" },
    iconButton: { width: 44, height: 44, alignItems: "center", justifyContent: "center" }, valueRow: { flexDirection: "row", alignItems: "center", gap: 6, paddingVertical: 8 },
    step: { width: 44, height: 44, borderRadius: 22, justifyContent: "center", alignItems: "center" }, sign: { fontSize: 28, lineHeight: 32, fontWeight: "500" },
    reading: { flex: 1, minWidth: 0, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 4 },
    number: { minWidth: 50, maxWidth: "82%", padding: 0, fontSize: 46, fontWeight: "700", letterSpacing: -1.5, fontVariant: ["tabular-nums"], textAlign: "center" },
    unit: { fontSize: 19, fontWeight: "600" }, ruler: { height: 62, flexDirection: "row" },
    tickCell: { flex: 1, height: 38, alignItems: "center", justifyContent: "center" }, tick: { borderRadius: 2 },
    tickLabel: { position: "absolute", top: 38, width: 46, textAlign: "center", fontSize: 12, fontVariant: ["tabular-nums"] },
    manualAction: { minHeight: 44, alignItems: "center", justifyContent: "center" },
    hint: { fontSize: 13, textAlign: "center" }, historyTitle: { fontSize: 20, fontWeight: "700", marginBottom: 4 },
    historyRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", minHeight: 46, borderBottomWidth: StyleSheet.hairlineWidth },
    historyWeight: { fontSize: 17, fontWeight: "600" }, label: { fontSize: 16, lineHeight: 22 }, noteAction: { minHeight: 50, paddingHorizontal: 16, borderRadius: 14, flexDirection: "row", alignItems: "center", gap: 10 },
    note: { borderRadius: 14, minHeight: 80, padding: 14, fontSize: 16, textAlignVertical: "top" },
    footer: { width: "100%", maxWidth: 560, alignSelf: "center", paddingHorizontal: 20, paddingTop: 10 }, save: { minHeight: 54, padding: 14, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10, borderRadius: 16 }, saveLabel: { color: "#FFFFFF", fontSize: 18, fontWeight: "700" },
})
