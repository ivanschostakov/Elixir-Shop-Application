import { useEffect, useRef, useState, type ReactNode } from "react"
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import type { useCompanion } from "@/screens/chat/companion"
import { MentorFoodEditor } from "@/screens/chat/mentor-food"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { mentorHomeData, mentorHomeNumber as number } from "@/screens/chat/mentor-home-data"
import { entryMeal, mainMeals, mealLabel, mealTotals, waterTarget } from "@/screens/chat/mentor-meals-data"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { getMealLibrary, requestKey, type CompanionEntry, type MealHabits, type MealType } from "@/services/api/companion"
import { syncPushNotifications } from "@/services/notifications/order-status-notifications"
import { getErrorMessage } from "@/utils/errors"

type Controller = ReturnType<typeof useCompanion>
export const nutritionEditorPages = new Set(["meal", "meal_group", "water", "food_help", "meal_reminders"])

function Action({ label, onPress, secondary, busy, icon }: { label: string; onPress: () => void; secondary?: boolean; busy?: boolean; icon?: MentorQuestionIconName }) {
    const colors = useMentorPalette()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={busy} onPress={onPress} style={({ pressed }) => [styles.action, { backgroundColor: secondary ? colors.soft : colors.greenBright, opacity: busy ? 0.55 : pressed ? 0.7 : 1 }]}>{busy ? <ActivityIndicator color={colors.green} /> : icon ? <MentorQuestionIcon name={icon} color={secondary ? colors.green : "#FFFFFF"} size={23} /> : null}<Text style={[styles.actionText, { color: secondary ? colors.green : "#FFFFFF" }]}>{label}</Text></Pressable>
}

function Page({ title, onBack, children }: { title: string; onBack: () => void; children: ReactNode }) {
    const colors = useMentorPalette()
    return <><MentorHomeHeader title={title} onBack={onBack} /><ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" contentContainerStyle={styles.body} style={{ backgroundColor: colors.surface }}>{children}</ScrollView></>
}

function MealGroup({ c, close }: { c: Controller; close: () => void }) {
    const colors = useMentorPalette(), editor = c.editor!
    const type = editor.mealType ?? "extra"
    const meals = mentorHomeData(c.state, c.clock).meals.filter(entry => entryMeal(entry, c.clock) === type && (!editor.mealKey || entry.data.meal_key === editor.mealKey))
    const totals = mealTotals(meals)
    const erase = (entry: CompanionEntry) => Alert.alert(mt("Удалить запись?"), entry.data.name ?? "", [{ text: mt("Отмена"), style: "cancel" }, { text: mt("Удалить"), style: "destructive", onPress: () => void c.attempt(() => c.perform({ kind: "delete_entry", resource_id: entry.id, expected_version: entry.version })) }])
    return <Page title={mealLabel(type)} onBack={close}>
        <Text style={[styles.total, { color: colors.text }]}>{number(totals.kcal)} {mt("ккал")}</Text>
        <View style={styles.macros}>{(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={[styles.macro, index > 0 && { borderLeftWidth: 1, borderLeftColor: colors.border }]}><Text style={[styles.caption, { color: colors.muted }]}>{[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]}</Text><Text style={[styles.value, { color: colors.text }]}>{number(totals[key])} {mt("г")}</Text></View>)}</View>
        <Text style={[styles.heading, { color: colors.text }]}>{mt("Блюда")}</Text>
        {!meals.length ? <Text style={[styles.caption, { color: colors.muted }]}>{mt("Пока ничего не добавлено")}</Text> : null}
        {meals.map(entry => <View key={entry.id} style={[styles.foodRow, { borderBottomColor: colors.border }]}>
            <View style={{ flex: 1, gap: 3 }}><Text style={[styles.foodName, { color: colors.text }]}>{entry.data.name}</Text>{entry.data.portion_g ? <Text style={[styles.caption, { color: colors.muted }]}>{number(entry.data.portion_g)} {mt("г")}</Text> : null}</View>
            <Text style={[styles.foodCalories, { color: colors.text }]}>{number(entry.data.nutrition?.kcal)} {mt("ккал")}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Изменить {0}", [entry.data.name ?? ""])} disabled={c.busy} onPress={() => c.setEditor({ page: "meal", entry, mealType: type, mealKey: editor.mealKey, parentMeal: true })} style={styles.iconButton}><MentorQuestionIcon name="custom" size={22} color={colors.text} /></Pressable>
            <Pressable accessibilityRole="button" accessibilityLabel={mt("Удалить {0}", [entry.data.name ?? ""])} disabled={c.busy} onPress={() => erase(entry)} style={styles.iconButton}><MentorQuestionIcon name="trash" size={22} color="#DF444A" /></Pressable>
        </View>)}
        {c.error ? <Text accessibilityRole="alert" style={{ color: colors.text }}>{c.error}</Text> : null}
        <Action label={mt("Добавить блюдо")} icon="plus" secondary onPress={() => c.setEditor({ page: "meal", mealType: type, mealKey: editor.mealKey, parentMeal: true })} />
    </Page>
}

function Water({ c, close }: { c: Controller; close: () => void }) {
    const colors = useMentorPalette()
    const [amount, setAmount] = useState("250"), [goal, setGoal] = useState(String(waterTarget(c.state))), [editingGoal, setEditingGoal] = useState(false), [error, setError] = useState("")
    const key = useRef<{ value: string; key: string; at: string } | null>(null), lock = useRef(false)
    const add = async () => {
        const ml = Number(amount)
        if (lock.current || c.busy) return
        if (!Number.isInteger(ml) || ml <= 0 || ml > 10000) { setError(mt("Укажите объём от 1 до 10 000 мл")); return }
        if (key.current?.value !== amount) key.current = { value: amount, key: requestKey(), at: new Date().toISOString() }
        lock.current = true; setError("")
        try { await c.perform({ kind: "entry", record_now: true, request_key: key.current.key, entry: { kind: "water", occurred_at: key.current.at, water_ml: ml } }); close() }
        catch (e) { setError(getErrorMessage(e)) } finally { lock.current = false }
    }
    const saveGoal = async () => {
        const ml = Number(goal), profile = c.state?.profile
        if (!profile || c.busy) return
        if (!Number.isInteger(ml) || ml < 250 || ml > 10000) { setError(mt("Укажите ориентир от 250 до 10 000 мл")); return }
        try { await c.perform({ kind: "settings", expected_version: profile.version, settings: { ...profile.settings, water_goal_ml: ml } }); setEditingGoal(false); setError("") } catch (e) { setError(getErrorMessage(e)) }
    }
    const today = mentorHomeData(c.state, c.clock)
    const consumed = c.state?.mentor?.today.date === today.date ? c.state.mentor.today.water?.consumed_ml ?? 0 : 0
    return <Page title={mt("Вода")} onBack={close}>
        <View style={[styles.waterCard, { backgroundColor: colors.soft }]}><MentorQuestionIcon name="water" size={42} color={colors.blue} /><Text style={[styles.total, { color: colors.blue }]}>{number(consumed)}<Text style={styles.value}> / {number(waterTarget(c.state))} {mt("мл")}</Text></Text></View>
        <View style={styles.choices}>{[200, 250, 500].map(ml => <Action key={ml} label={mt("{0} мл", [ml])} secondary onPress={() => setAmount(String(ml))} />)}</View>
        <Text style={[styles.caption, { color: colors.muted }]}>{mt("Свой объём, мл")}</Text>
        <TextInput accessibilityLabel={mt("Объём воды, мл")} value={amount} onChangeText={setAmount} keyboardType="number-pad" maxLength={5} style={[styles.input, { color: colors.text, borderColor: colors.border }]} />
        <Action label={mt("Добавить воду")} onPress={() => void add()} busy={c.busy} />
        <Action label={mt("Изменить дневной ориентир")} secondary onPress={() => setEditingGoal(value => !value)} />
        {editingGoal ? <><TextInput accessibilityLabel={mt("Ориентир воды, мл")} value={goal} onChangeText={setGoal} keyboardType="number-pad" maxLength={5} style={[styles.input, { color: colors.text, borderColor: colors.border }]} /><Action label={mt("Сохранить ориентир")} busy={c.busy} onPress={() => void saveGoal()} /></> : null}
        {error ? <Text accessibilityRole="alert" style={{ color: colors.text }}>{error}</Text> : null}
    </Page>
}

function MealReminders({ c, close }: { c: Controller; close: () => void }) {
    const colors = useMentorPalette()
    const [selected, setSelected] = useState(c.state?.profile?.settings.meal_reminders ?? []), [habits, setHabits] = useState<MealHabits | null>(null), [error, setError] = useState(""), [loading, setLoading] = useState(true)
    const alive = useRef(true), lock = useRef(false)
    useEffect(() => { alive.current = true; void getMealLibrary().then(result => { if (alive.current) setHabits(result.habits) }).catch(e => { if (alive.current) setError(getErrorMessage(e)) }).finally(() => { if (alive.current) setLoading(false) }); return () => { alive.current = false } }, [])
    const save = async (values = selected) => {
        const profile = c.state?.profile
        if (!profile || c.busy || lock.current) return
        lock.current = true
        try { await c.perform({ kind: "settings", expected_version: profile.version, settings: { ...profile.settings, meal_reminders: values } }); if (values.length) await syncPushNotifications({ requestPermissions: true }); if (alive.current) close() }
        catch (e) { if (alive.current) setError(getErrorMessage(e)) } finally { lock.current = false }
    }
    return <Page title={mt("Напоминания о еде")} onBack={close}>
        <View style={[styles.info, { backgroundColor: colors.soft }]}><MentorQuestionIcon name="clock" color={colors.green} /><Text style={[styles.foodName, { color: colors.text }]}>{mt("По привычному времени")}</Text></View>
        <Text style={[styles.caption, { color: colors.muted }]}>{mt("Если приём пищи ещё не записан")}</Text>
        {loading ? <ActivityIndicator color={colors.green} /> : null}
        {mainMeals.map(type => <View key={type} style={[styles.setting, { borderBottomColor: colors.border }]}><View style={{ flex: 1, gap: 5 }}><Text style={[styles.heading, { color: colors.text }]}>{mealLabel(type)}</Text><Text style={[styles.caption, { color: colors.muted }]}>{habits?.[type]?.time ? mt("Обычно в {0}", [habits[type].time]) : mt("Определим после трёх дней записей")}</Text></View><Switch accessibilityLabel={mealLabel(type)} value={selected.includes(type)} onValueChange={on => setSelected(value => on ? [...value.filter(item => item !== type), type] : value.filter(item => item !== type))} trackColor={{ false: colors.border, true: colors.greenBright }} thumbColor="#FFFFFF" /></View>)}
        <Text style={[styles.heading, { color: colors.text }]}>{mt("Пример уведомления")}</Text>
        <View style={[styles.preview, { backgroundColor: colors.soft }]}><MentorQuestionIcon name="leaf" color={colors.green} /><View style={{ flex: 1, gap: 5 }}><Text style={[styles.caption, { color: colors.green }]}>{mt("Наставник")}</Text><Text style={[styles.foodName, { color: colors.text }]}>{mt("Не забыли про завтрак?")}</Text><Text style={[styles.caption, { color: colors.muted }]}>{mt("Если уже поели, добавьте запись.")}</Text></View></View>
        {error ? <Text accessibilityRole="alert" style={{ color: colors.text }}>{error}</Text> : null}
        <Action label={mt("Сохранить")} busy={c.busy} onPress={() => void save()} />
        <Action label={mt("Отключить все")} secondary busy={c.busy} onPress={() => void save([])} />
    </Page>
}

export function MentorNutritionEditor({ controller: c, shown, onClose }: { controller: Controller; shown: boolean; onClose: () => void }) {
    useLanguage()
    const colors = useMentorPalette(), editor = c.editor!, insets = useSafeAreaInsets()
    const back = () => editor.parentMeal ? c.setEditor({ page: "meal_group", mealType: editor.mealType, mealKey: editor.mealKey }) : onClose()
    return <View style={{ flex: 1, backgroundColor: colors.surface, paddingTop: insets.top, paddingBottom: Math.max(insets.bottom, 8) }}>
        {editor.page === "meal" || editor.page === "food_help" ? <MentorFoodEditor controller={c} shown={shown} onClose={back} onSaved={async () => { back() }} helpMode={editor.page === "food_help" ? editor.helpMode ?? "suggest" : undefined} /> : editor.page === "meal_group" ? <MealGroup c={c} close={onClose} /> : editor.page === "water" ? <Water c={c} close={onClose} /> : <MealReminders c={c} close={onClose} />}
    </View>
}

const styles = StyleSheet.create({
    body: { width: "100%", maxWidth: 560, alignSelf: "center", padding: 24, gap: 18, paddingBottom: 30 }, action: { minHeight: 50, padding: 13, borderRadius: 17, flexDirection: "row", gap: 9, alignItems: "center", justifyContent: "center" }, actionText: { fontWeight: "700", fontSize: 16 }, total: { fontSize: 38, lineHeight: 48, fontWeight: "800", letterSpacing: -1 }, macros: { flexDirection: "row", paddingVertical: 10 }, macro: { flex: 1, alignItems: "center", gap: 7 }, value: { fontSize: 21, fontWeight: "700" }, caption: { fontSize: 14, lineHeight: 20, fontWeight: "500" }, heading: { fontSize: 22, fontWeight: "800" }, foodName: { fontSize: 17, lineHeight: 24, fontWeight: "700" }, foodCalories: { fontSize: 14, fontWeight: "600" }, foodRow: { minHeight: 72, flexDirection: "row", alignItems: "center", gap: 4, paddingVertical: 12, borderBottomWidth: StyleSheet.hairlineWidth }, iconButton: { width: 36, height: 44, alignItems: "center", justifyContent: "center" }, choices: { flexDirection: "row", justifyContent: "space-between", gap: 8 }, input: { borderWidth: 1, borderRadius: 17, padding: 16, fontWeight: "600", fontSize: 19 }, waterCard: { borderRadius: 24, padding: 24, gap: 14 }, info: { flexDirection: "row", alignItems: "center", gap: 12, borderRadius: 17, padding: 18 }, setting: { minHeight: 94, flexDirection: "row", alignItems: "center", gap: 12, borderBottomWidth: StyleSheet.hairlineWidth, paddingVertical: 16 }, preview: { flexDirection: "row", gap: 14, padding: 18, borderRadius: 23 },
})
