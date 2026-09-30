import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Alert, View } from "react-native"
import { getCompanionProgressPhotos, requestKey } from "@/services/api/companion"
import type { CompanionEntry } from "@/services/api/companion"
import type { AIAttachmentRead, AIMessageRead } from "@/services/api/ai-chat.types"
import type { useCompanion } from "@/screens/chat/companion"
import { calendarDate, formatCompanionDate } from "@/screens/chat/companion-timezones"
import { MentorButton as Button, MentorText as Copy, mentorStyles as styles } from "@/screens/chat/mentor-ui"

export function MentorPhotos({ controller: c, days, messages, renderAttachments }: { controller: ReturnType<typeof useCompanion>; days: number; messages: AIMessageRead[]; renderAttachments: (attachments: AIAttachmentRead[]) => React.ReactNode }) {
    const [entries, setEntries] = useState<CompanionEntry[]>([])
    const [draft, setDraft] = useState<AIMessageRead | null>(null)
    const [loading, setLoading] = useState(false)
    const [more, setMore] = useState(false)
    const [reload, setReload] = useState(0)
    const key = useRef(requestKey())
    const ref = useRef(c); ref.current = c
    useEffect(() => {
        let cancelled = false
        setLoading(true)
        void getCompanionProgressPhotos(calendarDate(1 - days), calendarDate(1)).then(result => { if (!cancelled) { setEntries(result.entries); setMore(result.may_have_more) } }).catch(error => { if (!cancelled) ref.current.setError(error instanceof Error ? error.message : "Не удалось загрузить фото") }).finally(() => { if (!cancelled) setLoading(false) })
        return () => { cancelled = true }
    }, [days, c.clock, reload])
    const privateImages = (message: AIMessageRead) => message.sender === "user" ? message.attachments.filter(attachment => attachment.type === "image" && attachment.is_private) : []
    const savedIds = new Set(entries.flatMap(entry => entry.data.photo_attachment_ids ?? []))
    const candidates = messages.filter(message => /фото прогресса/i.test(message.text) && privateImages(message).some(attachment => !savedIds.has(attachment.id)))
    return <View style={styles.section}>
        <Button label="Обновить фото" disabled={loading} onPress={() => setReload(value => value + 1)} />
        {loading ? <ActivityIndicator /> : null}
        {draft ? <View style={styles.section}><Copy heading>Сохранить фото в прогресс?</Copy><Copy muted>{formatCompanionDate(draft.created_at, c.clock)}</Copy>{renderAttachments(privateImages(draft))}<Button label="Подтвердить сохранение фото" primary disabled={c.busy} onPress={() => void c.attempt(async () => { await c.perform({ kind: "entry", request_key: key.current, entry: { kind: "progress_photo", occurred_at: draft.created_at, photo_attachment_ids: privateImages(draft).map(attachment => attachment.id), note: "Фото прогресса" } }); setDraft(null); setReload(value => value + 1) })} /><Button label="Отмена" onPress={() => setDraft(null)} /></View> : null}
        {candidates.map(message => <View key={message.id} style={styles.section}><Copy muted>Из вашего диалога · {formatCompanionDate(message.created_at, c.clock)}</Copy>{renderAttachments(privateImages(message))}<Button label="Сохранить в прогресс" disabled={c.busy || privateImages(message).length > 8} onPress={() => { key.current = requestKey(); setDraft(message) }} /></View>)}
        {entries.map(entry => <View key={entry.id} style={styles.section}><Copy>{formatCompanionDate(entry.occurred_at, c.clock)}</Copy>{renderAttachments(entry.photo_attachments ?? [])}{entry.unavailable_photo_attachment_ids?.length ? <Copy muted>Часть исходных фото удалена или недоступна.</Copy> : null}<Button label="Удалить запись о фото" disabled={c.busy} onPress={() => Alert.alert("Удалить запись о фото?", "Запись исчезнет из прогресса. Исходное вложение останется в диалоге.", [{ text: "Отмена", style: "cancel" }, { text: "Удалить", style: "destructive", onPress: () => void c.attempt(async () => { await c.perform({ kind: "delete_entry", resource_id: entry.id, expected_version: entry.version }); setReload(value => value + 1) }) }])} /></View>)}
        {!loading && !entries.length && !candidates.length ? <Copy muted>За этот период нет сохранённых фото прогресса.</Copy> : null}
        {more ? <Copy muted>Показаны последние {entries.length} записей. Выберите меньший период.</Copy> : null}
    </View>
}
