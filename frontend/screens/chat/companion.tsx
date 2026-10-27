import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useCallback, useEffect, useRef, useState } from "react"
import { useIsFocused } from "@react-navigation/native"
import { ActivityIndicator, Alert, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from "react-native"
import { useBasketMutations } from "@/hooks/basket/use-basket-mutations"
import { getErrorMessage } from "@/utils/errors"
import { actCompanion, eraseCompanion, getCompanion, getCompanionAvailability, getCompanionEntries, getCompanionEvents, getCompanionSummary, getCompanionSupply, getNutritionSuggestion, requestKey } from "@/services/api/companion"
import type { CompanionAction, CompanionCard, CompanionEntry, CompanionSettings, CompanionState, EntryData, Nutrition, PlanData, ProfileData, Proposal, Stage, Summary, Supply, Unit } from "@/services/api/companion"
import type { AIMessageRead } from "@/services/api/ai-chat.types"
import { CompanionActionCancelled, withStorageConsent } from "@/screens/chat/companion-consent"
import { calendarDate, deviceCompanionTimezone, formatCompanionDate as dateLabel, localDateTime, localEntryTimestamp } from "@/screens/chat/companion-timezones"
import { useDeviceClock } from "@/hooks/chat/use-device-clock"
import { DialogueCards, DialoguePanel } from "@/screens/chat/companion-dialogue"
import type { MentorPage } from "@/screens/chat/mentor-data"
import { goalLabels } from "@/screens/chat/mentor-data"
import { MentorIcon, useMentorPalette } from "@/screens/chat/mentor-ui"

type Page = "home" | "consent" | "profile" | "plan" | "meal" | "weight" | "wellbeing" | "nutrition" | "settings" | "journal" | "events" | "summary" | "supply"
type Editor = { page: Page; proposal?: Proposal; entry?: CompanionEntry }
type Controller = ReturnType<typeof useCompanion>
const unitLabels: Record<Unit, string> = { get mg() { return mt("мг") }, get mcg() { return mt("мкг") }, get g() { return mt("г") }, get ml() { return mt("мл") }, get capsule() { return mt("капсул") }, get tablet() { return mt("таблеток") }, get IU() { return mt("МЕ") } }
const settingsDefault: CompanionSettings = { timezone: "UTC", nutrition_auto_eligible: false, course_reminders: false, daily_time: null, weight_time: null, weekly_time: null, weekly_day: 6, supply_reminders: false, supply_days: 7 }
const emptyNutrition = (): Nutrition => ({ kcal: "", protein: "", fat: "", carbs: "" })
const numberOrNull = (value: string) => value.trim() ? Number(value.replace(",", ".")) : null
const legacyEntryPage = (kind?: EntryData["kind"]): Page => kind === "workout" || kind === "measurement" || kind === "progress_photo" ? "journal" : kind ?? "meal"
const editorTitles: Record<Page, string> = {
    get home() { return mt("Мой наставник") }, get consent() { return mt("Начнём знакомство") }, get profile() { return mt("Мой профиль") }, get plan() { return mt("Мой курс") },
    get meal() { return mt("Добавить еду") }, get weight() { return mt("Добавить вес") }, get wellbeing() { return mt("Самочувствие") }, get nutrition() { return mt("Настроить питание") },
    get settings() { return mt("Настройки") }, get journal() { return mt("Мой дневник") }, get events() { return mt("События курса") }, get summary() { return mt("Мои результаты") }, get supply() { return mt("Запас курса") },
}

export function useCompanion(enabled = true) {
    useLanguage()
    const focused = useIsFocused()
    const clock = useDeviceClock()
    const [state, setState] = useState<CompanionState | null>(null)
    const [initialized, setInitialized] = useState(false)
    const [busy, setBusy] = useState(false)
    const busyRef = useRef(false)
    const retryKeys = useRef(new Map<string, string>())
    const [error, setError] = useState("")
    const [editor, setEditor] = useState<Editor | null>(null)
    const [mentorPage, setMentorPage] = useState<MentorPage | null>("today")
    const refreshSequence = useRef(0)
    const protocolRef = useRef<1 | 2>(1)
    const refresh = useCallback(async () => {
        if (!enabled || Platform.OS === "web") return
        const sequence = ++refreshSequence.current
        try {
            const availability = await getCompanionAvailability()
            if (sequence !== refreshSequence.current) return
            if (availability.available) {
                setState(previous => previous ?? availability)
                const next = await getCompanion()
                if (sequence !== refreshSequence.current) return
                setState(next)
                protocolRef.current = next.dialogue_protocol ?? 1
                setError("")
                return next
            }
            setState(availability)
            setError("")
            return availability
        } catch (e) { if (sequence === refreshSequence.current) setError(getErrorMessage(e)) }
        finally { if (sequence === refreshSequence.current) setInitialized(true) }
    }, [enabled])
    useEffect(() => { if (focused && enabled) void refresh() }, [focused, enabled, refresh, clock])
    useEffect(() => () => { refreshSequence.current++ }, [enabled])
    const resolveEnabled = async () => {
        if (Platform.OS === "web") return false
        if (state?.profile) return state.profile.enabled
        if (state?.available === false) return false
        const next = await refresh()
        if (!next) throw new Error(mt("Не удалось загрузить чат. Попробуйте ещё раз."))
        return !!next.profile?.enabled
    }
    const perform = async (action: CompanionAction) => {
        if (busyRef.current) throw new Error(mt("Дождитесь завершения предыдущего действия"))
        busyRef.current = true; setBusy(true); setError("")
        try {
            const payload = await withStorageConsent(state, action, version => new Promise(resolve => {
                Alert.alert(mt("Сохранить личные данные?"), mt("Приложение сохранит профиль, курс и дневник; нужный контекст будет передаваться OpenAI для ответов. Данные можно удалить в настройках. Нажимая кнопку ниже, вы подтверждаете возраст 18+ и согласие на обработку этих данных (") + version + ").", [
                    { text: mt("Не сохранять"), style: "cancel", onPress: () => resolve(false) },
                    { text: mt("Мне есть 18 — сохранить"), onPress: () => resolve(true) },
                ], { cancelable: true, onDismiss: () => resolve(false) })
            }))
            const identity = JSON.stringify(action)
            const key = action.request_key ?? retryKeys.current.get(identity) ?? requestKey()
            retryKeys.current.set(identity, key)
            const result = await actCompanion({ ...payload, request_key: key, ...(payload.settings ? { settings: { ...payload.settings, timezone: deviceCompanionTimezone() } } : {}) })
            retryKeys.current.delete(identity)
            setState(result.state)
            return result.state
        } finally { busyRef.current = false; setBusy(false) }
    }
    const attempt = async (operation: () => Promise<unknown>) => {
        try { await operation() } catch (e) { if (!(e instanceof CompanionActionCancelled)) setError(getErrorMessage(e)) }
    }
    return { state, initialized, setState, clock, enabled: !!state?.profile?.enabled, resolveEnabled, resolveProtocol: () => protocolRef.current, busy, error, setError, editor, setEditor, mentorPage, setMentorPage, refresh, perform, attempt }
}

function Copy({ children }: { children: React.ReactNode }) {
    useLanguage()
    const colors = useMentorPalette()
    return <Text style={[styles.copy, { color: colors.text }]}>{children}</Text>
}
function Button({ label, onPress, disabled = false, primary = false, selected = false, danger = false }: { label: string; onPress: () => void; disabled?: boolean; primary?: boolean; selected?: boolean; danger?: boolean }) {
    useLanguage()
    const colors = useMentorPalette()
    const emphasized = primary || selected
    return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled, selected }} disabled={disabled} onPress={onPress} style={({ pressed }) => [styles.button, primary ? styles.primaryButton : null, { backgroundColor: emphasized ? colors.greenBright : colors.soft, opacity: disabled ? 0.4 : pressed ? 0.75 : 1 }]}><Text style={[styles.buttonText, { color: emphasized ? "#FFFFFF" : danger ? "#B55353" : colors.green }]}>{label}</Text></Pressable>
}
function Field({ label, value, onChange, numeric = false, multiline = false, disabled = false }: { label: string; value: unknown; onChange: (value: string) => void; numeric?: boolean; multiline?: boolean; disabled?: boolean }) {
    useLanguage()
    const colors = useMentorPalette()
    return <View style={styles.field}><Text style={[styles.fieldLabel, { color: colors.muted }]}>{label}</Text><TextInput accessibilityLabel={label} editable={!disabled} value={value == null ? "" : String(value)} onChangeText={onChange} keyboardType={numeric ? "decimal-pad" : "default"} autoCapitalize="none" multiline={multiline} textAlignVertical={multiline ? "top" : "center"} selectionColor={colors.greenBright} style={[styles.input, multiline ? styles.multilineInput : null, { color: colors.text, backgroundColor: colors.soft, borderColor: colors.border, opacity: disabled ? 0.55 : 1 }]} /></View>
}
function Toggle({ label, value, onChange, disabled = false }: { label: string; value: boolean; onChange: (value: boolean) => void; disabled?: boolean }) {
    useLanguage()
    const colors = useMentorPalette()
    return <View style={[styles.toggle, { backgroundColor: colors.soft, opacity: disabled ? 0.55 : 1 }]}><View style={{ flex: 1 }}><Copy>{label}</Copy></View><Switch accessibilityLabel={label} disabled={disabled} value={value} onValueChange={onChange} trackColor={{ false: colors.border, true: colors.greenBright }} thumbColor="#FFFFFF" ios_backgroundColor={colors.border} /></View>
}
function Choices<T extends string>({ options, value, onChange }: { options: Record<T, string>; value?: string | null; onChange: (value: T) => void }) {
    useLanguage()
    return <View style={styles.row}>{(Object.keys(options) as T[]).map(key => <Button key={key} selected={value === key} label={(value === key ? "✓ " : "") + options[key]} onPress={() => onChange(key)} />)}</View>
}
function NutritionFields({ value, onChange, disabled = false }: { value: Nutrition; onChange: (n: Nutrition) => void; disabled?: boolean }) {
    useLanguage()
    const labels = { kcal: mt("Калории, ккал"), protein: mt("Белки, г"), fat: mt("Жиры, г"), carbs: mt("Углеводы, г") }
    return <>{(Object.keys(labels) as (keyof Nutrition)[]).map(key => <Field key={key} label={labels[key]} value={value[key]} numeric disabled={disabled} onChange={text => onChange({ ...value, [key]: text.replace(",", ".") })} />)}</>
}
function NutritionCopy({ value }: { value: Nutrition }) {
    useLanguage(); return <Copy>{value.kcal} {mt(" ккал · Б ")}{value.protein} {mt(" · Ж ")}{value.fat} {mt(" · У ")}{value.carbs} {mt(" г")}</Copy> }

function ProposalCopy({ proposal, clock }: { proposal: Proposal; clock: string }) {
    useLanguage()
    if (proposal.plan) return <><Copy>{mt("Курс: ")}{proposal.plan.name} · {proposal.plan.timezone}</Copy>{proposal.plan.items.map((item, i) => <View key={i} style={styles.card}>
        <Copy>{item.name}{item.variant_id ? mt(" · вариант #") + item.variant_id : ""}</Copy>
        {item.stages.map((stage, j) => <Copy key={j}>{stage.start_date} — {stage.end_date}: {stage.amount} {unitLabels[stage.unit]}, {stage.times.join(", ")}; {stage.weekdays.length ? mt("дни недели: ") + stage.weekdays.map(d => [mt("пн"), mt("вт"), mt("ср"), mt("чт"), mt("пт"), mt("сб"), mt("вс")][d]).join(", ") : mt("каждые ") + stage.interval_days + mt(" дн.")}</Copy>)}
        <Copy>{mt("В упаковке: ")}{item.package_amount ?? mt("не уточнено")} {item.package_unit ? unitLabels[item.package_unit] : ""}{mt(". Фактический запас на начало этой версии: ")}{item.home_amount ?? mt("не уточнён")} {item.package_unit ? unitLabels[item.package_unit] : ""}.</Copy>
        {item.package_source_name ? <Copy>{mt("Источник размера упаковки: ")}{item.package_source_name}</Copy> : null}
    </View>)}<Copy>{mt("Это ваша готовая схема, а не назначение AI. Проверьте каждый этап и остаток перед подтверждением.")}</Copy></>
    if (proposal.entry) {
        const entry = proposal.entry
        return <><Copy>{dateLabel(entry.occurred_at, clock)} · {entry.kind === "meal" ? entry.name : entry.kind === "weight" ? String(entry.weight_kg) + mt(" кг") : entry.kind === "workout" ? entry.workout?.name : entry.kind === "measurement" ? mt("Замеры") : entry.kind === "progress_photo" ? mt("Фото прогресса") : mt("Самочувствие")}</Copy>
            {entry.portion_g ? <Copy>{mt("Порция: ")}{entry.portion_g} {mt(" г")}</Copy> : null}
            {entry.nutrition ? <NutritionCopy value={entry.nutrition} /> : null}
            {entry.estimated ? <Copy>{mt("Приблизительная оценка: ")}{entry.assumptions || mt("проверьте состав и размер порции")}</Copy> : null}
            {entry.kind === "wellbeing" ? <Copy>{mt("Самочувствие ")}{entry.wellbeing ?? "—"}{mt("/5 · аппетит ")}{entry.appetite ?? "—"}{mt("/5 · энергия ")}{entry.energy ?? "—"}{mt("/5 · сон ")}{entry.sleep_hours ?? "—"} {mt(" ч")}</Copy> : null}
            {entry.note ? <Copy>{entry.note}</Copy> : null}</>
    }
    if (proposal.nutrition) return <NutritionCopy value={proposal.nutrition} />
    if (proposal.profile) {
        const p = proposal.profile
        return <><Copy>{mt("Цель: ")}{p.goal ? goalLabels[p.goal] : mt("не указана")}{p.custom_goal ? ` · ${p.custom_goal}` : ""}{mt(". Возраст ")}{p.age ?? "—"}{mt(", рост ")}{p.height_cm ?? "—"} {mt(" см, целевой вес ")}{p.target_weight_kg ?? "—"} {mt(" кг.")}</Copy><Copy>{mt("Пол: ")}{p.sex === "female" ? mt("женский") : p.sex === "male" ? mt("мужской") : mt("не указан")}{mt(". Активность: ")}{({ low: mt("низкая"), light: mt("лёгкая"), moderate: mt("умеренная"), high: mt("высокая") })[p.activity ?? "low"]}.</Copy><Copy>{mt("Предпочтения: ")}{p.preferences || "—"}{mt(". Ограничения: ")}{p.restrictions || "—"}.</Copy>{p.nutrition ? <NutritionCopy value={p.nutrition} /> : null}</>
    }
    return null
}

export function CompanionCards({ controller: c, message, onChanged }: { controller: Controller; message: AIMessageRead; onChanged: () => Promise<void> }) {
    useLanguage()
    if (!c.enabled || Platform.OS === "web") return null
    const action = async (card: CompanionCard, kind: "confirm" | "cancel", edit = false) => {
        if (edit && c.state?.dialogue_protocol === 2) {
            await c.perform({ kind: "dialogue_edit", message_id: message.id, action_id: card.id, action_token: card.action_token ?? "" })
            await onChanged()
            return
        }
        await c.perform({ kind, message_id: message.id, action_id: card.id, action_token: card.action_token ?? "" })
        await onChanged()
        if (edit) c.setEditor({ page: card.kind === "entry" ? legacyEntryPage(card.proposal.entry?.kind) : card.kind, proposal: card.proposal })
    }
    return <><DialogueCards controller={c} message={message} onChanged={onChanged} />{message.companion_cards?.map(card => <View key={card.id} style={styles.card}>
        <Copy>{card.state === "confirmed" ? mt("✓ Сохранено") : card.state === "cancelled" ? mt("Отменено") : mt("Черновик — проверьте данные")}</Copy>
        <Copy>{card.summary}</Copy><ProposalCopy proposal={card.proposal} clock={c.clock} />
        {card.state === "pending" ? <View style={styles.row}>
            <Button label={mt("Подтвердить")} primary disabled={c.busy} onPress={() => void c.attempt(() => action(card, "confirm"))} />
            <Button label={mt("Исправить")} disabled={c.busy} onPress={() => void c.attempt(() => action(card, "cancel", true))} />
            <Button label={mt("Отмена")} disabled={c.busy} onPress={() => void c.attempt(() => action(card, "cancel"))} />
        </View> : null}
    </View>)}</>
}

export function CompanionPanel({ controller: c, onChanged, openRequested, onPrompt, sending, workspaceVisible = false, navigationVisible = true }: { controller: Controller; onChanged: () => Promise<void>; openRequested?: boolean; onPrompt?: (text: string) => Promise<unknown>; sending?: boolean; workspaceVisible?: boolean; navigationVisible?: boolean }) {
    useLanguage()
    const colors = useMentorPalette()
    const hasProfile = !!c.state?.profile
    const setEditor = c.setEditor
    useEffect(() => { if (openRequested && hasProfile && c.state?.dialogue_protocol !== 2) setEditor({ page: "home" }) }, [openRequested, hasProfile, setEditor, c.state?.dialogue_protocol])
    if (Platform.OS === "web" || !c.state?.available) return null
    const changed = async () => { await c.refresh(); await onChanged() }
    const dialogue = c.state.dialogue_protocol === 2 && onPrompt
    return <View style={dialogue ? undefined : [styles.panel, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {navigationVisible ? dialogue ? <DialoguePanel controller={c} onChanged={onChanged} onPrompt={onPrompt!} sending={sending} /> : <Button label={mt("Мой курс · дневник · прогресс")} disabled={!c.state.profile && !c.error} onPress={() => c.setEditor({ page: c.state?.profile ? "home" : "consent" })} /> : null}
        {c.error && !workspaceVisible ? <><Copy>{c.error}</Copy><Button label={mt("Обновить")} onPress={() => void changed()} /></> : null}
        <Modal visible={!!c.editor} animationType="slide" presentationStyle="pageSheet" onRequestClose={() => c.setEditor(null)}>
            <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.mint }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
                <View style={[styles.modalHeader, { backgroundColor: colors.surface }]}>
                    <View style={styles.modalBrandRow}>
                        <View style={[styles.modalAvatar, { backgroundColor: colors.mint }]}><MentorIcon name="leaf" size={27} /></View>
                        <Text style={[styles.modalBrand, { color: colors.green }]}>{mt("Наставник ElixirPeptide")}</Text>
                        {c.busy ? <ActivityIndicator color={colors.greenBright} /> : null}
                        <Pressable accessibilityRole="button" accessibilityLabel={mt("Закрыть")} onPress={() => c.setEditor(null)} style={({ pressed }) => [styles.modalClose, { backgroundColor: colors.soft, opacity: pressed ? 0.65 : 1 }]}><Text style={[styles.modalCloseText, { color: colors.green }]}>×</Text></Pressable>
                    </View>
                    <Text accessibilityRole="header" style={[styles.modalTitle, { color: colors.text }]}>{c.editor?.entry ? mt("Изменить запись") : editorTitles[c.editor?.page ?? "home"]}</Text>
                </View>
                <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.modal}>
                    <View style={[styles.modalCard, { backgroundColor: colors.surface }]}>
                        {c.error ? <Copy>{c.error}</Copy> : null}
                        {c.editor ? <CompanionContent key={JSON.stringify(c.editor)} controller={c} onChanged={changed} /> : null}
                    </View>
                </ScrollView>
            </KeyboardAvoidingView>
        </Modal>
    </View>
}

function CompanionContent({ controller: c, onChanged }: { controller: Controller; onChanged: () => Promise<void> }) {
    useLanguage()
    const page = c.editor!.page
    const state = c.state!
    const profile = state.profile
    const version = profile?.version
    const open = (page: Page) => { c.setError(""); c.setEditor({ page }) }
    const save = async (action: CompanionAction) => { await c.perform(action); c.setEditor(state.dialogue_protocol === 2 ? null : { page: "home" }); await onChanged() }
    if (page === "consent") return <ConsentForm controller={c} onSave={save} />
    if (["profile", "meal", "weight", "wellbeing", "nutrition", "plan", "settings"].includes(page)) return <ManualForm controller={c} onSave={save} onChanged={onChanged} />
    if (page === "summary" || page === "journal" || page === "events" || page === "supply") return <ReviewPanel controller={c} onChanged={onChanged} />
    return <>
        <Copy>{mt("Сопровождение ")}{profile?.enabled ? mt("включено") : mt("выключено")}{mt(". Данные сохраняются после подтверждения; AI не назначает препараты и не меняет дозировки.")}</Copy>
        {!profile?.enabled ? <Button label={mt("Возобновить сопровождение")} onPress={() => open("consent")} /> : null}
        <View style={styles.row}>{(["profile", "plan", "meal", "weight", "wellbeing", "journal", "summary", "supply", "settings", "events"] as Page[]).map((p, i) => <Button key={p} label={[mt("Профиль"), mt("Мой курс"), mt("Записать еду"), mt("Вес"), mt("Самочувствие"), mt("Дневник"), mt("Итоги"), mt("Запас"), mt("Настройки"), mt("История событий")][i]} onPress={() => open(p)} />)}</View>
        {state.today ? <><Copy>{mt("Сегодня записано: ")}{state.today.meals_logged} {mt(" приёмов пищи")}</Copy><NutritionCopy value={state.today.nutrition} /></> : null}
        {profile?.data.nutrition ? <><Copy>{mt("Ваш ориентир на день:")}</Copy><NutritionCopy value={profile.data.nutrition} /></> : null}
        <Button label={mt("КБЖУ: вручную или рассчитать")} onPress={() => open("nutrition")} />
        {state.plan ? <>
            <Copy>{mt("Курс: ")}{state.plan.data.name} {mt(" · версия ")}{state.plan.version} · {({ active: mt("активен"), paused: mt("на паузе"), completed: mt("завершён") } as Record<string, string>)[state.plan.status]}</Copy>
            <ProposalCopy proposal={{ kind: "plan", summary: "", plan: state.plan.data }} clock={c.clock} />
            <View style={styles.row}>
                {state.plan.status === "active" ? <Button label={mt("Пауза")} disabled={c.busy} onPress={() => void c.attempt(() => save({ kind: "plan_status", expected_version: version, status: "paused" }))} /> : null}
                {state.plan.status === "paused" ? <Button label={mt("Обновить и возобновить")} onPress={() => open("plan")} /> : null}
                {state.plan.status !== "completed" ? <Button label={mt("Завершить курс")} disabled={c.busy} onPress={() => Alert.alert(mt("Завершить курс?"), mt("Будущие напоминания будут отменены, история останется."), [{ text: mt("Отмена") }, { text: mt("Завершить"), onPress: () => void c.attempt(() => save({ kind: "plan_status", expected_version: version, status: "completed" })) }])} /> : null}
            </View>
        </> : <Copy>{mt("Пришлите свою готовую схему в чат или заполните «Мой курс». Бот подготовит карточку для проверки.")}</Copy>}
        <Copy>{mt("События сегодня и на ближайшие 7 дней · время телефона")}</Copy>
        {state.events?.map(event => <View key={event.id} style={styles.card}>
            <Copy>{dateLabel(event.scheduled_at, c.clock)} · {event.data.name} · {event.data.amount} {unitLabels[event.data.unit]}</Copy>
            <Copy>{event.status === "pending" ? mt("Нет отметки") : event.status === "done" ? mt("Выполнено") : mt("Пропущено")}</Copy>
            <View style={styles.row}>{(["done", "skipped", "pending"] as const).filter(status => status !== event.status).map(status => <Button key={status} label={status === "done" ? mt("Выполнено") : status === "skipped" ? mt("Пропущено") : mt("Снять отметку")} disabled={c.busy || status === "done" && Date.parse(event.scheduled_at) > Date.now()} onPress={() => void c.attempt(() => save({ kind: "event", resource_id: event.id, expected_version: event.version, status }))} />)}</View>
        </View>)}
    </>
}

function ConsentForm({ controller: c, onSave }: { controller: Controller; onSave: (action: CompanionAction) => Promise<void> }) {
    useLanguage()
    const [adult, setAdult] = useState(false)
    const [accepted, setAccepted] = useState(false)
    return <>
        <Copy>{mt("Чат поможет вести вашу готовую схему, питание, вес и самочувствие. Он не заменяет врача, не назначает пептиды и не корректирует дозировки. При ухудшении состояния обратитесь за медицинской помощью.")}</Copy>
        <Copy>{mt("По вашему согласию приложение хранит профиль, курс, дневник и сообщения сопровождения. Для ответов нужный контекст и отправленные вами вложения передаются OpenAI. Напоминания по умолчанию выключены; данные можно удалить в настройках. Не отправляйте чужие медицинские документы.")}</Copy>
        <Toggle label={mt("Мне исполнилось 18 лет")} value={adult} onChange={setAdult} />
        <Toggle label={mt("Согласен на обработку указанных данных и передачу контекста OpenAI для сопровождения (") + c.state?.consent_version + ")"} value={accepted} onChange={setAccepted} />
        <Button label={mt("Включить")} primary disabled={!adult || !accepted || c.busy} onPress={() => void c.attempt(() => onSave({ kind: "enable", adult_confirmed: adult, consent_version: c.state!.consent_version, settings: { ...settingsDefault, timezone: deviceCompanionTimezone() } }))} />
    </>
}

function ManualForm({ controller: c, onSave, onChanged }: { controller: Controller; onSave: (action: CompanionAction) => Promise<void>; onChanged: () => Promise<void> }) {
    useLanguage()
    const editor = c.editor!
    const page = editor.page
    const profile = c.state!.profile!
    const [person, setPerson] = useState<ProfileData>(editor.proposal?.profile ?? profile.data)
    const [nutrition, setNutrition] = useState<Nutrition>(editor.proposal?.nutrition ?? profile.data.nutrition ?? emptyNutrition())
    const [entry, setEntry] = useState<EntryData>(editor.entry?.data ?? editor.proposal?.entry ?? { kind: page as EntryData["kind"], occurred_at: new Date().toISOString(), ...(page === "meal" ? { nutrition: emptyNutrition() } : {}) })
    const [entryDateText, setEntryDateText] = useState(() => localDateTime(entry.occurred_at))
    const [plan, setPlan] = useState<PlanData>(editor.proposal?.plan ?? c.state!.plan?.data ?? { name: "", timezone: deviceCompanionTimezone(), items: [] })
    const [settings, setSettings] = useState<CompanionSettings>({ ...settingsDefault, ...profile.settings })
    const [suggestionNote, setSuggestionNote] = useState("")
    const [ruleVersion, setRuleVersion] = useState<string | undefined>()
    const [calculating, setCalculating] = useState(false)
    const calculationRef = useRef(false)
    const version = profile.version
    const convertOpenEditor = useRef(() => {})
    convertOpenEditor.current = () => {
        setEntryDateText(localDateTime(entry.occurred_at))
        if (!editor.proposal?.plan && !c.state?.plan) setPlan(previous => ({ ...previous, timezone: deviceCompanionTimezone() }))
    }
    useEffect(() => { convertOpenEditor.current() }, [c.clock]) // Only clock changes, not typing, reset the local-time input.
    const save = (action: CompanionAction) => void c.attempt(() => onSave({ expected_version: version, ...action }))
    return <>
        {page === "profile" ? <>
            <Copy>{mt("Профиль: заполняйте только нужные для сопровождения данные.")}</Copy>
            <Choices options={goalLabels} value={person.goal} onChange={goal => setPerson({ ...person, goal })} />
            {person.goal === "custom" ? <Field label={mt("Своя цель")} value={person.custom_goal} onChange={custom_goal => setPerson({ ...person, custom_goal })} /> : null}
            {c.state?.mentor?.latest_weight ? <Copy>{mt("Последний сохранённый вес: ")}{c.state.mentor.latest_weight.data.weight_kg} {mt(" кг · ")}{dateLabel(c.state.mentor.latest_weight.occurred_at, c.clock)}</Copy> : null}
            <Field label={mt("Возраст, лет")} value={person.age} numeric onChange={text => setPerson({ ...person, age: numberOrNull(text) })} />
            <Choices options={{ male: mt("Мужской"), female: mt("Женский") }} value={person.sex} onChange={sex => setPerson({ ...person, sex })} />
            <Field label={mt("Рост, см")} value={person.height_cm} numeric onChange={text => setPerson({ ...person, height_cm: numberOrNull(text) })} />
            <Field label={mt("Целевой вес, кг")} value={person.target_weight_kg} numeric onChange={text => setPerson({ ...person, target_weight_kg: numberOrNull(text) })} />
            <Choices options={{ low: mt("Низкая активность"), light: mt("Лёгкая"), moderate: mt("Умеренная"), high: mt("Высокая") }} value={person.activity} onChange={activity => setPerson({ ...person, activity })} />
            <Field label={mt("Пищевые предпочтения")} multiline value={person.preferences} onChange={preferences => setPerson({ ...person, preferences })} />
            <Field label={mt("Известные вам ограничения")} multiline value={person.restrictions} onChange={restrictions => setPerson({ ...person, restrictions })} />
            <Button label={mt("Сохранить профиль")} primary disabled={c.busy} onPress={() => save({ kind: "profile", profile: person })} />
        </> : null}
        {page === "nutrition" ? <>
            <Copy>{mt("КБЖУ на день: готовые значения можно внести вручную. Авторасчёт предлагает стартовый ориентир и не меняет прошлые записи.")}</Copy>
            <Copy>{mt("Авторасчёт не предназначен для беременности, грудного вскармливания, расстройств пищевого поведения, состояний и лечения, требующих индивидуального питания (например, болезней почек или сахароснижающих препаратов). В этих случаях используйте ориентир специалиста.")}</Copy>
            <Toggle label={mt("Подтверждаю, что перечисленные ограничения ко мне не относятся")} value={!!profile.settings.nutrition_auto_eligible} disabled={c.busy || calculating} onChange={value => void c.attempt(async () => {
                await c.perform({ kind: "settings", expected_version: version, settings: { ...settingsDefault, ...profile.settings, nutrition_auto_eligible: value } })
                setNutrition(profile.data.nutrition ?? emptyNutrition()); setRuleVersion(undefined); setSuggestionNote("")
            })} />
            <Button label={calculating ? mt("Считаем…") : mt("Предложить расчёт")} disabled={c.busy || calculating || !profile.settings.nutrition_auto_eligible} onPress={() => void c.attempt(async () => {
                if (calculationRef.current) return
                calculationRef.current = true; setCalculating(true); setSuggestionNote("")
                try {
                    const result = await getNutritionSuggestion()
                    if (result.available && result.nutrition) {
                        setNutrition(result.nutrition); setRuleVersion(result.rule_version)
                        setSuggestionNote((result.note ? mt(result.note) : mt("Проверьте перед сохранением.")) + mt(" Поддержание: ~") + result.maintenance_kcal + mt(" ккал; ") + (Number(result.surplus_kcal) > 0 ? mt("профицит: ~") + result.surplus_kcal : mt("дефицит: ~") + result.deficit_kcal) + mt(" ккал. Версия: ") + result.rule_version)
                    } else { setRuleVersion(undefined); setSuggestionNote(result.reason ? mt(result.reason) : mt("Расчёт недоступен")) }
                } finally { calculationRef.current = false; setCalculating(false) }
            })} />
            {suggestionNote ? <Copy>{suggestionNote}</Copy> : null}
            <NutritionFields value={nutrition} disabled={calculating || c.busy} onChange={value => { setNutrition(value); setRuleVersion(undefined); setSuggestionNote(mt("Ручные значения — проверьте перед сохранением.")) }} />
            <Button label={mt("Подтвердить КБЖУ")} primary disabled={c.busy || calculating} onPress={() => save({ kind: "nutrition", nutrition, nutrition_rule_version: ruleVersion })} />
        </> : null}
        {["meal", "weight", "wellbeing"].includes(page) ? <>
            <Field label={mt("Дата и время телефона, ГГГГ-ММ-ДД ЧЧ:ММ")} value={entryDateText} onChange={value => {
                setEntryDateText(value)
                try { setEntry({ ...entry, occurred_at: localEntryTimestamp(value, entry.occurred_at) }) } catch { /* Allow incomplete input while typing. */ }
            }} />
            {page === "meal" ? <><Field label={mt("Что съели")} value={entry.name} onChange={name => setEntry({ ...entry, name })} /><Field label={mt("Порция, г (если известна)")} value={entry.portion_g} numeric onChange={text => setEntry({ ...entry, portion_g: numberOrNull(text) })} /><NutritionFields value={entry.nutrition ?? emptyNutrition()} onChange={nutrition => setEntry({ ...entry, nutrition })} /><Toggle label={mt("Приблизительная оценка")} value={!!entry.estimated} onChange={estimated => setEntry({ ...entry, estimated })} />{entry.estimated ? <Field label={mt("Допущения оценки")} value={entry.assumptions} onChange={assumptions => setEntry({ ...entry, assumptions })} /> : null}<Copy>{mt("Можно отправить фото еды в чат — AI предложит оценку для подтверждения.")}</Copy></> : null}
            {page === "weight" ? <Field label={mt("Вес, кг")} value={entry.weight_kg} numeric onChange={text => setEntry({ ...entry, weight_kg: numberOrNull(text) })} /> : null}
            {page === "wellbeing" ? <>{(["wellbeing", "appetite", "energy", "sleep_hours"] as const).map((key, i) => <Field key={key} label={[mt("Самочувствие, 1–5"), mt("Аппетит, 1–5"), mt("Энергия, 1–5"), mt("Сон, часов")][i]} value={entry[key]} numeric onChange={text => setEntry({ ...entry, [key]: numberOrNull(text) })} />)}</> : null}
            <Field label={mt("Комментарий")} multiline value={entry.note} onChange={note => setEntry({ ...entry, note })} />
            <Button label={editor.entry ? mt("Сохранить исправление") : mt("Подтвердить запись")} primary disabled={c.busy} onPress={() => void c.attempt(() => onSave({ kind: "entry", entry: { ...entry, occurred_at: localEntryTimestamp(entryDateText, entry.occurred_at) }, resource_id: editor.entry?.id, expected_version: editor.entry?.version }))} />
        </> : null}
        {page === "plan" ? <><Copy>{mt("Перенесите готовую схему. Каждый этап задаётся отдельно. При обновлении старые отметки сохранятся, будущие события заменятся. Укажите фактический остаток на момент обновления.")}</Copy><Field label={mt("Название курса")} value={plan.name} onChange={name => setPlan({ ...plan, name })} /><Copy>{plan.timezone === deviceCompanionTimezone() ? mt("Время определяется по телефону автоматически.") : mt("Исходная схема записана в {0}. Её время не сдвигается при поездке; события в дневнике показаны по времени телефона.", [plan.timezone])}</Copy><PlanFields plan={plan} onChange={setPlan} /><Button label={mt("Подтвердить и сохранить курс")} primary disabled={c.busy || !plan.items.length} onPress={() => save({ kind: "plan", plan })} /></> : null}
        {page === "settings" ? <>
            <Copy>{mt("Push включается в настройках уведомлений приложения. Здесь задаётся, о чём и когда напоминать. Пустое время выключает напоминание.")}</Copy>
            <Copy>{mt("Дневник и ежедневные напоминания используют время телефона автоматически. При поездке старые записи отображаются в новом местном времени; подтверждённые события курса не переносятся.")}</Copy>
            <Toggle label={mt("Напоминать о событиях курса")} value={settings.course_reminders} onChange={course_reminders => setSettings({ ...settings, course_reminders })} />
            <Toggle label={mt("Ежедневный вопрос о самочувствии и дневнике")} value={!!settings.checkin_time} onChange={value => setSettings({ ...settings, checkin_time: value ? "18:00" : null })} />
            {settings.checkin_time ? <Field label={mt("Время ежедневного вопроса, ЧЧ:ММ")} value={settings.checkin_time} onChange={checkin_time => setSettings({ ...settings, checkin_time })} /> : null}
            <Toggle label={mt("Напомнить после перерыва")} value={settings.inactivity_days != null} onChange={value => setSettings({ ...settings, inactivity_days: value ? 3 : null })} />
            {settings.inactivity_days != null ? <><Field label={mt("Дней без записей, 2–30")} value={settings.inactivity_days} numeric onChange={text => setSettings({ ...settings, inactivity_days: numberOrNull(text) })} /><Field label={mt("Время напоминания после перерыва, ЧЧ:ММ")} value={settings.inactivity_time ?? "18:00"} onChange={inactivity_time => setSettings({ ...settings, inactivity_time })} /></> : null}
            {(["daily_time", "weight_time", "weekly_time"] as const).map((key, i) => <Field key={key} label={[mt("Итоги дня, ЧЧ:ММ"), mt("Напомнить внести вес, ЧЧ:ММ"), mt("Итоги недели, ЧЧ:ММ")][i]} value={settings[key]} onChange={text => setSettings({ ...settings, [key]: text || null })} />)}
            <Field label={mt("День недельной сводки: 0 пн … 6 вс")} value={settings.weekly_day} numeric onChange={text => setSettings({ ...settings, weekly_day: Number(text) })} />
            <Toggle label={mt("Напоминать о нехватке запаса")} value={settings.supply_reminders} onChange={supply_reminders => setSettings({ ...settings, supply_reminders })} />
            <Field label={mt("Проверять запас на ближайшие N дней")} value={settings.supply_days} numeric onChange={text => setSettings({ ...settings, supply_days: Number(text) })} />
            <Button label={mt("Сохранить настройки")} primary disabled={c.busy} onPress={() => save({ kind: "settings", settings })} />
            <Button label={mt("Выключить сопровождение")} disabled={c.busy} onPress={() => Alert.alert(mt("Выключить?"), mt("Напоминания прекратятся; дневник сохранится. Обычный чат начнёт новый контекст."), [{ text: mt("Отмена") }, { text: mt("Выключить"), onPress: () => void c.attempt(async () => { await c.perform({ kind: "disable", expected_version: version }); c.setEditor(null); await c.refresh() }) }])} />
            <Button label={mt("Удалить данные сопровождения")} danger disabled={c.busy} onPress={() => Alert.alert(mt("Удалить без восстановления?"), mt("Будут удалены профиль, курс, дневник и сообщения сопровождения. Удаление копий диалогов и файлов у OpenAI будет поставлено в очередь с повторными попытками."), [{ text: mt("Отмена") }, { text: mt("Удалить"), style: "destructive", onPress: () => void c.attempt(async () => { await eraseCompanion(); c.setEditor(null); await onChanged() }) }])} />
        </> : null}
    </>
}

function PlanFields({ plan, onChange }: { plan: PlanData; onChange: (plan: PlanData) => void }) {
    useLanguage()
    const blankStage = (): Stage => ({ start_date: "", end_date: "", amount: "", unit: "mg", interval_days: 1, weekdays: [], times: [""] })
    const itemChange = (i: number, patch: Partial<PlanData["items"][number]>) => onChange({ ...plan, items: plan.items.map((item, n) => n === i ? { ...item, ...patch } : item) })
    return <>{plan.items.map((item, i) => <View key={i} style={styles.card}>
        <Field label={mt("Позиция ") + (i + 1)} value={item.name} onChange={name => itemChange(i, { name })} />
        <Field label={mt("ID варианта из каталога (необязательно)")} value={item.variant_id} numeric onChange={text => itemChange(i, { variant_id: numberOrNull(text), package_source_name: null })} />
        <Field label={mt("Содержимое одной упаковки (если неизвестно — оставьте пустым)")} value={item.package_amount} numeric onChange={text => itemChange(i, { package_amount: numberOrNull(text), package_unit: text ? item.package_unit ?? "mg" : null })} />
        {item.package_amount ? <Choices options={unitLabels} value={item.package_unit} onChange={package_unit => itemChange(i, { package_unit })} /> : null}
        <Field label={mt("Фактический остаток сейчас, в единицах содержимого упаковки (не число упаковок)")} value={item.home_amount} numeric onChange={text => itemChange(i, { home_amount: text.trim() ? text.replace(",", ".") : null })} />
        {item.stages.map((stage, j) => {
            const change = (patch: Partial<Stage>) => itemChange(i, { stages: item.stages.map((s, n) => n === j ? { ...s, ...patch } : s) })
            return <View key={j} style={styles.card}>
                <Copy>{mt("Этап ")}{j + 1}</Copy>
                <Field label={mt("Начало, ГГГГ-ММ-ДД")} value={stage.start_date} onChange={start_date => change({ start_date })} />
                <Field label={mt("Конец включительно, ГГГГ-ММ-ДД")} value={stage.end_date} onChange={end_date => change({ end_date })} />
                <Field label={mt("Количество на одно событие — из вашей схемы")} value={stage.amount} numeric onChange={text => change({ amount: text.replace(",", ".") })} />
                <Choices options={unitLabels} value={stage.unit} onChange={unit => change({ unit })} />
                <Field label={mt("Время, ЧЧ:ММ; несколько через запятую")} value={stage.times.join(", ")} onChange={text => change({ times: text.split(",").map(t => t.trim()) })} />
                <Field label={mt("Интервал в днях (1 = ежедневно)")} value={stage.interval_days} numeric onChange={text => change({ interval_days: Number(text), weekdays: [] })} />
                <Copy>{mt("Или конкретные дни недели:")}</Copy>
                <View style={styles.row}>{[mt("Пн"), mt("Вт"), mt("Ср"), mt("Чт"), mt("Пт"), mt("Сб"), mt("Вс")].map((d, day) => <Button key={day} selected={stage.weekdays.includes(day)} label={(stage.weekdays.includes(day) ? "✓ " : "") + d} onPress={() => change({ interval_days: 1, weekdays: stage.weekdays.includes(day) ? stage.weekdays.filter(v => v !== day) : [...stage.weekdays, day] })} />)}</View>
                {item.stages.length > 1 ? <Button label={mt("Удалить этап из черновика")} onPress={() => itemChange(i, { stages: item.stages.filter((_, n) => n !== j) })} /> : null}
            </View>
        })}
        <Button label={mt("+ Этап")} disabled={item.stages.length >= 24} onPress={() => itemChange(i, { stages: [...item.stages, blankStage()] })} />
        <Button label={mt("Удалить позицию из черновика")} onPress={() => onChange({ ...plan, items: plan.items.filter((_, n) => n !== i) })} />
    </View>)}<Button label={mt("+ Позиция курса")} disabled={plan.items.length >= 12} onPress={() => onChange({ ...plan, items: [...plan.items, { name: "", stages: [blankStage()], home_amount: null }] })} /></>
}

function ReviewPanel({ controller: c, onChanged }: { controller: Controller; onChanged: () => Promise<void> }) {
    useLanguage()
    const page = c.editor!.page
    const [from, setFrom] = useState(calendarDate(-6))
    const [to, setTo] = useState(calendarDate(1))
    const [entries, setEntries] = useState(c.state!.entries ?? [])
    const [events, setEvents] = useState(c.state!.events ?? [])
    const [summary, setSummary] = useState<Summary | null>(null)
    const [supply, setSupply] = useState<Supply | null>(null)
    const [days, setDays] = useState("30")
    const [loading, setLoading] = useState(false)
    const [added, setAdded] = useState<number[]>([])
    const basket = useBasketMutations()
    const loadSequence = useRef(0)
    const load = async () => {
        const sequence = ++loadSequence.current
        setLoading(true)
        try {
            if (page === "supply") { const result = await getCompanionSupply(Number(days)); if (sequence === loadSequence.current) { setSupply(result); setAdded([]) } }
            else if (page === "events") { const result = await getCompanionEvents(from, to); if (sequence === loadSequence.current) setEvents(result.events) }
            else if (page === "summary") { const result = await getCompanionSummary(from, to); if (sequence === loadSequence.current) setSummary(result) }
            else { const result = await getCompanionEntries(from, to); if (sequence === loadSequence.current) setEntries(result.entries) }
        } finally { if (sequence === loadSequence.current) setLoading(false) }
    }
    const reloadForClock = useRef(() => {})
    reloadForClock.current = () => { void c.attempt(load) }
    const invalidateLoads = useCallback(() => { loadSequence.current++ }, [])
    useEffect(() => {
        reloadForClock.current()
        return invalidateLoads
    }, [c.clock, invalidateLoads]) // Requery on travel/DST; ignore responses from the previous zone.
    return <>
        <Button label={mt("Назад к плану")} onPress={() => c.setEditor({ page: "home" })} />
        {page === "supply" ? <><Field label={mt("Период прогноза, 1–90 дней")} value={days} numeric onChange={setDays} /><Copy>{mt("Расчёт не меняет схему. Покупка только по отдельному нажатию; добавление в корзину не увеличивает домашний запас.")}</Copy></> : <><Field label={mt("С даты включительно, ГГГГ-ММ-ДД")} value={from} onChange={setFrom} /><Field label={mt("До даты не включительно, ГГГГ-ММ-ДД (до 90 дней)")} value={to} onChange={setTo} /></>}
        <Button label={mt("Обновить")} disabled={loading} onPress={() => void c.attempt(load)} />
        {loading ? <ActivityIndicator /> : null}
        {page === "summary" && summary ? <><NutritionCopy value={summary.nutrition} /><Copy>{mt("Приёмов пищи: ")}{summary.meals_logged}{mt(", дней с записями: ")}{summary.days_with_meals}{mt(". Измерений веса: ")}{summary.weight_measurements}{mt("; изменение: ")}{summary.weight_change_kg == null ? mt("недостаточно данных") : summary.weight_change_kg + mt(" кг")}.</Copy><Copy>{mt("События: выполнено ")}{summary.events.done}{mt(", пропущено ")}{summary.events.skipped}{mt(", без отметки ")}{summary.events.pending}.</Copy><Copy>{mt(summary.coverage_note)}</Copy></> : null}
        {page === "events" ? <>{!events.length ? <Copy>{mt("Нет событий в выбранном периоде.")}</Copy> : null}{events.map(event => <View key={event.id} style={styles.card}>
            <Copy>{dateLabel(event.scheduled_at, c.clock)} · {event.data.name} · {event.data.amount} {unitLabels[event.data.unit]} · {event.status === "pending" ? mt("без отметки") : event.status === "done" ? mt("выполнено") : mt("пропущено")}</Copy>
            <View style={styles.row}>{(["done", "skipped", "pending"] as const).filter(status => status !== event.status).map(status => <Button key={status} label={status === "done" ? mt("Выполнено") : status === "skipped" ? mt("Пропущено") : mt("Снять отметку")} disabled={c.busy || status === "done" && Date.parse(event.scheduled_at) > Date.now()} onPress={() => void c.attempt(async () => { await c.perform({ kind: "event", resource_id: event.id, expected_version: event.version, status }); await load() })} />)}</View>
        </View>)}{events.length >= 200 ? <Copy>{mt("Показаны 200 событий. Сузьте период для остальных.")}</Copy> : null}</> : null}
        {page === "journal" ? <>{!entries.length ? <Copy>{mt("В этом периоде нет записей.")}</Copy> : null}{entries.map(entry => <View key={entry.id} style={styles.card}><ProposalCopy proposal={{ kind: "entry", summary: "", entry: entry.data }} clock={c.clock} /><View style={styles.row}>{legacyEntryPage(entry.kind) === "journal" ? <Button label={mt("Открыть")} onPress={() => { c.setEditor(null); c.setMentorPage(entry.kind === "workout" ? "workouts" : "progress") }} /> : <Button label={mt("Исправить")} onPress={() => c.setEditor({ page: legacyEntryPage(entry.kind), entry })} />}<Button label={mt("Удалить")} disabled={c.busy} onPress={() => Alert.alert(mt("Удалить запись?"), mt("Она исчезнет из дневника и итогов."), [{ text: mt("Отмена") }, { text: mt("Удалить"), style: "destructive", onPress: () => void c.attempt(async () => { await c.perform({ kind: "delete_entry", resource_id: entry.id, expected_version: entry.version }); await load(); await onChanged() }) }])} /></View></View>)}{entries.length >= 200 ? <Copy>{mt("Показаны последние 200 записей. Сузьте период для просмотра остальных; сводка считает весь выбранный период.")}</Copy> : null}</> : null}
        {page === "supply" && supply ? <>{supply.reason ? <Copy>{supply.reason ? mt(supply.reason) : null}</Copy> : null}{supply.items?.map((item, i) => <View key={i} style={styles.card}>
            <Copy>{item.name}</Copy>
            {item.available ? <>{item.projected_shortage_at ? <Copy>{mt("По прогнозу не хватит к: ")}{dateLabel(item.projected_shortage_at, c.clock)}</Copy> : null}<Copy>{mt("Нужно: ")}{item.required} {item.unit ? unitLabels[item.unit] : ""}{mt("; остаток по журналу: ")}{item.home_remaining}{mt(". Докупить: ")}{item.packages} {mt(" уп. Цена: ")}{item.price ?? mt("неизвестна")} {mt(" ₽, сумма: ")}{item.estimated_cost ?? mt("неизвестна")} {mt(" ₽. На складе: ")}{item.stock ?? mt("неизвестно")}.</Copy>
                {item.variant_id && !!item.packages && item.stock != null && item.stock >= item.packages ? <Button label={added.includes(i) ? mt("✓ Добавлено в корзину") : mt("Добавить ") + item.packages + mt(" уп. в корзину")} disabled={basket.updating || added.includes(i)} onPress={() => Alert.alert(mt("Добавить в корзину?"), item.name + ": " + item.packages + mt(" уп. Фактическая стоимость проверяется в корзине."), [{ text: mt("Отмена") }, { text: mt("Добавить"), onPress: () => void c.attempt(async () => { await basket.addItem(item.variant_id!, item.packages!); setAdded(values => [...values, i]) }) }])} /> : null}</> : <Copy>{item.reason ? mt(item.reason) : null}</Copy>}
        </View>)}<Copy>{supply.note ? mt(supply.note) : null}</Copy></> : null}
    </>
}

const styles = StyleSheet.create({
    panel: { borderWidth: 1, borderRadius: 18, padding: 6, gap: 8 },
    copy: { fontSize: 15, lineHeight: 23, flexShrink: 1 },
    row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
    button: { paddingHorizontal: 14, paddingVertical: 12, borderRadius: 13, alignSelf: "flex-start", minHeight: 48, maxWidth: "100%", justifyContent: "center", alignItems: "center" },
    primaryButton: { alignSelf: "stretch", marginTop: 6 },
    buttonText: { fontSize: 15, lineHeight: 21, fontWeight: "600", textAlign: "center", flexShrink: 1 },
    card: { padding: 14, borderRadius: 18, borderWidth: 1, borderColor: "#86AC953D", gap: 12, marginVertical: 5 },
    field: { gap: 6, marginVertical: 2 },
    fieldLabel: { fontSize: 14, lineHeight: 21, fontWeight: "500" },
    input: { borderWidth: 1, borderRadius: 13, paddingHorizontal: 14, paddingVertical: 12, minHeight: 50, fontSize: 16, lineHeight: 23 },
    multilineInput: { minHeight: 98 },
    toggle: { flexDirection: "row", alignItems: "center", gap: 12, padding: 13, borderRadius: 14 },
    modalHeader: { paddingTop: 16, paddingHorizontal: 18, paddingBottom: 20, gap: 15, borderBottomLeftRadius: 24, borderBottomRightRadius: 24 },
    modalBrandRow: { flexDirection: "row", alignItems: "center", gap: 9 },
    modalAvatar: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center" },
    modalBrand: { flex: 1, fontSize: 15, lineHeight: 22, fontWeight: "600" },
    modalTitle: { fontSize: 26, lineHeight: 33, fontWeight: "600" },
    modalClose: { width: 40, height: 40, borderRadius: 20, alignItems: "center", justifyContent: "center" },
    modalCloseText: { fontSize: 28, lineHeight: 32, fontWeight: "400" },
    modal: { padding: 14, paddingBottom: 50, width: "100%", maxWidth: 700, alignSelf: "center" },
    modalCard: { padding: 18, borderRadius: 22, gap: 15 },
})
