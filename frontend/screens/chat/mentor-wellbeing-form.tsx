import { useRef, useState } from "react"
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native"
import { Picker } from "@react-native-picker/picker"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { AppLevelSlider } from "@/components/platform/app-level-slider"
import { AppStepTransition } from "@/components/platform/app-step-transition"
import Animated, { FadeIn, FadeOut, ReduceMotion } from "react-native-reanimated"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { CompanionActionCancelled } from "@/screens/chat/companion-consent"
import { calendarDate, companionCalendarDay } from "@/screens/chat/companion-timezones"
import type { useCompanion } from "@/screens/chat/companion"
import { requestKey, type CompanionAction } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"
import { appetiteChoice, appetiteLabels, energyLabels, moodLabels, sleepQualityLabels, stressLabels, wellbeingDateLabel, wellbeingDraft, wellbeingLabels, wellbeingSaveAction, wellbeingStepComplete, wellbeingSummary, type WellbeingDraft } from "@/screens/chat/mentor-wellbeing-data"
import { WellbeingIcon, type WellbeingIconName } from "@/screens/chat/mentor-wellbeing-icons"
import { wellbeingStyles as styles } from "@/screens/chat/mentor-wellbeing.styles"

type Controller = ReturnType<typeof useCompanion>
const headings = ["Как вы себя чувствуете?", "Сколько было энергии?", "Настроение и стресс", "Как вы спали?", "Какой был аппетит?", "Что повлияло на день?"]
const descriptions = ["Оцените день в целом", "Вспомните, как прошёл день", "Отметьте своё состояние за день", "Ночь перед выбранным днём", "Оцените аппетит в течение дня", "Заметка по желанию"]

export function MentorWellbeingEditor({ controller: c, onClose }: { controller: Controller; onClose: () => void }) {
    useLanguage()
    const colors = useMentorPalette()
    const { top, bottom } = useSafeAreaInsets()
    const original = c.editor?.entry
    const day = c.editor?.date ?? (original ? companionCalendarDay(original.occurred_at, c.clock) : calendarDate())
    const [draft, setDraft] = useState(() => wellbeingDraft(original?.data ?? c.editor?.proposal?.entry ?? undefined))
    const [step, setStep] = useState(0)
    const [direction, setDirection] = useState(1)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState("")
    const pending = useRef<{ signature: string; action: CompanionAction } | null>(null)
    const savingNow = useRef(false)
    const busy = saving || c.busy
    const maxNoteLength = Math.max(500, original?.data.note?.length ?? 0)
    const change = (patch: Partial<WellbeingDraft>) => { setDraft(value => ({ ...value, ...patch })); setError("") }
    const move = (next: number) => { setDirection(next > step ? 1 : -1); setStep(next); setError("") }
    const back = () => { if (!busy) { if (step > 0) move(step - 1); else onClose() } }
    const save = async () => {
        if (savingNow.current || c.busy) return
        savingNow.current = true; setSaving(true); setError("")
        try {
            const signature = JSON.stringify({ day, draft, id: original?.id, version: original?.version })
            if (pending.current?.signature !== signature) pending.current = { signature, action: wellbeingSaveAction(draft, day, requestKey(), original) }
            await c.perform(pending.current.action)
            pending.current = null
            onClose()
        } catch (failure) {
            if (!(failure instanceof CompanionActionCancelled)) setError(getErrorMessage(failure))
        } finally { savingNow.current = false; setSaving(false) }
    }
    const primaryLabel = step === 5 ? mt("Сохранить запись") : mt("Далее")
    const renderStep = (page: number) => (
        <ScrollView bounces={false} contentInsetAdjustmentBehavior="never" automaticallyAdjustContentInsets={false} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={styles.content}>
            <View>
                <View style={styles.row}><Text style={[styles.subtitle, { color: colors.green }]}>{wellbeingDateLabel(day)}</Text><Text accessibilityLiveRegion="polite" style={[styles.subtitle, { color: colors.muted }]}>{mt("{0} из 6", [page + 1])}</Text></View>
                <View accessibilityRole="progressbar" accessibilityValue={{ min: 1, max: 6, now: page + 1 }} style={styles.progress}>{headings.map((_, index) => <View key={index} style={[styles.progressPart, { backgroundColor: index <= page ? colors.greenBright : colors.border }]} />)}</View>
            </View>
            <View style={{ gap: 8 }}><Text accessibilityRole="header" style={[styles.title, { color: colors.text }]}>{mt(headings[page])}</Text><Text style={[styles.subtitle, { color: colors.muted }]}>{mt(descriptions[page])}</Text></View>
            {page === 0 ? <RatingControl label={mt("Состояние")} labels={wellbeingLabels} value={draft.wellbeing} onChange={wellbeing => change({ wellbeing })} icon="face" disabled={busy} testID="wellbeing-overall" /> : null}
            {page === 1 ? <RatingControl label={mt("Энергия")} labels={energyLabels} value={draft.energy} onChange={energy => change({ energy })} icon="energy" disabled={busy} testID="wellbeing-energy" /> : null}
            {page === 2 ? <>
                <RatingControl label={mt("Настроение")} labels={moodLabels} value={draft.mood} onChange={mood => change({ mood })} icon="face" iconLevels={[1, 3, 5]} disabled={busy} compact testID="wellbeing-mood" />
                <RatingControl label={mt("Уровень стресса")} labels={stressLabels} value={draft.stress} onChange={stress => change({ stress })} icon="stress" disabled={busy} compact testID="wellbeing-stress" />
            </> : null}
            {page === 3 ? <>
                <View style={[styles.card, { backgroundColor: colors.surface }]}><View style={styles.row}><Text style={[styles.sectionTitle, { color: colors.text, flex: 1 }]}>{mt("Продолжительность сна")}</Text><WellbeingIcon name="moon" color={colors.green} size={32} /></View>
                    <View style={styles.wheelRow}>
                        <Picker accessibilityLabel={mt("Часы сна")} enabled={!busy} selectedValue={draft.sleepMinutes == null ? -1 : Math.floor(draft.sleepMinutes / 60)} onValueChange={value => { if (Number(value) >= 0) change({ sleepMinutes: Number(value) * 60 + (Number(value) === 24 ? 0 : (draft.sleepMinutes ?? 0) % 60) }) }} style={[styles.wheel, { color: colors.text }]} itemStyle={[styles.wheelItem, { color: colors.text }]}>
                            <Picker.Item label={mt("Часы")} value={-1} />{Array.from({ length: 25 }, (_, value) => <Picker.Item key={value} label={mt("{0} ч", [value])} value={value} />)}
                        </Picker>
                        <Picker accessibilityLabel={mt("Минуты сна")} enabled={!busy && draft.sleepMinutes !== 1440} selectedValue={(draft.sleepMinutes ?? 0) % 60} onValueChange={value => change({ sleepMinutes: Math.floor((draft.sleepMinutes ?? 0) / 60) * 60 + Number(value) })} style={[styles.wheel, { color: colors.text }]} itemStyle={[styles.wheelItem, { color: colors.text }]}>
                            {Array.from({ length: 60 }, (_, value) => <Picker.Item key={value} label={mt("{0} мин", [value])} value={value} />)}
                        </Picker>
                    </View>
                </View>
                <RatingControl label={mt("Насколько выспались?")} labels={sleepQualityLabels} value={draft.sleepQuality} onChange={sleepQuality => change({ sleepQuality })} icon="moon" disabled={busy} compact testID="wellbeing-sleep-quality" />
            </> : null}
            {page === 4 ? <RatingControl label={mt("Аппетит")} labels={appetiteLabels} value={draft.appetite == null ? null : appetiteChoice(draft.appetite)! + 1} onChange={value => change({ appetite: [1, 3, 5][value - 1] })} icon="apple" disabled={busy} testID="wellbeing-appetite" /> : null}
            {page === 5 ? <>
                <View style={[styles.card, { backgroundColor: colors.surface, padding: 0 }]}><TextInput accessibilityLabel={mt("Заметка по желанию")} editable={!busy} multiline maxLength={maxNoteLength} value={draft.note} onChangeText={note => change({ note })} placeholder={mt("Что запомнилось за день?")} placeholderTextColor={colors.muted} selectionColor={colors.greenBright} style={[styles.note, { color: colors.text, backgroundColor: colors.input }]} /><Text style={[styles.counter, { color: colors.muted }]}>{draft.note.length} / {maxNoteLength}</Text></View>
                <View style={[styles.card, { backgroundColor: colors.surface, gap: 8 }]}><Text style={[styles.sectionTitle, { color: colors.text }]}>{mt("Ваша запись")}</Text><WellbeingSummary draft={draft} /></View>
            </> : null}
            {error ? <View accessibilityRole="alert" style={[styles.error, { borderColor: colors.border, backgroundColor: colors.surface }]}><Text style={[styles.subtitle, { color: colors.text }]}>{error}</Text></View> : null}
        </ScrollView>
    )
    return <View testID="wellbeing-questionnaire" style={[styles.screen, { paddingTop: top, backgroundColor: colors.surface }]}>
        <MentorHomeHeader title={mt("Самочувствие")} onBack={back} />
        <AppStepTransition step={step} direction={direction} count={6} render={renderStep} />
        <View style={[styles.footer, { paddingBottom: Math.max(bottom, 16) }]}>
            <Pressable accessibilityRole="button" accessibilityLabel={primaryLabel} accessibilityState={{ disabled: busy || !wellbeingStepComplete(step, draft), busy: saving }} disabled={busy || !wellbeingStepComplete(step, draft)} onPress={() => { if (step < 5) move(step + 1); else void save() }} style={({ pressed }) => [styles.primary, { backgroundColor: colors.greenBright, opacity: busy || !wellbeingStepComplete(step, draft) ? 0.45 : pressed ? 0.8 : 1 }]}>
                {saving ? <ActivityIndicator color="#FFFFFF" /> : null}<Text style={styles.primaryLabel}>{primaryLabel}</Text>
            </Pressable>
            <Text accessibilityElementsHidden={step !== 5} importantForAccessibility={step === 5 ? "auto" : "no-hide-descendants"} style={[styles.caption, styles.captionSlot, { color: colors.muted, opacity: step === 5 ? 1 : 0 }]}>{mt("Запись появится в календаре")}</Text>
        </View>
    </View>
}

function RatingControl({ label, labels, value, onChange, icon, iconLevels, disabled, compact = false, testID }: { label: string; labels: readonly string[]; value: number | null; onChange: (value: number) => void; icon: WellbeingIconName; iconLevels?: number[]; disabled: boolean; compact?: boolean; testID: string }) {
    const colors = useMentorPalette()
    const selected = value == null ? mt("Передвиньте ползунок") : mt(labels[value - 1])
    const level = value == null ? Math.ceil(labels.length / 2) : value
    const iconLevel = iconLevels?.[level - 1] ?? level
    return <View style={[styles.card, { backgroundColor: colors.surface, gap: compact ? 8 : 14 }]}>
        {compact ? <Text style={[styles.sectionTitle, { color: colors.text }]}>{label}</Text> : null}
        <View style={{ alignItems: "center", paddingTop: compact ? 0 : 8 }}>
            <View style={{ width: compact ? 62 : 112, height: compact ? 62 : 112 }}>
                <Animated.View key={`${icon}:${iconLevel}`} entering={FadeIn.duration(140).reduceMotion(ReduceMotion.System)} exiting={FadeOut.duration(100).reduceMotion(ReduceMotion.System)} style={{ position: "absolute", inset: 0, alignItems: "center", justifyContent: "center" }}>
                    <WellbeingIcon name={icon} level={iconLevel} color={colors.green} size={compact ? 56 : 98} />
                </Animated.View>
            </View>
        </View>
        <Text accessibilityLiveRegion="polite" numberOfLines={2} adjustsFontSizeToFit style={[styles.heroLabel, compact ? styles.compactRatingLabel : styles.ratingLabel, { color: colors.text, fontSize: compact ? 18 : 22, lineHeight: compact ? 24 : 29 }]}>{selected}</Text>
        <AppLevelSlider testID={testID} label={label} value={value} maximum={labels.length} valueText={selected} onChange={onChange} disabled={disabled} color={colors.greenBright} trackColor={colors.border} />
        <View style={styles.row}><Text numberOfLines={2} style={[styles.endpoint, { color: colors.muted }]}>{mt(labels[0])}</Text><Text numberOfLines={2} style={[styles.endpoint, { color: colors.muted, textAlign: "right" }]}>{mt(labels[labels.length - 1])}</Text></View>
    </View>
}

export function WellbeingSummary({ draft }: { draft: WellbeingDraft }) {
    const colors = useMentorPalette()
    const icons: WellbeingIconName[] = ["heart", "energy", "face", "stress", "moon", "moon", "apple"]
    return <View>{wellbeingSummary(draft).map(([label, value], index) => <View key={label} style={[styles.summaryRow, { borderBottomColor: colors.border }]}><WellbeingIcon name={icons[index]} color={colors.green} size={21} /><Text style={[styles.summaryLabel, { color: colors.muted }]}>{label}</Text><Text style={[styles.summaryValue, { color: colors.text }]}>{value}</Text></View>)}</View>
}
