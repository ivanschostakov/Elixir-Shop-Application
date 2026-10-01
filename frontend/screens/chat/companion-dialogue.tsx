import { mentorText as mt, mentorLocale, mentorDateLabel } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { companionDialogue, eraseCompanion, requestKey } from "@/services/api/companion"
import type { CompanionAction, DialogueCard, EntryData, PlanData, Stage, Unit } from "@/services/api/companion"
import type { AIMessageRead } from "@/services/api/ai-chat.types"
import type { useCompanion } from "@/screens/chat/companion"
import { formatCompanionDate } from "@/screens/chat/companion-timezones"
import { MentorNavigation } from "@/screens/chat/mentor"
import { measurementLabels, workoutTotals } from "@/screens/chat/mentor-data"

type Controller = ReturnType<typeof useCompanion>
const units: Record<Unit, string> = { get mg() { return mt("мг") }, get mcg() { return mt("мкг") }, get g() { return mt("г") }, get ml() { return mt("мл") }, get capsule() { return mt("капсул") }, get tablet() { return mt("таблеток") }, get IU() { return mt("МЕ") } }
const periods: Record<string, string> = { get morning() { return mt("утром") }, get afternoon() { return mt("днём") }, get evening() { return mt("вечером") }, get night() { return mt("ночью") }, get unknown() { return mt("точное время не указано") } }
const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
const parameterLabels: Record<string, string> = { get goal() { return mt("Цель питания") }, get age() { return mt("Возраст") }, get sex() { return mt("Пол") }, get height_cm() { return mt("Рост, см") }, get target_weight_kg() { return mt("Целевой вес, кг") }, get activity() { return mt("Активность") }, get preferences() { return mt("Предпочтения") }, get restrictions() { return mt("Ограничения") }, get nutrition() { return mt("КБЖУ") }, get nutrition_source() { return mt("Источник КБЖУ") }, get nutrition_rule_version() { return mt("Правило расчёта") }, get checkin_time() { return mt("Ежедневный вопрос") }, get checkin_topics() { return mt("Темы вопросов") }, get daily_time() { return mt("Итоги дня") }, get weight_time() { return mt("Напоминание о весе") }, get weekly_time() { return mt("Еженедельный отчёт") }, get weekly_day() { return mt("День недели (0 — пн)") }, get course_reminders() { return mt("События курса") }, get supply_reminders() { return mt("Напоминания о запасе") }, get supply_days() { return mt("Запас, дней") }, get nutrition_auto_eligible() { return mt("Подтверждение условий расчёта питания") } }
const valueLabels: Record<string, string> = { get weight_loss() { return mt("снижение веса") }, get weight_gain() { return mt("набор веса") }, get custom() { return mt("своя цель") }, get maintain() { return mt("поддержание") }, get course() { return mt("курс") }, get male() { return mt("мужской") }, get female() { return mt("женский") }, get low() { return mt("низкая") }, get light() { return mt("лёгкая") }, get moderate() { return mt("умеренная") }, get high() { return mt("высокая") }, get nutrition() { return mt("питание") }, get weight() { return mt("вес") }, get wellbeing() { return mt("самочувствие") }, get manual() { return mt("пользователь") }, get calculated() { return mt("расчёт") } }
function displayValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return mt("не задано")
    if (typeof value === "boolean") return value ? mt("да") : mt("нет")
    if (Array.isArray(value)) return value.map(displayValue).join(", ")
    if (typeof value === "object") return JSON.stringify(value)
    return valueLabels[String(value)] ?? String(value)
}

function Copy({ children }: { children: React.ReactNode }) {
    useLanguage()
    const { palette } = useTheme()
    return <Text style={[styles.text, { color: palette.text }]}>{children}</Text>
}

function Chip({ label, onPress, disabled, tone = "glass" }: { label: string; onPress: () => void; disabled?: boolean; tone?: "glass" | "primary" | "quiet" | "danger" }) {
    useLanguage()
    const { palette } = useTheme()
    const backgroundColor = tone === "primary" ? palette.primary : tone === "danger" ? palette.dangerMuted : tone === "quiet" ? "transparent" : "rgba(255,255,255,0.92)"
    const color = tone === "primary" ? palette.onPrimary : tone === "danger" ? palette.danger : palette.primary
    return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={[styles.chip, tone === "quiet" ? styles.quietChip : styles.glassChip, { backgroundColor, opacity: disabled ? 0.45 : 1 }]}>
        <Text style={[styles.chipText, { color }]}>{label}</Text>
    </Pressable>
}

export function DialoguePanel({ controller: c, onChanged, onPrompt, sending }: { controller: Controller; onChanged: () => Promise<void>; onPrompt: (text: string) => Promise<unknown>; sending?: boolean }) {
    useLanguage()
    const { palette } = useTheme()
    const [working, setWorking] = useState(false)
    const [expanded, setExpanded] = useState<"record" | "reports" | "more" | null>(null)
    const callbacks = useRef({ c, onChanged })
    callbacks.current = { c, onChanged }
    const userProfileId = c.enabled ? c.state?.profile?.id : undefined
    useEffect(() => {
        if (!userProfileId) return
        let disposed = false
        void companionDialogue("intro", 7, `dialogue-intro-${userProfileId}`).then(async () => {
            if (!disposed) await callbacks.current.onChanged()
        }).catch(error => { if (!disposed) callbacks.current.c.setError(error instanceof Error ? error.message : mt("Не удалось загрузить знакомство")) })
        return () => { disposed = true }
    }, [userProfileId])
    const busyRef = useRef(false)
    const run = (operation: () => Promise<unknown>) => {
        if (busyRef.current || sending || c.busy) return
        busyRef.current = true; setWorking(true)
        void c.attempt(operation).finally(() => { busyRef.current = false; setWorking(false) })
    }
    const prompt = (text: string) => run(() => onPrompt(text))
    const report = (kind: "course" | "nutrition" | "progress", days: 7 | 30 = 7) => run(async () => {
        if (c.state?.consent_required) {
            await onPrompt(kind === "course" ? mt("Хочу вести свой текущий курс. Что тебе нужно знать?") : mt("Хочу начать вести питание и вес в чате. Что нужно сообщить?"))
            return
        }
        await companionDialogue(kind, days)
        await onChanged()
    })
    const busy = working || c.busy || sending || !c.enabled
    const toggle = (section: "record" | "reports" | "more") => setExpanded(current => current === section ? null : section)
    if (c.state && "mentor" in c.state && c.enabled) return <View testID="companion-dialogue-panel"><MentorNavigation controller={c} /></View>
    return <View testID="companion-dialogue-panel" style={styles.panel}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.quickActionsRow}>
            <Chip label={mt("Мой курс")} disabled={busy} onPress={() => prompt(mt("Покажи мой текущий курс и ближайшие события. Если курса ещё нет, помоги записать мою схему."))} />
            <Chip label={mt("Отметить")} disabled={busy} onPress={() => prompt(mt("Хочу отметить фактический приём. Покажи подходящие события и уточни, какое отметить."))} />
            <Chip label={expanded === "record" ? mt("Записать ↑") : mt("Записать")} disabled={busy} onPress={() => toggle("record")} />
            <Chip label={expanded === "reports" ? mt("Отчёты ↑") : mt("Отчёты")} disabled={busy} onPress={() => toggle("reports")} />
            <Chip label={expanded === "more" ? mt("Ещё ↑") : mt("Ещё")} disabled={busy} onPress={() => toggle("more")} />
        </ScrollView>
        {expanded === "record" ? <View style={styles.submenuRow}>
            <Chip label={mt("Еду")} disabled={busy} onPress={() => { setExpanded(null); prompt(mt("Хочу записать еду. Спроси, что я ел и какая была порция.")) }} />
            <Chip label={mt("Вес")} disabled={busy} onPress={() => { setExpanded(null); prompt(mt("Хочу записать измерение веса. Спроси результат и дату.")) }} />
            <Chip label={mt("Самочувствие")} disabled={busy} onPress={() => { setExpanded(null); prompt(mt("Хочу записать самочувствие. Спроси, как я себя чувствую.")) }} />
        </View> : null}
        {expanded === "reports" ? <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.submenuRow}>
            <Chip label={mt("По курсу")} disabled={busy} onPress={() => report("course")} />
            <Chip label={mt("Питание")} disabled={busy} onPress={() => report("nutrition")} />
            <Chip label={mt("Прогресс · 7 дней")} disabled={busy} onPress={() => report("progress")} />
            <Chip label={mt("Прогресс · 30 дней")} disabled={busy} onPress={() => report("progress", 30)} />
        </ScrollView> : null}
        {expanded === "more" ? <View style={styles.submenuRow}>
            <Chip label={mt("Напоминания")} disabled={busy} onPress={() => { setExpanded(null); prompt(mt("Покажи мои настройки напоминаний. Хочу настроить их в диалоге.")) }} />
            <Chip label={mt("Удалить учёт")} tone="danger" disabled={busy} onPress={() => Alert.alert(mt("Удалить данные сопровождения?"), mt("Будут удалены курс, дневник, черновики и сообщения сопровождения. Это нельзя отменить."), [
                { text: mt("Отмена"), style: "cancel" },
                { text: mt("Удалить"), style: "destructive", onPress: () => run(async () => { await eraseCompanion(); await c.refresh(); await onChanged() }) },
            ])} />
        </View> : null}
        {working ? <ActivityIndicator size="small" color={palette.primary} /> : null}
        {c.error ? <><Copy>{c.error}</Copy><Chip label={mt("Обновить")} onPress={() => run(async () => { await c.refresh(); await onChanged() })} /></> : null}
        {!c.enabled ? <><Copy>{mt("Сопровождение отключено.")}</Copy><Chip label={mt("Начать заново")} onPress={() => Alert.alert(mt("Возобновить учёт?"), mt("Курс, дневник и нужный контекст будут храниться в приложении и передаваться OpenAI для ответов. Подтвердите возраст 18+ и согласие на обработку данных."), [
            { text: mt("Отмена"), style: "cancel" },
            { text: mt("Мне есть 18 — начать"), onPress: () => run(async () => { await c.perform({ kind: "enable", adult_confirmed: true, consent_version: c.state?.consent_version }); await onChanged() }) },
        ])} /></> : null}
    </View>
}

function displayNumber(value: string | number) {
    const decimal = new Intl.NumberFormat(mentorLocale()).formatToParts(1.1).find(part => part.type === "decimal")?.value ?? "."
    return String(value).replace(".", decimal)
}

function shortTime(value: string) {
    const match = /^(\d{2}):(\d{2})/.exec(value)
    return match ? `${match[1]}:${match[2]}` : value
}

function localDateParts(value: string) {
    const [year, month, day] = value.split("-").map(Number)
    return { year, date: new Date(year, month - 1, day) }
}

function dateRange(start: string, end: string) {
    const first = localDateParts(start), last = localDateParts(end)
    const format = (value: Date, year: boolean) => mentorDateLabel(value, { day: "numeric", month: "short", ...(year ? { year: "numeric" as const } : {}) }).replace(" г.", "")
    return first.year === last.year
        ? `${format(first.date, false)} — ${format(last.date, true)}`
        : `${format(first.date, true)} — ${format(last.date, true)}`
}

function scheduleLabel(stage: Stage) {
    const days = stage.weekdays.length ? stage.weekdays.map(day => mt(weekdays[day])).join(", ") : stage.interval_days === 1 ? mt("Каждый день") : mt("Каждые {0} дн.", [stage.interval_days])
    return `${days} · ${stage.times.map(shortTime).join(", ")}`
}

function CoursePlanDetails({ plan, recommended, reminders }: { plan: PlanData; recommended: boolean; reminders?: boolean | null }) {
    useLanguage()
    const { palette } = useTheme()
    return <View style={styles.course}>
        <View style={styles.courseHeader}>
            <View style={[styles.courseIcon, { backgroundColor: palette.primaryMuted }]}><Text style={[styles.courseIconText, { color: palette.primary }]}>◉</Text></View>
            <View style={styles.courseHeaderText}>
                <Text style={[styles.courseEyebrow, { color: palette.primary }]}>{recommended ? mt("РЕКОМЕНДАЦИЯ ИИ") : mt("МОЙ КУРС")}</Text>
                <Text style={[styles.courseTitle, { color: palette.text }]}>{plan.name}</Text>
            </View>
        </View>
        {recommended ? <View style={[styles.notice, { backgroundColor: palette.warningMuted }]}><Text style={[styles.noticeText, { color: palette.warning }]}>{mt("Рекомендация ИИ, а не медицинское назначение. Проверьте схему перед сохранением.")}</Text></View> : null}
        {plan.items.map((item, itemIndex) => <View key={`${item.name}-${itemIndex}`} style={[styles.courseItem, { borderColor: palette.border }]}>
            <Text style={[styles.itemTitle, { color: palette.text }]}>{item.name}</Text>
            {item.package_source_name ? <Text style={[styles.itemCaption, { color: palette.mutedText }]}>{item.package_source_name}</Text> : null}
            <View style={styles.timeline}>
                {item.stages.map((stage, index) => <View key={`${stage.start_date}-${index}`} style={styles.stageRow}>
                    <View style={styles.stageRail}>
                        <View style={[styles.stageDot, { backgroundColor: palette.primary }]} />
                        {index < item.stages.length - 1 ? <View style={[styles.stageLine, { backgroundColor: palette.border }]} /> : null}
                    </View>
                    <View style={styles.stageContent}>
                        <View style={styles.stageHeading}>
                            <Text style={[styles.stageIndex, { color: palette.mutedText }]}>{mt("Этап ")}{index + 1}</Text>
                            <Text style={[styles.stageDate, { color: palette.text }]}>{dateRange(stage.start_date, stage.end_date)}</Text>
                        </View>
                        <View style={styles.stageTags}>
                            <View style={[styles.doseTag, { backgroundColor: palette.primaryMuted }]}><Text style={[styles.doseText, { color: palette.primary }]}>{displayNumber(stage.amount)} {units[stage.unit]}</Text></View>
                            <Text style={[styles.scheduleText, { color: palette.stateText }]}>{scheduleLabel(stage)}</Text>
                        </View>
                    </View>
                </View>)}
            </View>
        </View>)}
        <View style={[styles.courseFooter, { borderTopColor: palette.border }]}>
            <Text style={[styles.footerText, { color: palette.stateText }]}>{mt("◷ Ближайшие события — по времени телефона")}</Text>
            {reminders !== undefined && reminders !== null ? <Text style={[styles.footerText, { color: reminders ? palette.success : palette.mutedText }]}>{reminders ? mt("● Напоминания включены") : mt("○ Напоминания выключены")}</Text> : null}
        </View>
    </View>
}

function NutritionMetric({ label, value, color }: { label: string; value: string; color: string }) {
    useLanguage()
    const { palette } = useTheme()
    return <View style={[styles.metric, { borderColor: palette.border }]}><Text style={[styles.metricValue, { color }]}>{value}</Text><Text style={[styles.metricLabel, { color: palette.mutedText }]}>{label}</Text></View>
}

function EntryDetails({ entry, clock }: { entry: EntryData; clock: string }) {
    useLanguage()
    const { palette } = useTheme()
    const title = entry.kind === "weight" ? mt("{0} кг", [entry.weight_kg]) : entry.kind === "workout" ? entry.workout?.name : entry.kind === "measurement" ? mt("Замеры") : entry.kind === "progress_photo" ? mt("Фото прогресса") : entry.name || mt("Самочувствие")
    return <View style={styles.entryDetails}>
        <Text style={[styles.entryTitle, { color: palette.text }]}>{title}</Text>
        <Text style={[styles.itemCaption, { color: palette.mutedText }]}>{formatCompanionDate(entry.occurred_at, clock)}</Text>
        {entry.workout ? <><Copy>{entry.workout.status === "completed" ? mt("Завершена") : mt("В процессе")} · {workoutTotals(entry.workout).sets} {mt(" выполненных подходов · ")}{workoutTotals(entry.workout).volume} {mt(" кг объёма")}</Copy>{entry.workout.exercises.map(exercise => <View key={exercise.key}><Copy>{exercise.name}</Copy>{exercise.sets.map((set, index) => <Copy key={index}>{index + 1}: {set.weight_kg ?? "—"} {mt(" кг × ")}{set.reps ?? "—"} · {set.completed ? mt("выполнен") : mt("не выполнен")}</Copy>)}</View>)}</> : null}
        {entry.measurement ? <>{Object.entries(entry.measurement).filter(([, value]) => value != null).map(([key, value]) => <Copy key={key}>{measurementLabels[key as keyof typeof measurementLabels]}: {value}</Copy>)}</> : null}
        {entry.kind === "progress_photo" ? <Copy>{mt("Приватных фото: ")}{entry.photo_attachment_ids?.length ?? 0}</Copy> : null}
        {entry.nutrition ? <View style={styles.metricsRow}>
            <NutritionMetric label={mt("ккал")} value={displayNumber(entry.nutrition.kcal)} color={palette.text} />
            <NutritionMetric label={mt("белки")} value={mt("{0} г", [displayNumber(entry.nutrition.protein)])} color={palette.primary} />
            <NutritionMetric label={mt("жиры")} value={mt("{0} г", [displayNumber(entry.nutrition.fat)])} color={palette.warning} />
            <NutritionMetric label={mt("углеводы")} value={mt("{0} г", [displayNumber(entry.nutrition.carbs)])} color={palette.success} />
        </View> : null}
        {entry.estimated ? <View style={[styles.notice, { backgroundColor: palette.warningMuted }]}><Text style={[styles.noticeText, { color: palette.warning }]}>{mt("Приблизительная оценка ")}{entry.assumptions ? ` · ${entry.assumptions}` : ""}</Text></View> : null}
        {entry.note ? <Text style={[styles.entryNote, { color: palette.stateText }]}>{entry.note}</Text> : null}
    </View>
}

function Details({ card, clock }: { card: DialogueCard; clock: string }) {
    useLanguage()
    const op = card.operation
    if (card.children?.length) return <>{card.children.map(child => <View key={child.id}><Copy>{child.summary}</Copy><Details card={child} clock={clock} /></View>)}</>
    if (op.operations) return <>{op.operations.map((operation, index) => <Details key={index} card={{ ...card, changes: undefined, operation }} clock={clock} />)}</>
    if (card.changes?.length) return <>{card.changes.map(change => <Copy key={change.parameter}>{parameterLabels[change.parameter] ?? change.parameter}: {displayValue(change.before)} → {displayValue(change.after)}</Copy>)}</>
    if (op.plan) return <CoursePlanDetails plan={op.plan} recommended={op.plan.source === "ai_recommended_plan"} reminders={op.remind_course} />
    if (op.entry) {
        return <EntryDetails entry={op.entry} clock={clock} />
    }
    if (op.intake) {
        const i = op.intake
        return <Copy>{i.name} · {i.occurred_at ? formatCompanionDate(i.occurred_at, clock) : `${i.local_date}, ${periods[i.period]}`} {i.amount != null && i.unit ? `· ${i.amount} ${units[i.unit]}` : ""}{i.note ? `\n${i.note}` : ""}</Copy>
    }
    if (op.nutrition) return <Copy>{op.nutrition.kcal} {mt(" ккал · Б ")}{op.nutrition.protein} {mt(" · Ж ")}{op.nutrition.fat} {mt(" · У ")}{op.nutrition.carbs} {mt(" г")}</Copy>
    if (op.settings || op.profile) return <>{Object.entries(op.settings ?? op.profile ?? {}).filter(([key]) => key !== "timezone").map(([key, value]) => <Copy key={key}>{parameterLabels[key] ?? key}: {displayValue(value)}</Copy>)}</>
    return null
}

export function DialogueCards({ controller: c, message, onChanged }: { controller: Controller; message: AIMessageRead; onChanged: () => Promise<void> }) {
    useLanguage()
    const { palette } = useTheme()
    const keys = useRef(new Map<string, string>())
    const perform = (card: DialogueCard, kind: CompanionAction["kind"]) => void c.attempt(async () => {
        const identity = `${message.id}:${card.id}:${kind}`
        const key = keys.current.get(identity) ?? requestKey()
        keys.current.set(identity, key)
        await c.perform({ kind, request_key: key, message_id: message.id, action_id: card.id, action_token: card.action_token })
        await onChanged()
        keys.current.delete(identity)
    })
    const labels = { pending: mt("Нужно подтверждение"), saved: mt("✓ Сохранено"), cancelled: mt("Не сохранено"), superseded: mt("Заменено"), undone: mt("Отменено"), needs_correction: mt("Нужно уточнение") }
    const statusColors = { pending: palette.warning, saved: palette.success, cancelled: palette.mutedText, superseded: palette.mutedText, undone: palette.mutedText, needs_correction: palette.danger }
    const statusBackgrounds = { pending: palette.warningMuted, saved: palette.successMuted, cancelled: palette.surfaceMuted, superseded: palette.surfaceMuted, undone: palette.surfaceMuted, needs_correction: palette.dangerMuted }
    return <>{message.dialogue_cards?.map(card => <View key={card.id} style={[styles.card, { backgroundColor: palette.surfaceOverlay, borderColor: palette.border }]}>
        <View style={styles.cardTopRow}><View style={[styles.statusPill, { backgroundColor: statusBackgrounds[card.state] }]}><Text style={[styles.statusText, { color: statusColors[card.state] }]}>{labels[card.state]}</Text></View></View>
        {card.kind === "plan" ? null : <Text style={[styles.cardSummary, { color: palette.text }]}>{card.summary}</Text>}
        <Details card={card} clock={c.clock} />
        {card.error ? <View style={[styles.notice, { backgroundColor: palette.dangerMuted }]}><Text style={[styles.noticeText, { color: palette.danger }]}>{card.error}</Text></View> : null}
        {c.state?.dialogue_protocol === 2 ? <View style={styles.cardActions}>
            {card.state === "pending" ? <Chip tone="primary" label={card.kind === "plan" ? mt("Сохранить курс") : card.kind === "entry" ? mt("Сохранить запись") : mt("Подтвердить")} disabled={c.busy} onPress={() => perform(card, "dialogue_confirm")} /> : null}
            {["pending", "saved", "needs_correction"].includes(card.state) && card.kind !== "delete_entry" ? <Chip label={mt("Изменить")} disabled={c.busy} onPress={() => perform(card, "dialogue_edit")} /> : null}
            {card.state === "pending" ? <Chip tone="quiet" label={mt("Не сохранять")} disabled={c.busy} onPress={() => perform(card, "dialogue_cancel")} /> : null}
            {card.state === "saved" && card.can_undo ? <Chip tone="quiet" label={mt("Отменить")} disabled={c.busy} onPress={() => perform(card, "dialogue_undo")} /> : null}
        </View> : null}
    </View>)}</>
}

const styles = StyleSheet.create({
    panel: { backgroundColor: "transparent", gap: 6, marginBottom: 6 },
    quickActionsRow: { flexDirection: "row", gap: 8, alignItems: "center", paddingHorizontal: 2, paddingVertical: 2 },
    submenuRow: { flexDirection: "row", gap: 8, flexWrap: "wrap", alignItems: "center", paddingHorizontal: 2 },
    row: { flexDirection: "row", gap: 6, flexWrap: "wrap", alignItems: "center" },
    chip: { minHeight: 38, borderRadius: 19, paddingHorizontal: 14, paddingVertical: 9, alignItems: "center", justifyContent: "center" },
    glassChip: { borderWidth: 1, borderColor: "rgba(255,255,255,0.72)", shadowColor: "#07121C", shadowOpacity: 0.12, shadowRadius: 8, shadowOffset: { width: 0, height: 3 }, elevation: 3 },
    quietChip: { paddingHorizontal: 8 },
    chipText: { fontWeight: "700", fontSize: 13, lineHeight: 17 },
    text: { fontSize: 14, lineHeight: 21 },
    card: { borderWidth: 1, borderRadius: 22, padding: 14, gap: 12, marginTop: 8, overflow: "hidden" },
    cardTopRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
    statusPill: { borderRadius: 12, paddingHorizontal: 9, paddingVertical: 5 },
    statusText: { fontSize: 11, lineHeight: 14, fontWeight: "800", textTransform: "uppercase", letterSpacing: 0.3 },
    cardSummary: { fontSize: 16, lineHeight: 21, fontWeight: "700" },
    cardActions: { flexDirection: "row", gap: 8, flexWrap: "wrap", alignItems: "center", paddingTop: 2 },
    course: { gap: 12 },
    courseHeader: { flexDirection: "row", alignItems: "center", gap: 11 },
    courseIcon: { width: 42, height: 42, borderRadius: 14, alignItems: "center", justifyContent: "center" },
    courseIconText: { fontSize: 20, lineHeight: 23, fontWeight: "900" },
    courseHeaderText: { flex: 1, gap: 2 },
    courseEyebrow: { fontSize: 10, lineHeight: 13, fontWeight: "900", letterSpacing: 0.8 },
    courseTitle: { fontSize: 19, lineHeight: 24, fontWeight: "800" },
    notice: { borderRadius: 13, paddingHorizontal: 11, paddingVertical: 9 },
    noticeText: { fontSize: 12, lineHeight: 17, fontWeight: "600" },
    courseItem: { borderTopWidth: 1, paddingTop: 12, gap: 3 },
    itemTitle: { fontSize: 15, lineHeight: 20, fontWeight: "800" },
    itemCaption: { fontSize: 12, lineHeight: 17 },
    timeline: { marginTop: 9 },
    stageRow: { flexDirection: "row", minHeight: 75 },
    stageRail: { width: 22, alignItems: "center" },
    stageDot: { width: 10, height: 10, borderRadius: 5, marginTop: 5 },
    stageLine: { width: 2, flex: 1, marginVertical: 4 },
    stageContent: { flex: 1, paddingBottom: 13, gap: 7 },
    stageHeading: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 8 },
    stageIndex: { fontSize: 11, lineHeight: 14, fontWeight: "800", textTransform: "uppercase" },
    stageDate: { flexShrink: 1, fontSize: 13, lineHeight: 17, fontWeight: "700", textAlign: "right" },
    stageTags: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 7 },
    doseTag: { borderRadius: 10, paddingHorizontal: 9, paddingVertical: 5 },
    doseText: { fontSize: 14, lineHeight: 17, fontWeight: "900" },
    scheduleText: { flexShrink: 1, fontSize: 13, lineHeight: 17, fontWeight: "600" },
    courseFooter: { borderTopWidth: 1, paddingTop: 10, gap: 5 },
    footerText: { fontSize: 12, lineHeight: 17, fontWeight: "600" },
    entryDetails: { gap: 8 },
    entryTitle: { fontSize: 18, lineHeight: 23, fontWeight: "800" },
    metricsRow: { flexDirection: "row", gap: 6 },
    metric: { flex: 1, minWidth: 58, borderWidth: 1, borderRadius: 12, paddingHorizontal: 6, paddingVertical: 8, alignItems: "center" },
    metricValue: { fontSize: 13, lineHeight: 17, fontWeight: "900" },
    metricLabel: { fontSize: 9, lineHeight: 12, fontWeight: "700" },
    entryNote: { fontSize: 13, lineHeight: 18 },
})
