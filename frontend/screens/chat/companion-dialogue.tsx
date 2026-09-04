import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Alert, Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { useTheme } from "@/providers/theme-provider"
import { companionDialogue, eraseCompanion, requestKey } from "@/services/api/companion"
import type { CompanionAction, DialogueCard, Unit } from "@/services/api/companion"
import type { AIMessageRead } from "@/services/api/ai-chat.types"
import type { useCompanion } from "@/screens/chat/companion"
import { formatCompanionDate } from "@/screens/chat/companion-timezones"

type Controller = ReturnType<typeof useCompanion>
const units: Record<Unit, string> = { mg: "мг", mcg: "мкг", g: "г", ml: "мл", capsule: "капсул", tablet: "таблеток", IU: "МЕ" }
const periods: Record<string, string> = { morning: "утром", afternoon: "днём", evening: "вечером", night: "ночью", unknown: "точное время не указано" }
const parameterLabels: Record<string, string> = { goal: "Цель питания", age: "Возраст", sex: "Пол", height_cm: "Рост, см", target_weight_kg: "Целевой вес, кг", activity: "Активность", preferences: "Предпочтения", restrictions: "Ограничения", nutrition: "КБЖУ", nutrition_source: "Источник КБЖУ", nutrition_rule_version: "Правило расчёта", checkin_time: "Ежедневный вопрос", checkin_topics: "Темы вопросов", daily_time: "Итоги дня", weight_time: "Напоминание о весе", weekly_time: "Еженедельный отчёт", weekly_day: "День недели (0 — пн)", course_reminders: "События курса", supply_reminders: "Напоминания о запасе", supply_days: "Запас, дней", nutrition_auto_eligible: "Подтверждение условий расчёта питания" }
const valueLabels: Record<string, string> = { weight_loss: "снижение веса", maintain: "поддержание", course: "курс", male: "мужской", female: "женский", low: "низкая", light: "лёгкая", moderate: "умеренная", high: "высокая", nutrition: "питание", weight: "вес", wellbeing: "самочувствие", manual: "пользователь", calculated: "расчёт" }
function displayValue(value: unknown): string {
    if (value === null || value === undefined || value === "") return "не задано"
    if (typeof value === "boolean") return value ? "да" : "нет"
    if (Array.isArray(value)) return value.map(displayValue).join(", ")
    if (typeof value === "object") return JSON.stringify(value)
    return valueLabels[String(value)] ?? String(value)
}

function Copy({ children }: { children: React.ReactNode }) {
    const { palette } = useTheme()
    return <Text style={[styles.text, { color: palette.text }]}>{children}</Text>
}

function Chip({ label, onPress, disabled }: { label: string; onPress: () => void; disabled?: boolean }) {
    const { palette } = useTheme()
    return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled} onPress={onPress} style={[styles.chip, { backgroundColor: palette.surfaceMuted, opacity: disabled ? 0.45 : 1 }]}>
        <Text style={{ color: palette.primary, fontWeight: "600", fontSize: 13 }}>{label}</Text>
    </Pressable>
}

export function DialoguePanel({ controller: c, onChanged, onPrompt, sending }: { controller: Controller; onChanged: () => Promise<void>; onPrompt: (text: string) => Promise<unknown>; sending?: boolean }) {
    const { palette } = useTheme()
    const [working, setWorking] = useState(false)
    const [expanded, setExpanded] = useState(false)
    const callbacks = useRef({ c, onChanged })
    callbacks.current = { c, onChanged }
    const userProfileId = c.enabled ? c.state?.profile?.id : undefined
    useEffect(() => {
        if (!userProfileId) return
        let disposed = false
        void companionDialogue("intro", 7, `dialogue-intro-${userProfileId}`).then(async () => {
            if (!disposed) await callbacks.current.onChanged()
        }).catch(error => { if (!disposed) callbacks.current.c.setError(error instanceof Error ? error.message : "Не удалось загрузить знакомство") })
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
            await onPrompt(kind === "course" ? "Хочу вести свой текущий курс. Что тебе нужно знать?" : "Хочу начать вести питание и вес в чате. Что нужно сообщить?")
            return
        }
        await companionDialogue(kind, days)
        await onChanged()
    })
    const busy = working || c.busy || sending || !c.enabled
    return <View testID="companion-dialogue-panel" style={[styles.panel, { backgroundColor: palette.surface, borderColor: palette.border }]}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} keyboardShouldPersistTaps="handled" contentContainerStyle={styles.row}>
            <Chip label="Мой курс" disabled={busy} onPress={() => prompt("Покажи мой текущий курс и ближайшие события. Если курса ещё нет, помоги записать мою схему.")} />
            <Chip label="Отметить приём" disabled={busy} onPress={() => prompt("Хочу отметить фактический приём. Покажи подходящие события и уточни, какое отметить.")} />
            <Chip label="Записать" disabled={busy} onPress={() => setExpanded(!expanded)} />
            <Chip label="Отчёт по курсу" disabled={busy} onPress={() => report("course")} />
            <Chip label="Питание" disabled={busy} onPress={() => report("nutrition")} />
            <Chip label="Прогресс · 7 дней" disabled={busy} onPress={() => report("progress")} />
            <Chip label="30 дней" disabled={busy} onPress={() => report("progress", 30)} />
            <Chip label="Напоминания" disabled={busy} onPress={() => prompt("Покажи мои настройки напоминаний. Хочу настроить их в диалоге.")} />
            <Chip label="Удалить учёт" disabled={busy} onPress={() => Alert.alert("Удалить данные сопровождения?", "Будут удалены курс, дневник, черновики и сообщения сопровождения. Это нельзя отменить.", [
                { text: "Отмена", style: "cancel" },
                { text: "Удалить", style: "destructive", onPress: () => run(async () => { await eraseCompanion(); await c.refresh(); await onChanged() }) },
            ])} />
        </ScrollView>
        {expanded ? <View style={styles.row}>
            <Chip label="Еда" disabled={busy} onPress={() => { setExpanded(false); prompt("Хочу записать еду. Спроси, что я ел и какая была порция.") }} />
            <Chip label="Вес" disabled={busy} onPress={() => { setExpanded(false); prompt("Хочу записать измерение веса. Спроси результат и дату.") }} />
            <Chip label="Самочувствие" disabled={busy} onPress={() => { setExpanded(false); prompt("Хочу записать самочувствие. Спроси, как я себя чувствую.") }} />
        </View> : null}
        {working ? <ActivityIndicator size="small" color={palette.primary} /> : null}
        {c.error ? <><Copy>{c.error}</Copy><Chip label="Обновить" onPress={() => run(async () => { await c.refresh(); await onChanged() })} /></> : null}
        {!c.enabled ? <><Copy>Сопровождение отключено.</Copy><Chip label="Начать заново" onPress={() => Alert.alert("Возобновить учёт?", "Курс, дневник и нужный контекст будут храниться в приложении и передаваться OpenAI для ответов. Подтвердите возраст 18+ и согласие на обработку данных.", [
            { text: "Отмена", style: "cancel" },
            { text: "Мне есть 18 — начать", onPress: () => run(async () => { await c.perform({ kind: "enable", adult_confirmed: true, consent_version: c.state?.consent_version }); await onChanged() }) },
        ])} /></> : null}
    </View>
}

function Details({ card, clock }: { card: DialogueCard; clock: string }) {
    const op = card.operation
    if (card.children?.length) return <>{card.children.map(child => <View key={child.id}><Copy>{child.summary}</Copy><Details card={child} clock={clock} /></View>)}</>
    if (op.operations) return <>{op.operations.map((operation, index) => <Details key={index} card={{ ...card, changes: undefined, operation }} clock={clock} />)}</>
    if (card.changes?.length) return <>{card.changes.map(change => <Copy key={change.parameter}>{parameterLabels[change.parameter] ?? change.parameter}: {displayValue(change.before)} → {displayValue(change.after)}</Copy>)}</>
    if (op.plan) return <>
        <Copy>{op.plan.name}</Copy>
        {op.plan.items.map((item, index) => <View key={index}>
            <Copy>{item.name}{item.package_source_name ? ` · ${item.package_source_name}` : ""}</Copy>
            {item.stages.map((stage, i) => <Copy key={i}>{stage.start_date} — {stage.end_date} · {stage.amount} {units[stage.unit]} · {stage.times.join(", ")}{stage.weekdays.length ? ` · дни недели: ${stage.weekdays.map(d => ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][d]).join(", ")}` : ` · каждые ${stage.interval_days} дн.`}</Copy>)}
        </View>)}
        <Copy>Исходное расписание: {op.plan.timezone}. Время ближайших событий показывается по телефону.</Copy>
    </>
    if (op.entry) {
        const e = op.entry
        return <><Copy>{formatCompanionDate(e.occurred_at, clock)} · {e.kind === "weight" ? `${e.weight_kg} кг` : e.name || "Самочувствие"}</Copy>
            {e.nutrition ? <Copy>{e.nutrition.kcal} ккал · Б {e.nutrition.protein} · Ж {e.nutrition.fat} · У {e.nutrition.carbs} г</Copy> : null}
            {e.estimated ? <Copy>Приблизительно. {e.assumptions}</Copy> : null}
            {e.note ? <Copy>{e.note}</Copy> : null}</>
    }
    if (op.intake) {
        const i = op.intake
        return <Copy>{i.name} · {i.occurred_at ? formatCompanionDate(i.occurred_at, clock) : `${i.local_date}, ${periods[i.period]}`} {i.amount != null && i.unit ? `· ${i.amount} ${units[i.unit]}` : ""}{i.note ? `\n${i.note}` : ""}</Copy>
    }
    if (op.nutrition) return <Copy>{op.nutrition.kcal} ккал · Б {op.nutrition.protein} · Ж {op.nutrition.fat} · У {op.nutrition.carbs} г</Copy>
    if (op.settings || op.profile) return <>{Object.entries(op.settings ?? op.profile ?? {}).filter(([key]) => key !== "timezone").map(([key, value]) => <Copy key={key}>{parameterLabels[key] ?? key}: {displayValue(value)}</Copy>)}</>
    return null
}

export function DialogueCards({ controller: c, message, onChanged }: { controller: Controller; message: AIMessageRead; onChanged: () => Promise<void> }) {
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
    const labels = { pending: "Проверьте и подтвердите", saved: "✓ Сохранено", cancelled: "Отменено", superseded: "Заменено новой карточкой", undone: "Изменение отменено", needs_correction: "Не сохранено — нужно уточнение" }
    return <>{message.dialogue_cards?.map(card => <View key={card.id} style={[styles.card, { backgroundColor: palette.surface, borderColor: palette.border }]}>
        <Copy>{labels[card.state]}</Copy><Copy>{card.summary}</Copy>
        <Details card={card} clock={c.clock} />
        {card.error ? <Copy>{card.error}</Copy> : null}
        {c.state?.dialogue_protocol === 2 ? <View style={styles.row}>
            {card.state === "pending" ? <Chip label="Подтвердить" disabled={c.busy} onPress={() => perform(card, "dialogue_confirm")} /> : null}
            {["pending", "saved", "needs_correction"].includes(card.state) && card.kind !== "delete_entry" ? <Chip label="Исправить" disabled={c.busy} onPress={() => perform(card, "dialogue_edit")} /> : null}
            {card.state === "pending" ? <Chip label="Не сохранять" disabled={c.busy} onPress={() => perform(card, "dialogue_cancel")} /> : null}
            {card.state === "saved" && card.can_undo ? <Chip label="Отменить запись" disabled={c.busy} onPress={() => perform(card, "dialogue_undo")} /> : null}
        </View> : null}
    </View>)}</>
}

const styles = StyleSheet.create({
    panel: { borderWidth: 1, borderRadius: 16, padding: 8, gap: 6, marginBottom: 6 },
    row: { flexDirection: "row", gap: 6, flexWrap: "wrap", alignItems: "center" },
    chip: { borderRadius: 16, paddingHorizontal: 12, paddingVertical: 10 },
    text: { fontSize: 14, lineHeight: 21 },
    card: { borderWidth: 1, borderRadius: 16, padding: 12, gap: 8, marginTop: 8 },
})
