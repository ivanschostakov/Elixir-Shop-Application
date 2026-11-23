import { useEffect, useRef, useState } from "react"
import { Alert, Image, Pressable, ScrollView, Text, View } from "react-native"
import * as ImagePicker from "expo-image-picker"
import { AppStepTransition } from "@/components/platform/app-step-transition"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { CompanionActionCancelled } from "@/screens/chat/companion-consent"
import { AiConsentDeclinedError } from "@/services/api/ai-data-consent"
import { createAttachmentFromImagePickerAsset } from "@/screens/chat/chat-attachments"
import type { useCompanion } from "@/screens/chat/companion"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import { requestKey, type CompanionAction, type WorkoutPlan } from "@/services/api/companion"
import { requestWorkoutDraft, type WorkoutDraftRequest, type WorkoutSetup } from "@/services/api/companion-workouts"
import { trainingDayNames, trainingEquipment, trainingExperiences, trainingGoals, trainingPlaces, trainingRepLabel, trainingWeekdays, validateTrainingPlan } from "@/screens/chat/mentor-training-data"
import { TrainingAction, TrainingChoice, TrainingField, TrainingFrame, TrainingHeading, TrainingIcon, trainingStyles as styles } from "@/screens/chat/mentor-training-ui"
import { getErrorMessage } from "@/utils/errors"

type Controller = ReturnType<typeof useCompanion>
type SetupDraft = { [K in keyof WorkoutSetup]: K extends "goal" | "experience" | "place" ? WorkoutSetup[K] | null : WorkoutSetup[K] }
type Phase = "setup" | "input" | "review" | "questions" | "revise" | "day" | "exercise"
const headings = ["Ваша цель", "Где тренируетесь?", "Дни тренировок", "Что учесть?", "Добавить фото?"]
const descriptions = ["", "", "Отметьте дни, в которые удобно заниматься", "Пожелания и упражнения, которые стоит исключить", "Покажите исходную форму, если хотите"]
const copyPlan = (plan: WorkoutPlan) => JSON.parse(JSON.stringify(plan)) as WorkoutPlan

export function MentorTrainingPlan({ controller: c, mode, today, onClose, onSaved }: { controller: Controller; mode: "generate" | "import" | "edit"; today: string; onClose: () => void; onSaved: () => void }) {
    const { language } = useLanguage(), colors = useMentorPalette()
    const original = useRef(c.state?.mentor?.workout_plan ?? c.state?.profile?.data.workout_plan ?? null)
    const [phase, setPhase] = useState<Phase>(mode === "edit" && original.current ? "review" : mode === "import" ? "input" : "setup")
    const [step, setStep] = useState(0), [direction, setDirection] = useState(1)
    const [setup, setSetup] = useState<SetupDraft>({ goal: null, experience: null, place: null, equipment: [], weekdays: [], minutes: 45, preferences: "" })
    const [photos, setPhotos] = useState<(UploadableChatAttachment | null)[]>([null, null, null])
    const [text, setText] = useState(""), [answer, setAnswer] = useState(""), [revision, setRevision] = useState("")
    const [questions, setQuestions] = useState<string[]>([]), [message, setMessage] = useState("")
    const [plan, setPlan] = useState<WorkoutPlan | null>(() => mode === "edit" && original.current ? copyPlan(original.current) : null)
    const [dayIndex, setDayIndex] = useState(0), [exerciseIndex, setExerciseIndex] = useState(0)
    const [busy, setBusy] = useState(false), [error, setError] = useState("")
    const alive = useRef(true), locked = useRef(false), generating = useRef(false)
    const draftRequest = useRef<{ signature: string; key: string; payload: WorkoutDraftRequest } | null>(null)
    const saveRequest = useRef<{ signature: string; action: CompanionAction } | null>(null)
    useEffect(() => { alive.current = true; return () => { alive.current = false } }, [])
    const disabled = busy || c.busy
    const changeSetup = (patch: Partial<SetupDraft>) => { setSetup(value => ({ ...value, ...patch })); setError("") }
    const changePlan = (next: WorkoutPlan) => { setPlan(next); setError(""); saveRequest.current = null }
    const move = (next: number) => { setDirection(next > step ? 1 : -1); setStep(next); setError("") }
    const request = async (payload: WorkoutDraftRequest, skipPhotos = false) => {
        if (locked.current || c.busy) return
        if (payload.text.length > 10000) { setError(mt("Сократите описание программы до 10 000 символов")); return }
        locked.current = true; generating.current = true; setBusy(true); setError("")
        try {
            const uploads = skipPhotos ? [] : photos.filter((photo): photo is UploadableChatAttachment => !!photo)
            const signature = JSON.stringify([payload, uploads.map(photo => photo.uri)])
            if (draftRequest.current?.signature !== signature) draftRequest.current = { signature, key: requestKey(), payload }
            const result = await requestWorkoutDraft(draftRequest.current.payload, uploads, draftRequest.current.key)
            if (!alive.current) return
            if (result.plan) {
                const validation = validateTrainingPlan(result.plan)
                if (validation) throw new Error(validation)
                changePlan(result.plan); setPhase("review"); setQuestions([]); setRevision("")
            } else { setQuestions(result.questions); setMessage(result.message); setAnswer(""); setPhase("questions") }
        } catch (failure) { if (alive.current && !(failure instanceof AiConsentDeclinedError)) setError(getErrorMessage(failure)) }
        finally { locked.current = false; generating.current = false; if (alive.current) setBusy(false) }
    }
    const generate = () => request({ mode: "generate", language, start_date: today, text: "", setup: setup as WorkoutSetup })
    const importPlan = () => request({ mode: "import", language, start_date: today, text: text.trim() })
    const save = async () => {
        if (!plan || locked.current || c.busy) return
        const validation = validateTrainingPlan(plan)
        if (validation) { setError(validation); return }
        const latest = c.state?.mentor?.workout_plan ?? c.state?.profile?.data.workout_plan ?? null
        if (JSON.stringify(latest) !== JSON.stringify(original.current)) { setError(mt("Программа изменилась на другом устройстве. Откройте её заново перед сохранением.")); return }
        locked.current = true; setBusy(true); setError("")
        try {
            const signature = JSON.stringify([plan, c.state?.profile?.version])
            if (saveRequest.current?.signature !== signature) saveRequest.current = { signature, action: { kind: "workout_plan", workout_plan: plan, expected_version: c.state?.profile?.version, request_key: requestKey() } }
            await c.perform(saveRequest.current.action)
            if (alive.current) onSaved()
        } catch (failure) { if (alive.current && !(failure instanceof CompanionActionCancelled)) setError(getErrorMessage(failure)) }
        finally { locked.current = false; if (alive.current) setBusy(false) }
    }
    const pickPhoto = async (index: number) => {
        if (locked.current || c.busy) return
        locked.current = true; setBusy(true); setError("")
        try {
            const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.85, allowsMultipleSelection: false })
            if (alive.current && !result.canceled && result.assets[0]) {
                const photo = createAttachmentFromImagePickerAsset(result.assets[0])
                setPhotos(value => value.map((previous, position) => position === index ? photo : previous))
            }
        } catch (failure) { if (alive.current) setError(getErrorMessage(failure)) }
        finally { locked.current = false; if (alive.current) setBusy(false) }
    }
    const back = () => {
        if (c.busy) return
        if (generating.current) { onClose(); return }
        if (locked.current) return
        setError("")
        if (phase === "exercise") setPhase("day")
        else if (phase === "day" || phase === "revise") setPhase("review")
        else if (phase === "questions") setPhase(mode === "import" ? "input" : plan ? "review" : "setup")
        else if (phase === "setup" && step > 0) move(step - 1)
        else if (phase === "review" && mode !== "edit") setPhase(mode === "import" ? "input" : "setup")
        else onClose()
    }
    const footer = (action: React.ReactNode, secondary?: React.ReactNode) => <><View style={styles.errorSlot}>{error ? <Text accessibilityRole="alert" numberOfLines={2} style={[styles.error, { color: colors.text }]}>{error}</Text> : null}</View>{action}{secondary}</>
    const title = (label: string) => <Text style={[styles.section, { color: colors.text }]}>{mt(label)}</Text>
    const setupComplete = step === 0 ? !!setup.goal && !!setup.experience : step === 1 ? !!setup.place && !!setup.equipment.length : step === 2 ? !!setup.weekdays.length : true
    const renderSetup = (page: number) => <ScrollView bounces={false} keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={styles.body}>
        <View><Text style={[styles.caption, { color: colors.muted }]}>{mt("{0} из 5", [page + 1])}</Text><View style={styles.progress}>{headings.map((_, index) => <View key={index} style={[styles.segment, { backgroundColor: index <= page ? colors.greenBright : colors.border }]} />)}</View></View>
        <TrainingHeading title={mt(headings[page])} subtitle={descriptions[page] ? mt(descriptions[page]) : undefined} />
        {page === 0 ? <><View>{Object.entries(trainingGoals).map(([key, label]) => <TrainingChoice key={key} label={mt(label)} selected={setup.goal === key} disabled={disabled} onPress={() => changeSetup({ goal: key as WorkoutSetup["goal"] })} />)}</View>{title("Опыт")}<View style={styles.row}>{Object.entries(trainingExperiences).map(([key, label]) => <TrainingChoice key={key} label={mt(label)} selected={setup.experience === key} pill disabled={disabled} onPress={() => changeSetup({ experience: key as WorkoutSetup["experience"] })} />)}</View></> : null}
        {page === 1 ? <><View style={styles.row}>{Object.entries(trainingPlaces).map(([key, label]) => <TrainingChoice key={key} label={mt(label)} pill selected={setup.place === key} disabled={disabled} onPress={() => changeSetup({ place: key as WorkoutSetup["place"] })} />)}</View>{title("Оборудование")}<View>{Object.entries(trainingEquipment).map(([key, label]) => <TrainingChoice key={key} label={mt(label)} selected={setup.equipment.includes(key as WorkoutSetup["equipment"][number])} disabled={disabled} onPress={() => changeSetup({ equipment: setup.equipment.includes(key as WorkoutSetup["equipment"][number]) ? setup.equipment.filter(value => value !== key) : [...setup.equipment, key as WorkoutSetup["equipment"][number]] })} />)}</View></> : null}
        {page === 2 ? <><View style={[styles.row, { gap: 5 }]}>{trainingWeekdays.map((day, index) => <TrainingChoice key={day} label={mt(day)} pill selected={setup.weekdays.includes(index)} disabled={disabled} onPress={() => changeSetup({ weekdays: setup.weekdays.includes(index) ? setup.weekdays.filter(value => value !== index) : [...setup.weekdays, index].sort() })} />)}</View>{title("Длительность")}<View style={styles.row}>{[30, 45, 60].map(minutes => <TrainingChoice key={minutes} label={mt("{0} мин", [minutes])} pill selected={setup.minutes === minutes} disabled={disabled} onPress={() => changeSetup({ minutes })} />)}</View></> : null}
        {page === 3 ? <TrainingField label={mt("Пожелания к программе")} value={setup.preferences} onChange={preferences => changeSetup({ preferences })} multiline maxLength={2000} disabled={disabled} placeholder={mt("Например: предпочитаю гантели, не люблю бег")} /> : null}
        {page === 4 ? <View style={[styles.row, { alignItems: "flex-start", gap: 10 }]}>{photos.map((photo, index) => <View key={index} style={styles.photo}>
            <Pressable accessibilityRole="button" accessibilityLabel={mt(["Фото спереди", "Фото сбоку", "Фото сзади"][index])} disabled={disabled} onPress={() => void pickPhoto(index)} style={[styles.photoSlot, { backgroundColor: colors.input }]}>{photo ? <Image source={{ uri: photo.uri }} style={styles.photoImage} /> : <TrainingIcon name="photo" size={32} />}</Pressable>
            {photo ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Убрать фото")} disabled={disabled} onPress={() => setPhotos(value => value.map((item, position) => position === index ? null : item))} style={{ position: "absolute", top: 5, right: 5, borderRadius: 16, backgroundColor: colors.surface, width: 32, height: 32, alignItems: "center", justifyContent: "center" }}><TrainingIcon name="close" size={18} /></Pressable> : null}
            <Text style={[styles.photoLabel, { color: colors.muted }]}>{mt(["Спереди", "Сбоку", "Сзади"][index])}</Text>
        </View>)}</View> : null}
    </ScrollView>

    if (phase === "day" && plan) return <TrainingDayEditor plan={plan} index={dayIndex} onChange={changePlan} onBack={back} onExercise={index => { setExerciseIndex(index); setPhase("exercise") }} />
    if (phase === "exercise" && plan) return <TrainingExerciseEditor plan={plan} dayIndex={dayIndex} index={exerciseIndex} onChange={changePlan} onBack={back} />
    if (phase === "setup") return <TrainingFrame title={mt("Новый план")} onBack={back} footer={footer(<TrainingAction label={mt(step === 4 ? "Составить план" : "Далее")} busy={busy} disabled={c.busy || !setupComplete} onPress={() => step < 4 ? move(step + 1) : void generate()} />, step === 4 ? <TrainingAction label={mt("Пропустить")} secondary disabled={disabled} onPress={() => { setPhotos([null, null, null]); void request({ mode: "generate", language, start_date: today, text: "", setup: setup as WorkoutSetup }, true) }} /> : undefined)}><AppStepTransition step={step} direction={direction} count={5} render={renderSetup} /></TrainingFrame>
    if (phase === "review" && plan) return <TrainingFrame title={mt("План тренировок")} onBack={back} footer={footer(<><TrainingAction label={mt("Изменить с наставником")} secondary disabled={disabled} onPress={() => setPhase("revise")} /><TrainingAction label={mt("Сохранить план")} busy={busy} disabled={c.busy} onPress={() => void save()} /></>)}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.body}>
        <TrainingHeading title={mt("Ваша неделя")} subtitle={mt("Проверьте дни, упражнения и подходы")} />
        <TrainingField label={mt("Название программы")} value={plan.name} onChange={name => changePlan({ ...plan, name })} disabled={disabled} />
        {plan.days.map((day, index) => <View key={day.key} style={{ gap: 8 }}><Pressable accessibilityRole="button" accessibilityLabel={mt("Изменить {0}", [day.name])} disabled={disabled} onPress={() => { setDayIndex(index); setPhase("day") }} style={styles.spread}><View style={{ flex: 1 }}><Text style={[styles.section, { color: colors.text }]}>{day.weekdays.map(day => mt(trainingDayNames[day])).join(", ") || mt("Выберите дни")}</Text><Text style={[styles.caption, { color: colors.muted }]}>{day.name}</Text></View><TrainingIcon name="edit" /></Pressable>{day.exercises.map(exercise => <View key={exercise.key} style={[styles.listRow, { minHeight: 44, borderBottomColor: colors.border }]}><Text style={[styles.subtitle, { color: colors.text, flex: 1 }]}>{exercise.name}</Text><Text style={[styles.listValue, { color: colors.muted }]}>{trainingRepLabel(exercise)}</Text></View>)}</View>)}
        <TrainingAction label={mt("Добавить тренировочный день")} secondary onPress={() => { const next = { ...plan, days: [...plan.days, { key: requestKey(), name: mt("Тренировка"), weekdays: [], exercises: [] }] }; changePlan(next); setDayIndex(next.days.length - 1); setPhase("day") }} disabled={disabled || plan.days.length >= 14} />
    </ScrollView></TrainingFrame>
    const isQuestions = phase === "questions", isRevision = phase === "revise"
    const label = isQuestions ? mt("Уточните программу") : isRevision ? mt("Что изменить?") : mt("Ваша программа")
    const value = isQuestions ? answer : isRevision ? revision : text
    return <TrainingFrame title={mt(isRevision ? "План тренировок" : "Свой план")} onBack={back} footer={footer(<TrainingAction label={mt(isQuestions ? "Продолжить" : isRevision ? "Обновить черновик" : "Разобрать программу")} busy={busy} disabled={c.busy || !value.trim()} onPress={() => {
        if (isQuestions && draftRequest.current) void request({ ...draftRequest.current.payload, text: `${draftRequest.current.payload.text}\n${questions.join("\n")}\n${answer.trim()}` })
        else if (isRevision && plan) void request({ mode: "revise", language, start_date: today, text: revision.trim(), current_plan: plan })
        else void importPlan()
    }} />)}><ScrollView keyboardShouldPersistTaps="handled" keyboardDismissMode="on-drag" contentContainerStyle={styles.body}>
        <TrainingHeading title={label} subtitle={isQuestions ? undefined : isRevision ? mt("Например: перенеси пятницу на субботу") : mt("Вставьте готовый план или опишите своими словами")} />
        {isQuestions ? <View style={{ gap: 10 }}>{questions.length ? questions.map(question => <Text key={question} style={[styles.subtitle, { color: colors.text }]}>{question}</Text>) : <Text style={[styles.subtitle, { color: colors.text }]}>{message}</Text>}</View> : null}
        <TrainingField label={label} value={value} onChange={next => { setError(""); if (isQuestions) setAnswer(next); else if (isRevision) setRevision(next); else setText(next) }} multiline maxLength={10000} disabled={disabled} placeholder={isQuestions ? mt("Ваш ответ") : isRevision ? mt("Опишите изменения") : mt("Пн — грудь и трицепс\nЖим лёжа 3×8\nСр — спина")} />
    </ScrollView></TrainingFrame>
}

function TrainingDayEditor({ plan, index, onChange, onBack, onExercise }: { plan: WorkoutPlan; index: number; onChange: (plan: WorkoutPlan) => void; onBack: () => void; onExercise: (index: number) => void }) {
    const colors = useMentorPalette(), day = plan.days[index]
    const [duration, setDuration] = useState(day.duration_minutes == null ? "" : String(day.duration_minutes)), [error, setError] = useState("")
    const change = (patch: Partial<typeof day>) => onChange({ ...plan, days: plan.days.map((day, position) => position === index ? { ...day, ...patch } : day) })
    return <TrainingFrame title={mt("Тренировочный день")} onBack={onBack} footer={<><View style={styles.errorSlot}>{error ? <Text style={[styles.error, { color: colors.text }]}>{error}</Text> : null}</View><TrainingAction label={mt("Готово")} onPress={() => { const value = duration.trim() ? Number(duration) : null; if (value != null && (!Number.isInteger(value) || value < 1 || value > 300)) { setError(mt("Укажите длительность от 1 до 300 минут")); return }; change({ duration_minutes: value }); onBack() }} /></>}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.body}>
        <TrainingField labeled label={mt("Название тренировки")} value={day.name} onChange={name => change({ name })} />
        <View style={[styles.row, { gap: 5 }]}>{trainingWeekdays.map((label, weekday) => <TrainingChoice key={label} label={mt(label)} selected={day.weekdays.includes(weekday)} pill onPress={() => change({ weekdays: day.weekdays.includes(weekday) ? day.weekdays.filter(value => value !== weekday) : [...day.weekdays, weekday].sort() })} />)}</View>
        <TrainingField labeled label={mt("Длительность, минут")} value={duration} numeric onChange={value => { setDuration(value); setError(""); const minutes = value.trim() ? Number(value) : null; if (minutes == null || Number.isInteger(minutes) && minutes >= 1 && minutes <= 300) change({ duration_minutes: minutes }) }} />
        {day.exercises.map((exercise, position) => <Pressable key={exercise.key} accessibilityRole="button" accessibilityLabel={exercise.name || mt("Новое упражнение")} onPress={() => onExercise(position)} style={[styles.listRow, { borderBottomColor: colors.border }]}><Text style={[styles.listTitle, { flex: 1, color: colors.text }]}>{exercise.name || mt("Новое упражнение")}</Text><Text style={[styles.caption, { color: colors.muted }]}>{trainingRepLabel(exercise)}</Text><TrainingIcon name="edit" /></Pressable>)}
        <TrainingAction label={mt("Добавить упражнение")} secondary disabled={day.exercises.length >= 30} onPress={() => { const exercises = [...day.exercises, { key: requestKey(), name: "", sets: 1, target_reps: null, target_weight_kg: null }]; change({ exercises }); onExercise(exercises.length - 1) }} />
        <TrainingAction label={mt("Удалить тренировку из плана")} secondary onPress={() => Alert.alert(mt("Удалить тренировку из плана?"), day.name, [{ text: mt("Отмена"), style: "cancel" }, { text: mt("Удалить"), style: "destructive", onPress: () => { onChange({ ...plan, days: plan.days.filter((_, position) => position !== index) }); onBack() } }])} />
    </ScrollView></TrainingFrame>
}

function TrainingExerciseEditor({ plan, dayIndex, index, onChange, onBack }: { plan: WorkoutPlan; dayIndex: number; index: number; onChange: (plan: WorkoutPlan) => void; onBack: () => void }) {
    const exercise = plan.days[dayIndex].exercises[index]
    const [name, setName] = useState(exercise.name), [sets, setSets] = useState(String(exercise.sets))
    const [reps, setReps] = useState(exercise.target_reps == null ? "" : exercise.target_reps_max && exercise.target_reps_max !== exercise.target_reps ? `${exercise.target_reps}–${exercise.target_reps_max}` : String(exercise.target_reps))
    const [weight, setWeight] = useState(exercise.target_weight_kg == null ? "" : String(exercise.target_weight_kg)), [rest, setRest] = useState(exercise.rest_seconds == null ? "" : String(exercise.rest_seconds))
    const [error, setError] = useState("")
    const colors = useMentorPalette()
    const done = () => {
        const range = /^\s*(\d+)\s*(?:[–—-]\s*(\d+))?\s*$/.exec(reps)
        if (reps.trim() && !range) { setError(mt("Укажите число повторений или диапазон, например 8–12")); return }
        const next = copyPlan(plan)
        next.days[dayIndex].exercises[index] = { ...exercise, name: name.trim(), sets: Number(sets), target_reps: range ? Number(range[1]) : null, target_reps_max: range?.[2] ? Number(range[2]) : null, target_weight_kg: weight.trim() ? weight.replace(",", ".") : null, rest_seconds: rest.trim() ? Number(rest) : null }
        // Validate the edited exercise independently while other new draft days may be incomplete.
        const validation = validateTrainingPlan({ ...next, days: [{ ...next.days[dayIndex], weekdays: [0], exercises: [next.days[dayIndex].exercises[index]] }] })
        if (validation) { setError(validation); return }
        onChange(next); onBack()
    }
    return <TrainingFrame title={mt("Упражнение")} onBack={onBack} footer={<><View style={styles.errorSlot}>{error ? <Text accessibilityRole="alert" numberOfLines={2} style={[styles.error, { color: colors.text }]}>{error}</Text> : null}</View><TrainingAction label={mt("Готово")} onPress={done} /></>}><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.body}>
        <TrainingField labeled label={mt("Название упражнения")} value={name} onChange={setName} />
        <TrainingField labeled label={mt("Подходов")} numeric value={sets} onChange={setSets} maxLength={2} />
        <TrainingField labeled label={mt("Повторения, например 8–12")} value={reps} onChange={setReps} maxLength={12} />
        <TrainingField labeled label={mt("Вес, кг (по желанию)")} numeric value={weight} onChange={setWeight} maxLength={8} />
        <TrainingField labeled label={mt("Отдых, секунд (по желанию)")} numeric value={rest} onChange={setRest} maxLength={4} />
        <TrainingAction label={mt("Удалить упражнение")} secondary onPress={() => { const next = copyPlan(plan); next.days[dayIndex].exercises = next.days[dayIndex].exercises.filter((_, position) => position !== index); onChange(next); onBack() }} />
    </ScrollView></TrainingFrame>
}
