import { useCallback, useEffect, useRef, useState } from "react"
import { useIsFocused } from "@react-navigation/native"
import { ActivityIndicator, Alert, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { getErrorMessage } from "@/utils/errors"
import { actCompanion, eraseCompanion, getCompanion, getCompanionAvailability, getCompanionEntries, getCompanionEvents, getCompanionSummary, getCompanionSupply, getNutritionSuggestion } from "@/services/api/companion"
import type { CompanionAction, CompanionCard, CompanionEntry, CompanionSettings, CompanionState, EntryData, Nutrition, PlanData, ProfileData, Proposal, Stage, Summary, Supply, Unit } from "@/services/api/companion"
import type { AIMessageRead } from "@/services/api/ai-chat.types"
import { CompanionActionCancelled, withStorageConsent } from "@/screens/chat/companion-consent"

type Page = "home" | "consent" | "profile" | "plan" | "meal" | "weight" | "wellbeing" | "nutrition" | "settings" | "journal" | "events" | "summary" | "supply"
type Editor = { page: Page; proposal?: Proposal; entry?: CompanionEntry }
type Controller = ReturnType<typeof useCompanion>
const unitLabels: Record<Unit, string> = { mg: "мг", mcg: "мкг", g: "г", ml: "мл", capsule: "капсул", tablet: "таблеток", IU: "МЕ" }
const settingsDefault: CompanionSettings = { timezone: "Europe/Moscow", nutrition_auto_eligible: false, course_reminders: false, daily_time: null, weight_time: null, weekly_time: null, weekly_day: 6, supply_reminders: false, supply_days: 7 }
const emptyNutrition = (): Nutrition => ({ kcal: "", protein: "", fat: "", carbs: "" })
const dateLabel = (date: string, zone?: string) => new Date(date).toLocaleString("ru-RU", zone ? { timeZone: zone } : undefined)
const numberOrNull = (value: string) => value.trim() ? Number(value.replace(",", ".")) : null
function calendarDate(zone: string, days = 0) {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: zone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date())
    const part = (type: string) => parts.find(p => p.type === type)?.value ?? ""
    const date = new Date(part("year") + "-" + part("month") + "-" + part("day") + "T12:00:00Z")
    date.setUTCDate(date.getUTCDate() + days)
    return date.toISOString().slice(0, 10)
}

export function useCompanion() {
    const focused = useIsFocused()
    const [state, setState] = useState<CompanionState | null>(null)
    const [busy, setBusy] = useState(false)
    const busyRef = useRef(false)
    const [error, setError] = useState("")
    const [editor, setEditor] = useState<Editor | null>(null)
    const refresh = useCallback(async () => {
        if (Platform.OS === "web") return
        try {
            const availability = await getCompanionAvailability()
            if (availability.available) {
                setState(previous => previous ?? availability)
                const next = await getCompanion()
                setState(next)
                setError("")
                return next
            }
            setState(availability)
            setError("")
            return availability
        } catch (e) { setError(getErrorMessage(e)) }
    }, [])
    useEffect(() => { if (focused) void refresh() }, [focused, refresh])
    const resolveEnabled = async () => {
        if (Platform.OS === "web") return false
        if (state?.profile) return state.profile.enabled
        if (state?.available === false) return false
        const next = await refresh()
        if (!next) throw new Error("Не удалось загрузить чат. Попробуйте ещё раз.")
        return !!next.profile?.enabled
    }
    const perform = async (action: CompanionAction) => {
        if (busyRef.current) throw new Error("Дождитесь завершения предыдущего действия")
        busyRef.current = true; setBusy(true); setError("")
        try {
            const payload = await withStorageConsent(state, action, version => new Promise(resolve => {
                Alert.alert("Сохранить личные данные?", "Приложение сохранит профиль, курс и дневник; нужный контекст будет передаваться OpenAI для ответов. Данные можно удалить в настройках. Нажимая кнопку ниже, вы подтверждаете возраст 18+ и согласие на обработку этих данных (" + version + ").", [
                    { text: "Не сохранять", style: "cancel", onPress: () => resolve(false) },
                    { text: "Мне есть 18 — сохранить", onPress: () => resolve(true) },
                ], { cancelable: true, onDismiss: () => resolve(false) })
            }))
            const result = await actCompanion(payload)
            setState(result.state)
            return result.state
        } finally { busyRef.current = false; setBusy(false) }
    }
    const attempt = async (operation: () => Promise<unknown>) => {
        try { await operation() } catch (e) { if (!(e instanceof CompanionActionCancelled)) setError(getErrorMessage(e)) }
    }
    return { state, setState, enabled: !!state?.profile?.enabled, resolveEnabled, busy, error, setError, editor, setEditor, refresh, perform, attempt }
}

function Copy({ children }: { children: React.ReactNode }) {
    const { palette } = useTheme()
    return <Text style={{ color: palette.text, lineHeight: 21, fontSize: 14 }}>{children}</Text>
}
function Button({ label, onPress, disabled = false }: { label: string; onPress: () => void; disabled?: boolean }) {
    const { palette } = useTheme()
    return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={[styles.button, { backgroundColor: palette.surfaceMuted, opacity: disabled ? 0.4 : 1 }]}><Text style={{ color: palette.primary, fontWeight: "600" }}>{label}</Text></Pressable>
}
function Field({ label, value, onChange, numeric = false, multiline = false, disabled = false }: { label: string; value: unknown; onChange: (value: string) => void; numeric?: boolean; multiline?: boolean; disabled?: boolean }) {
    const { palette } = useTheme()
    return <View style={styles.field}><Copy>{label}</Copy><TextInput accessibilityLabel={label} editable={!disabled} value={value == null ? "" : String(value)} onChangeText={onChange} keyboardType={numeric ? "decimal-pad" : "default"} autoCapitalize="none" multiline={multiline} style={[styles.input, { color: palette.text, backgroundColor: palette.fieldBackground, borderColor: palette.border }]} /></View>
}
function Toggle({ label, value, onChange, disabled = false }: { label: string; value: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
    return <View style={styles.toggle}><View style={{ flex: 1 }}><Copy>{label}</Copy></View><Switch accessibilityLabel={label} disabled={disabled} value={value} onValueChange={onChange} /></View>
}
function Choices<T extends string>({ options, value, onChange }: { options: Record<T, string>; value?: string | null; onChange: (value: T) => void }) {
    return <View style={styles.row}>{(Object.keys(options) as T[]).map(key => <Button key={key} label={(value === key ? "✓ " : "") + options[key]} onPress={() => onChange(key)} />)}</View>
}
function NutritionFields({ value, onChange, disabled = false }: { value: Nutrition; onChange: (n: Nutrition) => void; disabled?: boolean }) {
    const labels = { kcal: "Калории, ккал", protein: "Белки, г", fat: "Жиры, г", carbs: "Углеводы, г" }
    return <>{(Object.keys(labels) as (keyof Nutrition)[]).map(key => <Field key={key} label={labels[key]} value={value[key]} numeric disabled={disabled} onChange={text => onChange({ ...value, [key]: text.replace(",", ".") })} />)}</>
}
function NutritionCopy({ value }: { value: Nutrition }) { return <Copy>{value.kcal} ккал · Б {value.protein} · Ж {value.fat} · У {value.carbs} г</Copy> }

function ProposalCopy({ proposal }: { proposal: Proposal }) {
    if (proposal.plan) return <><Copy>Курс: {proposal.plan.name} · {proposal.plan.timezone}</Copy>{proposal.plan.items.map((item, i) => <View key={i} style={styles.card}>
        <Copy>{item.name}{item.variant_id ? " · вариант #" + item.variant_id : ""}</Copy>
        {item.stages.map((stage, j) => <Copy key={j}>{stage.start_date} — {stage.end_date}: {stage.amount} {unitLabels[stage.unit]}, {stage.times.join(", ")}; {stage.weekdays.length ? "дни недели: " + stage.weekdays.map(d => ["пн", "вт", "ср", "чт", "пт", "сб", "вс"][d]).join(", ") : "каждые " + stage.interval_days + " дн."}</Copy>)}
        <Copy>В упаковке: {item.package_amount ?? "не уточнено"} {item.package_unit ? unitLabels[item.package_unit] : ""}. Фактический запас на начало этой версии: {item.home_amount ?? "не уточнён"} {item.package_unit ? unitLabels[item.package_unit] : ""}.</Copy>
        {item.package_source_name ? <Copy>Источник размера упаковки: {item.package_source_name}</Copy> : null}
    </View>)}<Copy>Это ваша готовая схема, а не назначение AI. Проверьте каждый этап и остаток перед подтверждением.</Copy></>
    if (proposal.entry) {
        const entry = proposal.entry
        return <><Copy>{dateLabel(entry.occurred_at)} · {entry.kind === "meal" ? entry.name : entry.kind === "weight" ? String(entry.weight_kg) + " кг" : "Самочувствие"}</Copy>
            {entry.portion_g ? <Copy>Порция: {entry.portion_g} г</Copy> : null}
            {entry.nutrition ? <NutritionCopy value={entry.nutrition} /> : null}
            {entry.estimated ? <Copy>Приблизительная оценка: {entry.assumptions || "проверьте состав и размер порции"}</Copy> : null}
            {entry.kind === "wellbeing" ? <Copy>Самочувствие {entry.wellbeing ?? "—"}/5 · аппетит {entry.appetite ?? "—"}/5 · энергия {entry.energy ?? "—"}/5 · сон {entry.sleep_hours ?? "—"} ч</Copy> : null}
            {entry.note ? <Copy>{entry.note}</Copy> : null}</>
    }
    if (proposal.nutrition) return <NutritionCopy value={proposal.nutrition} />
    if (proposal.profile) {
        const p = proposal.profile
        return <><Copy>Цель: {p.goal === "course" ? "сопровождение курса" : p.goal === "maintain" ? "поддержание" : "снижение веса"}. Возраст {p.age ?? "—"}, рост {p.height_cm ?? "—"} см, целевой вес {p.target_weight_kg ?? "—"} кг.</Copy><Copy>Пол: {p.sex === "female" ? "женский" : p.sex === "male" ? "мужской" : "не указан"}. Активность: {({ low: "низкая", light: "лёгкая", moderate: "умеренная", high: "высокая" })[p.activity ?? "low"]}.</Copy><Copy>Предпочтения: {p.preferences || "—"}. Ограничения: {p.restrictions || "—"}.</Copy>{p.nutrition ? <NutritionCopy value={p.nutrition} /> : null}</>
    }
    return null
}

export function CompanionCards({ controller: c, message, onChanged }: { controller: Controller; message: AIMessageRead; onChanged: () => Promise<void> }) {
    if (!c.enabled || Platform.OS === "web") return null
    const action = async (card: CompanionCard, kind: "confirm" | "cancel", edit = false) => {
        await c.perform({ kind, message_id: message.id, action_id: card.id, action_token: card.action_token ?? "" })
        await onChanged()
        if (edit) c.setEditor({ page: card.kind === "entry" ? card.proposal.entry?.kind ?? "meal" : card.kind, proposal: card.proposal })
    }
    return <>{message.companion_cards?.map(card => <View key={card.id} style={styles.card}>
        <Copy>{card.state === "confirmed" ? "✓ Сохранено" : card.state === "cancelled" ? "Отменено" : "Черновик — проверьте данные"}</Copy>
        <Copy>{card.summary}</Copy><ProposalCopy proposal={card.proposal} />
        {card.state === "pending" ? <View style={styles.row}>
            <Button label="Подтвердить" disabled={c.busy} onPress={() => void c.attempt(() => action(card, "confirm"))} />
            <Button label="Исправить" disabled={c.busy} onPress={() => void c.attempt(() => action(card, "cancel", true))} />
            <Button label="Отмена" disabled={c.busy} onPress={() => void c.attempt(() => action(card, "cancel"))} />
        </View> : null}
    </View>)}</>
}

export function CompanionPanel({ controller: c, onChanged, openRequested }: { controller: Controller; onChanged: () => Promise<void>; openRequested?: boolean }) {
    const { palette } = useTheme()
    useEffect(() => { if (openRequested && c.state?.profile) c.setEditor({ page: "home" }) }, [openRequested, !!c.state?.profile]) // Wait for the profile, not just availability.
    if (Platform.OS === "web" || !c.state?.available) return null
    const changed = async () => { await c.refresh(); await onChanged() }
    return <View style={[styles.panel, { backgroundColor: palette.surface, borderColor: palette.border }]}>
        <Button label="Мой курс · дневник · прогресс" disabled={!c.state.profile && !c.error} onPress={() => c.setEditor({ page: c.state?.profile ? "home" : "consent" })} />
        {c.error ? <><Copy>{c.error}</Copy><Button label="Обновить" onPress={() => void changed()} /></> : null}
        <Modal visible={!!c.editor} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => c.setEditor(null)}>
            <KeyboardAvoidingView style={{ flex: 1, backgroundColor: palette.background }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
                <View style={styles.modalHeader}><Button label="Закрыть" onPress={() => c.setEditor(null)} />{c.busy ? <ActivityIndicator /> : null}</View>
                <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.modal}>
                    {c.error ? <Copy>{c.error}</Copy> : null}
                    {c.editor ? <CompanionContent key={JSON.stringify(c.editor)} controller={c} onChanged={changed} /> : null}
                </ScrollView>
            </KeyboardAvoidingView>
        </Modal>
    </View>
}

function CompanionContent({ controller: c, onChanged }: { controller: Controller; onChanged: () => Promise<void> }) {
    const page = c.editor!.page
    const state = c.state!
    const profile = state.profile
    const version = profile?.version
    const open = (page: Page) => { c.setError(""); c.setEditor({ page }) }
    const save = async (action: CompanionAction) => { await c.perform(action); c.setEditor({ page: "home" }); await onChanged() }
    if (page === "consent") return <ConsentForm controller={c} onSave={save} />
    if (["profile", "meal", "weight", "wellbeing", "nutrition", "plan", "settings"].includes(page)) return <ManualForm controller={c} onSave={save} onChanged={onChanged} />
    if (page === "summary" || page === "journal" || page === "events" || page === "supply") return <ReviewPanel controller={c} onChanged={onChanged} />
    return <>
        <Copy>Сопровождение {profile?.enabled ? "включено" : "выключено"}. Данные сохраняются после подтверждения; AI не назначает препараты и не меняет дозировки.</Copy>
        {!profile?.enabled ? <Button label="Возобновить сопровождение" onPress={() => open("consent")} /> : null}
        <View style={styles.row}>{(["profile", "plan", "meal", "weight", "wellbeing", "journal", "summary", "supply", "settings", "events"] as Page[]).map((p, i) => <Button key={p} label={["Профиль", "Мой курс", "Записать еду", "Вес", "Самочувствие", "Дневник", "Итоги", "Запас", "Настройки", "История событий"][i]} onPress={() => open(p)} />)}</View>
        {state.today ? <><Copy>Сегодня записано: {state.today.meals_logged} приёмов пищи</Copy><NutritionCopy value={state.today.nutrition} /></> : null}
        {profile?.data.nutrition ? <><Copy>Ваш ориентир на день:</Copy><NutritionCopy value={profile.data.nutrition} /></> : null}
        <Button label="КБЖУ: вручную или рассчитать" onPress={() => open("nutrition")} />
        {state.plan ? <>
            <Copy>Курс: {state.plan.data.name} · версия {state.plan.version} · {({ active: "активен", paused: "на паузе", completed: "завершён" } as Record<string, string>)[state.plan.status]}</Copy>
            <ProposalCopy proposal={{ kind: "plan", summary: "", plan: state.plan.data }} />
            <View style={styles.row}>
                {state.plan.status === "active" ? <Button label="Пауза" disabled={c.busy} onPress={() => void c.attempt(() => save({ kind: "plan_status", expected_version: version, status: "paused" }))} /> : null}
                {state.plan.status === "paused" ? <Button label="Обновить и возобновить" onPress={() => open("plan")} /> : null}
                {state.plan.status !== "completed" ? <Button label="Завершить курс" disabled={c.busy} onPress={() => Alert.alert("Завершить курс?", "Будущие напоминания будут отменены, история останется.", [{ text: "Отмена" }, { text: "Завершить", onPress: () => void c.attempt(() => save({ kind: "plan_status", expected_version: version, status: "completed" })) }])} /> : null}
            </View>
        </> : <Copy>Пришлите свою готовую схему в чат или заполните «Мой курс». Бот подготовит карточку для проверки.</Copy>}
        <Copy>События сегодня и на ближайшие 7 дней · {profile?.settings.timezone}</Copy>
        {state.events?.map(event => <View key={event.id} style={styles.card}>
            <Copy>{dateLabel(event.scheduled_at, profile?.settings.timezone)} · {event.data.name} · {event.data.amount} {unitLabels[event.data.unit]}</Copy>
            <Copy>{event.status === "pending" ? "Нет отметки" : event.status === "done" ? "Выполнено" : "Пропущено"}</Copy>
            <View style={styles.row}>{(["done", "skipped", "pending"] as const).filter(status => status !== event.status).map(status => <Button key={status} label={status === "done" ? "Выполнено" : status === "skipped" ? "Пропущено" : "Снять отметку"} disabled={c.busy || status === "done" && Date.parse(event.scheduled_at) > Date.now()} onPress={() => void c.attempt(() => save({ kind: "event", resource_id: event.id, expected_version: event.version, status }))} />)}</View>
        </View>)}
    </>
}

function ConsentForm({ controller: c, onSave }: { controller: Controller; onSave: (action: CompanionAction) => Promise<void> }) {
    const [adult, setAdult] = useState(false)
    const [accepted, setAccepted] = useState(false)
    return <>
        <Copy>Чат поможет вести вашу готовую схему, питание, вес и самочувствие. Он не заменяет врача, не назначает пептиды и не корректирует дозировки. При ухудшении состояния обратитесь за медицинской помощью.</Copy>
        <Copy>По вашему согласию приложение хранит профиль, курс, дневник и сообщения сопровождения. Для ответов нужный контекст и отправленные вами вложения передаются OpenAI. Напоминания по умолчанию выключены; данные можно удалить в настройках. Не отправляйте чужие медицинские документы.</Copy>
        <Toggle label="Мне исполнилось 18 лет" value={adult} onChange={setAdult} />
        <Toggle label={"Согласен на обработку указанных данных и передачу контекста OpenAI для сопровождения (" + c.state?.consent_version + ")"} value={accepted} onChange={setAccepted} />
        <Button label="Включить" disabled={!adult || !accepted || c.busy} onPress={() => void c.attempt(() => onSave({ kind: "enable", adult_confirmed: adult, consent_version: c.state!.consent_version, settings: { ...settingsDefault, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Moscow" } }))} />
    </>
}

function ManualForm({ controller: c, onSave, onChanged }: { controller: Controller; onSave: (action: CompanionAction) => Promise<void>; onChanged: () => Promise<void> }) {
    const editor = c.editor!
    const page = editor.page
    const profile = c.state!.profile!
    const [person, setPerson] = useState<ProfileData>(editor.proposal?.profile ?? profile.data)
    const [nutrition, setNutrition] = useState<Nutrition>(editor.proposal?.nutrition ?? profile.data.nutrition ?? emptyNutrition())
    const [entry, setEntry] = useState<EntryData>(editor.entry?.data ?? editor.proposal?.entry ?? { kind: page as EntryData["kind"], occurred_at: new Date().toISOString(), ...(page === "meal" ? { nutrition: emptyNutrition() } : {}) })
    const [plan, setPlan] = useState<PlanData>(editor.proposal?.plan ?? c.state!.plan?.data ?? { name: "", timezone: profile.settings.timezone, items: [] })
    const [settings, setSettings] = useState<CompanionSettings>({ ...settingsDefault, ...profile.settings })
    const [suggestionNote, setSuggestionNote] = useState("")
    const [ruleVersion, setRuleVersion] = useState<string | undefined>()
    const [calculating, setCalculating] = useState(false)
    const calculationRef = useRef(false)
    const version = profile.version
    const save = (action: CompanionAction) => void c.attempt(() => onSave({ expected_version: version, ...action }))
    return <>
        {page === "profile" ? <>
            <Copy>Профиль: заполняйте только нужные для сопровождения данные.</Copy>
            <Choices options={{ weight_loss: "Снижение веса", maintain: "Поддержание", course: "Курс" }} value={person.goal} onChange={goal => setPerson({ ...person, goal })} />
            <Field label="Возраст, лет" value={person.age} numeric onChange={text => setPerson({ ...person, age: numberOrNull(text) })} />
            <Choices options={{ male: "Мужской", female: "Женский" }} value={person.sex} onChange={sex => setPerson({ ...person, sex })} />
            <Field label="Рост, см" value={person.height_cm} numeric onChange={text => setPerson({ ...person, height_cm: numberOrNull(text) })} />
            <Field label="Целевой вес, кг" value={person.target_weight_kg} numeric onChange={text => setPerson({ ...person, target_weight_kg: numberOrNull(text) })} />
            <Choices options={{ low: "Низкая активность", light: "Лёгкая", moderate: "Умеренная", high: "Высокая" }} value={person.activity} onChange={activity => setPerson({ ...person, activity })} />
            <Field label="Пищевые предпочтения" multiline value={person.preferences} onChange={preferences => setPerson({ ...person, preferences })} />
            <Field label="Известные вам ограничения" multiline value={person.restrictions} onChange={restrictions => setPerson({ ...person, restrictions })} />
            <Button label="Сохранить профиль" disabled={c.busy} onPress={() => save({ kind: "profile", profile: person })} />
        </> : null}
        {page === "nutrition" ? <>
            <Copy>КБЖУ на день: готовые значения можно внести вручную. Авторасчёт предлагает стартовый ориентир и не меняет прошлые записи.</Copy>
            <Copy>Авторасчёт не предназначен для беременности, грудного вскармливания, расстройств пищевого поведения, состояний и лечения, требующих индивидуального питания (например, болезней почек или сахароснижающих препаратов). В этих случаях используйте ориентир специалиста.</Copy>
            <Toggle label="Подтверждаю, что перечисленные ограничения ко мне не относятся" value={!!profile.settings.nutrition_auto_eligible} disabled={c.busy || calculating} onChange={value => void c.attempt(async () => {
                await c.perform({ kind: "settings", expected_version: version, settings: { ...settingsDefault, ...profile.settings, nutrition_auto_eligible: value } })
                setNutrition(profile.data.nutrition ?? emptyNutrition()); setRuleVersion(undefined); setSuggestionNote("")
            })} />
            <Button label={calculating ? "Считаем…" : "Предложить расчёт"} disabled={c.busy || calculating || !profile.settings.nutrition_auto_eligible} onPress={() => void c.attempt(async () => {
                if (calculationRef.current) return
                calculationRef.current = true; setCalculating(true); setSuggestionNote("")
                try {
                    const result = await getNutritionSuggestion()
                    if (result.available && result.nutrition) {
                        setNutrition(result.nutrition); setRuleVersion(result.rule_version)
                        setSuggestionNote((result.note ?? "Проверьте перед сохранением.") + " Поддержание: ~" + result.maintenance_kcal + " ккал; дефицит: ~" + result.deficit_kcal + " ккал. Версия: " + result.rule_version)
                    } else { setRuleVersion(undefined); setSuggestionNote(result.reason ?? "Расчёт недоступен") }
                } finally { calculationRef.current = false; setCalculating(false) }
            })} />
            {suggestionNote ? <Copy>{suggestionNote}</Copy> : null}
            <NutritionFields value={nutrition} disabled={calculating || c.busy} onChange={value => { setNutrition(value); setRuleVersion(undefined); setSuggestionNote("Ручные значения — проверьте перед сохранением.") }} />
            <Button label="Подтвердить КБЖУ" disabled={c.busy || calculating} onPress={() => save({ kind: "nutrition", nutrition, nutrition_rule_version: ruleVersion })} />
        </> : null}
        {["meal", "weight", "wellbeing"].includes(page) ? <>
            <Field label="Дата и время с часовым поясом (например, 2026-09-02T12:30:00+03:00)" value={entry.occurred_at} onChange={occurred_at => setEntry({ ...entry, occurred_at })} />
            {page === "meal" ? <><Field label="Что съели" value={entry.name} onChange={name => setEntry({ ...entry, name })} /><Field label="Порция, г (если известна)" value={entry.portion_g} numeric onChange={text => setEntry({ ...entry, portion_g: numberOrNull(text) })} /><NutritionFields value={entry.nutrition ?? emptyNutrition()} onChange={nutrition => setEntry({ ...entry, nutrition })} /><Toggle label="Приблизительная оценка" value={!!entry.estimated} onChange={estimated => setEntry({ ...entry, estimated })} />{entry.estimated ? <Field label="Допущения оценки" value={entry.assumptions} onChange={assumptions => setEntry({ ...entry, assumptions })} /> : null}<Copy>Можно отправить фото еды в чат — AI предложит оценку для подтверждения.</Copy></> : null}
            {page === "weight" ? <Field label="Вес, кг" value={entry.weight_kg} numeric onChange={text => setEntry({ ...entry, weight_kg: numberOrNull(text) })} /> : null}
            {page === "wellbeing" ? <>{(["wellbeing", "appetite", "energy", "sleep_hours"] as const).map((key, i) => <Field key={key} label={["Самочувствие, 1–5", "Аппетит, 1–5", "Энергия, 1–5", "Сон, часов"][i]} value={entry[key]} numeric onChange={text => setEntry({ ...entry, [key]: numberOrNull(text) })} />)}</> : null}
            <Field label="Комментарий" multiline value={entry.note} onChange={note => setEntry({ ...entry, note })} />
            <Button label={editor.entry ? "Сохранить исправление" : "Подтвердить запись"} disabled={c.busy} onPress={() => save({ kind: "entry", entry, resource_id: editor.entry?.id, expected_version: editor.entry?.version })} />
        </> : null}
        {page === "plan" ? <><Copy>Перенесите готовую схему. Каждый этап задаётся отдельно. При обновлении старые отметки сохранятся, будущие события заменятся. Укажите фактический остаток на момент обновления.</Copy><Field label="Название курса" value={plan.name} onChange={name => setPlan({ ...plan, name })} /><Field label="Часовой пояс расписания (IANA)" value={plan.timezone} onChange={timezone => setPlan({ ...plan, timezone })} /><PlanFields plan={plan} onChange={setPlan} /><Button label="Подтвердить и сохранить курс" disabled={c.busy || !plan.items.length} onPress={() => save({ kind: "plan", plan })} /></> : null}
        {page === "settings" ? <>
            <Copy>Push включается в настройках уведомлений приложения. Здесь задаётся, о чём и когда напоминать. Пустое время выключает напоминание.</Copy>
            <Field label="Часовой пояс дневника и напоминаний (IANA)" value={settings.timezone} onChange={timezone => setSettings({ ...settings, timezone })} />
            <Copy>Смена этого пояса не меняет расписание курса — его пояс редактируется в «Мой курс».</Copy>
            <Toggle label="Напоминать о событиях курса" value={settings.course_reminders} onChange={course_reminders => setSettings({ ...settings, course_reminders })} />
            {(["daily_time", "weight_time", "weekly_time"] as const).map((key, i) => <Field key={key} label={["Итоги дня, ЧЧ:ММ", "Напомнить внести вес, ЧЧ:ММ", "Итоги недели, ЧЧ:ММ"][i]} value={settings[key]} onChange={text => setSettings({ ...settings, [key]: text || null })} />)}
            <Field label="День недельной сводки: 0 пн … 6 вс" value={settings.weekly_day} numeric onChange={text => setSettings({ ...settings, weekly_day: Number(text) })} />
            <Toggle label="Напоминать о нехватке запаса" value={settings.supply_reminders} onChange={supply_reminders => setSettings({ ...settings, supply_reminders })} />
            <Field label="Проверять запас на ближайшие N дней" value={settings.supply_days} numeric onChange={text => setSettings({ ...settings, supply_days: Number(text) })} />
            <Button label="Сохранить настройки" disabled={c.busy} onPress={() => save({ kind: "settings", settings })} />
            <Button label="Выключить сопровождение" disabled={c.busy} onPress={() => Alert.alert("Выключить?", "Напоминания прекратятся; дневник сохранится. Обычный чат начнёт новый контекст.", [{ text: "Отмена" }, { text: "Выключить", onPress: () => void c.attempt(async () => { await c.perform({ kind: "disable", expected_version: version }); c.setEditor(null); await c.refresh() }) }])} />
            <Button label="Удалить данные сопровождения" disabled={c.busy} onPress={() => Alert.alert("Удалить без восстановления?", "Будут удалены профиль, курс, дневник и сообщения сопровождения. Удаление копий диалогов и файлов у OpenAI будет поставлено в очередь с повторными попытками.", [{ text: "Отмена" }, { text: "Удалить", style: "destructive", onPress: () => void c.attempt(async () => { await eraseCompanion(); c.setEditor(null); await onChanged() }) }])} />
        </> : null}
    </>
}

function PlanFields({ plan, onChange }: { plan: PlanData; onChange: (plan: PlanData) => void }) {
    const blankStage = (): Stage => ({ start_date: "", end_date: "", amount: "", unit: "mg", interval_days: 1, weekdays: [], times: [""] })
    const itemChange = (i: number, patch: Partial<PlanData["items"][number]>) => onChange({ ...plan, items: plan.items.map((item, n) => n === i ? { ...item, ...patch } : item) })
    return <>{plan.items.map((item, i) => <View key={i} style={styles.card}>
        <Field label={"Позиция " + (i + 1)} value={item.name} onChange={name => itemChange(i, { name })} />
        <Field label="ID варианта из каталога (необязательно)" value={item.variant_id} numeric onChange={text => itemChange(i, { variant_id: numberOrNull(text), package_source_name: null })} />
        <Field label="Содержимое одной упаковки (если неизвестно — оставьте пустым)" value={item.package_amount} numeric onChange={text => itemChange(i, { package_amount: numberOrNull(text), package_unit: text ? item.package_unit ?? "mg" : null })} />
        {item.package_amount ? <Choices options={unitLabels} value={item.package_unit} onChange={package_unit => itemChange(i, { package_unit })} /> : null}
        <Field label="Фактический остаток сейчас, в единицах содержимого упаковки (не число упаковок)" value={item.home_amount} numeric onChange={text => itemChange(i, { home_amount: text.trim() ? text.replace(",", ".") : null })} />
        {item.stages.map((stage, j) => {
            const change = (patch: Partial<Stage>) => itemChange(i, { stages: item.stages.map((s, n) => n === j ? { ...s, ...patch } : s) })
            return <View key={j} style={styles.card}>
                <Copy>Этап {j + 1}</Copy>
                <Field label="Начало, ГГГГ-ММ-ДД" value={stage.start_date} onChange={start_date => change({ start_date })} />
                <Field label="Конец включительно, ГГГГ-ММ-ДД" value={stage.end_date} onChange={end_date => change({ end_date })} />
                <Field label="Количество на одно событие — из вашей схемы" value={stage.amount} numeric onChange={text => change({ amount: text.replace(",", ".") })} />
                <Choices options={unitLabels} value={stage.unit} onChange={unit => change({ unit })} />
                <Field label="Время, ЧЧ:ММ; несколько через запятую" value={stage.times.join(", ")} onChange={text => change({ times: text.split(",").map(t => t.trim()) })} />
                <Field label="Интервал в днях (1 = ежедневно)" value={stage.interval_days} numeric onChange={text => change({ interval_days: Number(text), weekdays: [] })} />
                <Copy>Или конкретные дни недели:</Copy>
                <View style={styles.row}>{["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((d, day) => <Button key={day} label={(stage.weekdays.includes(day) ? "✓ " : "") + d} onPress={() => change({ interval_days: 1, weekdays: stage.weekdays.includes(day) ? stage.weekdays.filter(v => v !== day) : [...stage.weekdays, day] })} />)}</View>
                {item.stages.length > 1 ? <Button label="Удалить этап из черновика" onPress={() => itemChange(i, { stages: item.stages.filter((_, n) => n !== j) })} /> : null}
            </View>
        })}
        <Button label="+ Этап" disabled={item.stages.length >= 24} onPress={() => itemChange(i, { stages: [...item.stages, blankStage()] })} />
        <Button label="Удалить позицию из черновика" onPress={() => onChange({ ...plan, items: plan.items.filter((_, n) => n !== i) })} />
    </View>)}<Button label="+ Позиция курса" disabled={plan.items.length >= 12} onPress={() => onChange({ ...plan, items: [...plan.items, { name: "", stages: [blankStage()], home_amount: null }] })} /></>
}

function ReviewPanel({ controller: c, onChanged }: { controller: Controller; onChanged: () => Promise<void> }) {
    const page = c.editor!.page
    const zone = c.state!.profile!.settings.timezone
    const [from, setFrom] = useState(calendarDate(zone, -6))
    const [to, setTo] = useState(calendarDate(zone, 1))
    const [entries, setEntries] = useState(c.state!.entries ?? [])
    const [events, setEvents] = useState(c.state!.events ?? [])
    const [summary, setSummary] = useState<Summary | null>(null)
    const [supply, setSupply] = useState<Supply | null>(null)
    const [days, setDays] = useState("30")
    const [loading, setLoading] = useState(false)
    const [added, setAdded] = useState<number[]>([])
    const basket = useBasketMutations()
    const load = async () => {
        setLoading(true)
        try {
            if (page === "supply") { setSupply(await getCompanionSupply(Number(days))); setAdded([]) }
            else if (page === "events") setEvents((await getCompanionEvents(from, to)).events)
            else if (page === "summary") setSummary(await getCompanionSummary(from, to))
            else setEntries((await getCompanionEntries(from, to)).entries)
        } finally { setLoading(false) }
    }
    useEffect(() => { void c.attempt(load) }, []) // Load the initial view; subsequent date changes use the explicit button.
    return <>
        <Button label="Назад к плану" onPress={() => c.setEditor({ page: "home" })} />
        {page === "supply" ? <><Field label="Период прогноза, 1–90 дней" value={days} numeric onChange={setDays} /><Copy>Расчёт не меняет схему. Покупка только по отдельному нажатию; добавление в корзину не увеличивает домашний запас.</Copy></> : <><Field label="С даты включительно, ГГГГ-ММ-ДД" value={from} onChange={setFrom} /><Field label="До даты не включительно, ГГГГ-ММ-ДД (до 90 дней)" value={to} onChange={setTo} /></>}
        <Button label="Обновить" disabled={loading} onPress={() => void c.attempt(load)} />
        {loading ? <ActivityIndicator /> : null}
        {page === "summary" && summary ? <><NutritionCopy value={summary.nutrition} /><Copy>Приёмов пищи: {summary.meals_logged}, дней с записями: {summary.days_with_meals}. Измерений веса: {summary.weight_measurements}; изменение: {summary.weight_change_kg == null ? "недостаточно данных" : summary.weight_change_kg + " кг"}.</Copy><Copy>События: выполнено {summary.events.done}, пропущено {summary.events.skipped}, без отметки {summary.events.pending}.</Copy><Copy>{summary.coverage_note}</Copy></> : null}
        {page === "events" ? <>{!events.length ? <Copy>Нет событий в выбранном периоде.</Copy> : null}{events.map(event => <View key={event.id} style={styles.card}>
            <Copy>{dateLabel(event.scheduled_at, zone)} · {event.data.name} · {event.data.amount} {unitLabels[event.data.unit]} · {event.status === "pending" ? "без отметки" : event.status === "done" ? "выполнено" : "пропущено"}</Copy>
            <View style={styles.row}>{(["done", "skipped", "pending"] as const).filter(status => status !== event.status).map(status => <Button key={status} label={status === "done" ? "Выполнено" : status === "skipped" ? "Пропущено" : "Снять отметку"} disabled={c.busy || status === "done" && Date.parse(event.scheduled_at) > Date.now()} onPress={() => void c.attempt(async () => { await c.perform({ kind: "event", resource_id: event.id, expected_version: event.version, status }); await load() })} />)}</View>
        </View>)}{events.length >= 200 ? <Copy>Показаны 200 событий. Сузьте период для остальных.</Copy> : null}</> : null}
        {page === "journal" ? <>{!entries.length ? <Copy>В этом периоде нет записей.</Copy> : null}{entries.map(entry => <View key={entry.id} style={styles.card}><ProposalCopy proposal={{ kind: "entry", summary: "", entry: entry.data }} /><View style={styles.row}><Button label="Исправить" onPress={() => c.setEditor({ page: entry.kind, entry })} /><Button label="Удалить" disabled={c.busy} onPress={() => Alert.alert("Удалить запись?", "Она исчезнет из дневника и итогов.", [{ text: "Отмена" }, { text: "Удалить", style: "destructive", onPress: () => void c.attempt(async () => { await c.perform({ kind: "delete_entry", resource_id: entry.id, expected_version: entry.version }); await load(); await onChanged() }) }])} /></View></View>)}{entries.length >= 200 ? <Copy>Показаны последние 200 записей. Сузьте период для просмотра остальных; сводка считает весь выбранный период.</Copy> : null}</> : null}
        {page === "supply" && supply ? <>{supply.reason ? <Copy>{supply.reason}</Copy> : null}{supply.items?.map((item, i) => <View key={i} style={styles.card}>
            <Copy>{item.name}</Copy>
            {item.available ? <>{item.projected_shortage_at ? <Copy>По прогнозу не хватит к: {dateLabel(item.projected_shortage_at, zone)}</Copy> : null}<Copy>Нужно: {item.required} {item.unit ? unitLabels[item.unit] : ""}; остаток по журналу: {item.home_remaining}. Докупить: {item.packages} уп. Цена: {item.price ?? "неизвестна"} ₽, сумма: {item.estimated_cost ?? "неизвестна"} ₽. На складе: {item.stock ?? "неизвестно"}.</Copy>
                {item.variant_id && !!item.packages && item.stock != null && item.stock >= item.packages ? <Button label={added.includes(i) ? "✓ Добавлено в корзину" : "Добавить " + item.packages + " уп. в корзину"} disabled={basket.updating || added.includes(i)} onPress={() => Alert.alert("Добавить в корзину?", item.name + ": " + item.packages + " уп. Фактическая стоимость проверяется в корзине.", [{ text: "Отмена" }, { text: "Добавить", onPress: () => void c.attempt(async () => { await basket.addItem(item.variant_id!, item.packages!); setAdded(values => [...values, i]) }) }])} /> : null}</> : <Copy>{item.reason}</Copy>}
        </View>)}<Copy>{supply.note}</Copy></> : null}
    </>
}

const styles = StyleSheet.create({
    panel: { borderWidth: 1, borderRadius: 16, padding: 4, gap: 8 },
    row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    button: { paddingHorizontal: 14, paddingVertical: 12, borderRadius: 12, alignSelf: "flex-start", minHeight: 44 },
    card: { padding: 12, borderRadius: 12, borderWidth: 1, borderColor: "#8191a333", gap: 10, marginVertical: 5 },
    field: { gap: 5, marginVertical: 4 },
    input: { borderWidth: 1, borderRadius: 10, padding: 12, minHeight: 46, fontSize: 16 },
    toggle: { flexDirection: "row", alignItems: "center", gap: 12, paddingVertical: 8 },
    modalHeader: { paddingTop: 16, paddingHorizontal: 20, flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    modal: { padding: 20, paddingBottom: 60, gap: 12 },
})
