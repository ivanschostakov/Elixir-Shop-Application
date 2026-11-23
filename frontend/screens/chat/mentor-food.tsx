import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, ActionSheetIOS, Alert, Image, Keyboard, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native"
import * as ImagePicker from "expo-image-picker"
import { RecordingPresets, setAudioModeAsync, useAudioRecorder, useAudioRecorderState } from "expo-audio"
import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { requestChatRecordingPermission } from "@/screens/chat/chat-recording-permission"
import { createAttachmentFromImagePickerAsset, getVoiceRecordingFilename, getVoiceRecordingMimeType } from "@/screens/chat/chat-attachments"
import { CHAT_IDLE_AUDIO_MODE, CHAT_RECORDING_AUDIO_MODE } from "@/screens/chat/chat-screen.constants"
import type { useCompanion } from "@/screens/chat/companion"
import { appendFoodDictation, foodDescription, foodSaveAction } from "@/screens/chat/mentor-food-data"
import { MentorHomeHeader } from "@/screens/chat/mentor-home"
import { MentorMealImage } from "@/screens/chat/mentor-meal-image"
import { entryMeal, needsFoodDetails, suggestedMeal } from "@/screens/chat/mentor-meals-data"
import { MentorMealSelector } from "@/screens/chat/mentor-meal-selector"
import { mentorHomeNumber } from "@/screens/chat/mentor-home-data"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { askNutritionHelp, estimateCompanionFood } from "@/services/api/companion-food"
import { transcribeMyAiChatVoice } from "@/services/api/ai-chat"
import { AiConsentDeclinedError } from "@/services/api/ai-data-consent"
import type { UploadableChatAttachment } from "@/services/api/ai-chat.types"
import { getMealLibrary, requestKey, type CompanionAction, type CompanionEntry, type EntryData, type MealType } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"

type Phase = "idle" | "picking" | "recording" | "transcribing" | "calculating" | "saving"
type Controller = ReturnType<typeof useCompanion>

export function MentorFoodEditor({ controller: c, shown, onClose, onSaved, helpMode }: { controller: Controller; shown: boolean; onClose: () => void; onSaved: () => Promise<void>; helpMode?: "suggest" | "product" }) {
    const { t } = useLanguage()
    const { isDark } = useTheme()
    const colors = useMentorPalette()
    const original = useRef<CompanionEntry | undefined>(c.editor?.entry).current
    const [selectedMeal, setSelectedMeal] = useState<MealType>(() => c.editor?.mealType ?? (original ? entryMeal(original, c.clock) : suggestedMeal(c.clock)))
    const [recent, setRecent] = useState<CompanionEntry[]>([])
    const [recipe, setRecipe] = useState<CompanionEntry | null>(original ?? null)
    const [answer, setAnswer] = useState("")
    const previousPhoto = recipe?.photo_attachments?.[0]
    const [text, setText] = useState(() => foodDescription(original?.data ?? c.editor?.proposal?.entry))
    const [photo, setPhoto] = useState<UploadableChatAttachment | null>(null)
    const [estimate, setEstimate] = useState<EntryData | null>(null)
    const [phase, setPhase] = useState<Phase>("idle")
    const [error, setError] = useState("")
    const input = useRef<TextInput>(null)
    const alive = useRef(true)
    const phaseRef = useRef<Phase>("idle")
    const isRecording = () => phaseRef.current === "recording"
    const estimateRequest = useRef<{ fingerprint: string; key: string } | null>(null)
    const saveRequest = useRef<CompanionAction | null>(null)
    const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY)
    const recording = useAudioRecorderState(recorder, 250)
    const busy = phase !== "idle" || c.busy
    const transition = (next: Phase) => { phaseRef.current = next; if (alive.current) setPhase(next) }
    useEffect(() => {
        alive.current = true
        return () => {
            alive.current = false
            try { void recorder.stop().catch(() => undefined) } catch { /* Native recorder may already be released. */ }
            if (phaseRef.current === "recording" || phaseRef.current === "transcribing") void setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined)
        }
    }, [recorder])
    useEffect(() => { if (shown) input.current?.focus() }, [shown])
    useEffect(() => {
        if (helpMode) return
        let disposed = false
        void getMealLibrary().then(result => { if (!disposed) setRecent(result.entries) }).catch(() => {})
        return () => { disposed = true }
    }, [helpMode])
    const changeText = (value: string) => { setText(value); setError(""); saveRequest.current = null }
    const calculate = async (force = false) => {
        if (phaseRef.current !== "idle" || c.busy || !text.trim() && !photo && !previousPhoto && helpMode !== "suggest") return
        if (!force && !helpMode && needsFoodDetails(text, !!photo || !!previousPhoto)) {
            Alert.alert(mt("Добавьте подробности"), mt("Укажите состав и примерную порцию — так расчёт будет точнее, а рецепт можно будет использовать снова."), [{ text: mt("Дополнить"), style: "cancel", onPress: () => input.current?.focus() }, { text: mt("Рассчитать так"), onPress: () => void calculate(true) }])
            return
        }
        Keyboard.dismiss(); setError(""); transition("calculating")
        const fingerprint = JSON.stringify([text.trim(), photo, previousPhoto?.id, helpMode])
        if (estimateRequest.current?.fingerprint !== fingerprint) estimateRequest.current = { fingerprint, key: requestKey() }
        try {
            const result = helpMode ? await askNutritionHelp(helpMode, text || mt("Что можно съесть с учётом оставшихся КБЖУ и моих предпочтений?"), photo, estimateRequest.current.key) : await estimateCompanionFood(text, photo, estimateRequest.current.key, previousPhoto?.id)
            if (!alive.current) return
            if (helpMode) { setAnswer(result.message); return }
            if (!result.entry) { setError(result.message || mt("Не удалось рассчитать КБЖУ. Уточните описание еды.")); input.current?.focus(); return }
            // Validate the estimate before offering its save action.
            foodSaveAction(result.entry, text, "validate-food", original)
            saveRequest.current = null; setEstimate(result.entry)
        } catch (e) { if (alive.current && !(e instanceof AiConsentDeclinedError)) setError(getErrorMessage(e)) }
        finally { transition("idle") }
    }
    const save = async () => {
        if (phaseRef.current !== "idle" || c.busy || !estimate) return
        transition("saving"); setError("")
        try {
            saveRequest.current ??= foodSaveAction(estimate, text, requestKey(), original, new Date(), selectedMeal, c.editor?.mealKey)
            await c.perform(saveRequest.current)
            if (alive.current) await onSaved()
        } catch (e) { if (alive.current) setError(getErrorMessage(e)) }
        finally { transition("idle") }
    }
    const pickPhoto = async (camera: boolean) => {
        if (phaseRef.current !== "idle") return
        Keyboard.dismiss(); setError(""); transition("picking")
        try {
            if (camera && !(await ImagePicker.requestCameraPermissionsAsync()).granted) { if (alive.current) setError(t("chat.attachmentsPhotoPermissionMessage")); return }
            const options: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], quality: 0.92, allowsMultipleSelection: false }
            const result = camera ? await ImagePicker.launchCameraAsync(options) : await ImagePicker.launchImageLibraryAsync(options)
            if (!alive.current || result.canceled || !result.assets[0]) return
            setRecipe(null); setPhoto(createAttachmentFromImagePickerAsset(result.assets[0])); saveRequest.current = null
        } catch (e) { if (alive.current) setError(getErrorMessage(e)) }
        finally { transition("idle"); if (alive.current) input.current?.focus() }
    }
    const photoOptions = () => {
        if (busy) return
        Keyboard.dismiss()
        if (Platform.OS === "ios") ActionSheetIOS.showActionSheetWithOptions({ options: [mt("Отмена"), mt("Сделать фото"), mt("Выбрать из галереи")], cancelButtonIndex: 0, userInterfaceStyle: isDark ? "dark" : "light" }, selected => { if (selected > 0) void pickPhoto(selected === 1) })
        else Alert.alert(mt("Фото еды"), undefined, [{ text: mt("Сделать фото"), onPress: () => void pickPhoto(true) }, { text: mt("Выбрать из галереи"), onPress: () => void pickPhoto(false) }, { text: mt("Отмена"), style: "cancel" }])
    }
    const voice = async () => {
        if (phaseRef.current === "recording") {
            transition("transcribing")
            try {
                await recorder.stop()
                const uri = recorder.uri ?? recorder.getStatus().url
                await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE)
                if (!alive.current) return
                if (!uri) throw new Error(t("chat.voiceTranscriptionFailedMessage"))
                const result = await transcribeMyAiChatVoice({ uri, fileName: getVoiceRecordingFilename(uri), mimeType: getVoiceRecordingMimeType(uri) })
                if (alive.current) { setText(value => appendFoodDictation(value, result.text)); input.current?.focus() }
            } catch (e) { if (alive.current && !(e instanceof AiConsentDeclinedError)) setError(getErrorMessage(e)) }
            finally { await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined); transition("idle") }
            return
        }
        if (phaseRef.current !== "idle" || c.busy) return
        transition("transcribing"); setError(""); Keyboard.dismiss()
        try {
            if (!await requestChatRecordingPermission(t) || !alive.current) return
            await setAudioModeAsync(CHAT_RECORDING_AUDIO_MODE)
            await recorder.prepareToRecordAsync()
            if (!alive.current) { await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE); return }
            recorder.record(); transition("recording")
        } catch (e) { if (alive.current) setError(getErrorMessage(e)); await setAudioModeAsync(CHAT_IDLE_AUDIO_MODE).catch(() => undefined) }
        finally { if (!isRecording()) transition("idle") }
    }
    const close = () => { if (phaseRef.current !== "saving") { Keyboard.dismiss(); onClose() } }
    const hasFood = !!text.trim() || !!photo || !!previousPhoto || helpMode === "suggest"
    const primaryLabel = estimate ? mt("Сохранить") : answer ? mt("Задать другой вопрос") : helpMode === "product" ? mt("Узнать о продукте") : helpMode === "suggest" ? mt("Подобрать варианты") : mt("Рассчитать КБЖУ")
    const title = helpMode === "product" ? mt("О продукте") : helpMode === "suggest" ? mt("Что поесть?") : estimate ? estimate.kind === "water" ? mt("Вода") : mt("Расчёт КБЖУ") : original ? mt("Изменить блюдо") : mt("Добавить еду")
    const placeholder = helpMode === "product" ? mt("О каком продукте хотите узнать?") : helpMode === "suggest" ? mt("Какие продукты есть дома?") : mt("Что вы съели? Добавьте и выпитую воду, например: курица с рисом и 300 мл воды.")
    const seconds = Math.floor(recording.durationMillis / 1000)
    const enteringFood = !estimate && !answer && !helpMode
    const content = <>
        {!helpMode && !estimate ? <MentorMealSelector value={selectedMeal} disabled={busy} onChange={type => { setSelectedMeal(type); saveRequest.current = null }} /> : null}
        {answer ? <View style={[styles.answer, { backgroundColor: colors.soft }]}><Text selectable style={{ color: colors.text, fontSize: 17, lineHeight: 26, fontWeight: "500" }}>{answer}</Text></View> : estimate ? <View style={styles.result}>
            <Text style={[styles.foodName, { color: colors.text }]}>{estimate.kind === "water" ? mt("Вода") : estimate.name}</Text>
            <Text style={[styles.calories, { color: estimate.kind === "water" ? colors.blue : colors.green }]}>{mentorHomeNumber(estimate.kind === "water" ? estimate.water_ml : estimate.nutrition?.kcal)}<Text style={styles.unit}> {estimate.kind === "water" ? mt("мл") : mt("ккал")}</Text></Text>
            {estimate.kind === "meal" ? <View style={styles.macros}>{(["protein", "fat", "carbs"] as const).map((key, index) => <View key={key} style={[styles.macro, index > 0 && { borderLeftWidth: 1, borderLeftColor: colors.border }]}><Text style={[styles.macroLabel, { color: colors.muted }]}>{[mt("Белки"), mt("Жиры"), mt("Углеводы")][index]}</Text><Text style={[styles.macroValue, { color: colors.text }]}>{mentorHomeNumber(estimate.nutrition?.[key])} {mt("г")}</Text></View>)}</View> : null}
            {estimate.kind === "meal" && estimate.water_ml ? <View style={[styles.waterResult, { backgroundColor: colors.soft }]}><Text style={[styles.photoLabel, { color: colors.text }]}>{mt("Вода")}</Text><Text style={[styles.photoLabel, { color: colors.blue }]}>{mentorHomeNumber(estimate.water_ml)} {mt("мл")}</Text></View> : null}
            <Text numberOfLines={3} style={[styles.caption, { color: colors.muted }]}>{estimate.assumptions || mt("Приблизительная оценка")}</Text>
        </View> : <View style={[styles.composer, { backgroundColor: colors.soft, borderColor: colors.border }]}>
            <TextInput ref={input} accessibilityLabel={placeholder} value={text} onChangeText={changeText} placeholder={placeholder} placeholderTextColor={colors.muted} maxLength={4000} multiline textAlignVertical="top" editable={phase === "idle"} keyboardAppearance={isDark ? "dark" : "light"} selectionColor={colors.greenBright} style={[styles.input, { color: colors.text }]} />
            {photo || previousPhoto ? <View style={styles.photo}>{photo ? <Image source={{ uri: photo.uri }} style={styles.thumbnail} /> : previousPhoto ? <MentorMealImage attachment={previousPhoto} style={styles.thumbnail} /> : null}<Pressable accessibilityRole="button" accessibilityLabel={mt("Убрать фото")} disabled={busy} onPress={() => { setPhoto(null); setRecipe(null); saveRequest.current = null }} style={[styles.remove, { backgroundColor: colors.surface }]}><MentorQuestionIcon name="close" size={16} color={colors.green} /></Pressable></View> : null}
            <View style={[styles.toolbar, { borderTopColor: colors.border }]}><Pressable accessibilityRole="button" accessibilityLabel={mt("Фото еды")} disabled={busy} onPress={photoOptions} style={styles.photoButton}><MentorQuestionIcon name="camera" color={colors.green} size={25} /><Text style={[styles.photoLabel, { color: colors.green }]}>{mt("Фото")}</Text></Pressable>
                <View style={styles.voiceArea}>{phase === "recording" ? <Text accessibilityLiveRegion="polite" style={[styles.caption, { color: colors.green }]}>{`${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`}</Text> : phase === "transcribing" ? <ActivityIndicator color={colors.green} /> : null}<Pressable accessibilityRole="button" accessibilityLabel={phase === "recording" ? mt("Завершить диктовку") : mt("Надиктовать описание")} accessibilityState={{ disabled: busy && phase !== "recording" }} disabled={busy && phase !== "recording"} onPress={() => void voice()} style={[styles.microphone, { backgroundColor: colors.mint }]}><MentorQuestionIcon name={phase === "recording" ? "stop" : "microphone"} color={colors.green} size={25} /></Pressable></View>
            </View>
        </View>}
        {error ? <Text accessibilityRole="alert" numberOfLines={3} style={[styles.error, { color: colors.text }]}>{error}</Text> : null}
        <Pressable accessibilityRole="button" accessibilityLabel={primaryLabel} disabled={busy || !estimate && !answer && !hasFood} onPress={() => { if (answer) { setAnswer(""); requestAnimationFrame(() => input.current?.focus()) } else void (estimate ? save() : calculate()) }} style={({ pressed }) => [styles.primary, { backgroundColor: colors.greenBright, opacity: busy || !estimate && !answer && !hasFood ? 0.55 : pressed ? 0.75 : 1 }]}>{phase === "calculating" || phase === "saving" ? <ActivityIndicator color="#FFFFFF" /> : null}<Text style={styles.primaryText}>{phase === "calculating" ? helpMode ? mt("Готовим ответ…") : mt("Считаем…") : phase === "saving" ? mt("Сохраняем…") : primaryLabel}</Text></Pressable>
        {estimate ? <Pressable accessibilityRole="button" accessibilityLabel={mt("Изменить описание")} disabled={busy} onPress={() => { setEstimate(null); setError(""); requestAnimationFrame(() => input.current?.focus()) }} style={styles.edit}><Text style={[styles.photoLabel, { color: colors.green }]}>{mt("Изменить описание")}</Text></Pressable> : null}
        {enteringFood && recent.length ? <View style={styles.recentSection}><Text style={[styles.foodName, { color: colors.text, fontSize: 22, fontWeight: "800" }]}>{mt("Добавляли раньше")}</Text><ScrollView testID="mentor-food-history" keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" style={styles.recentList} contentContainerStyle={styles.recentContent}>{recent.map(entry => <Pressable key={entry.id} accessibilityRole="button" accessibilityLabel={mt("Повторить {0}", [entry.data.name ?? ""])} disabled={busy} onPress={() => { setText(foodDescription(entry.data)); setRecipe(entry); setPhoto(null); setError(""); saveRequest.current = null; input.current?.focus() }} style={[styles.recent, { backgroundColor: recipe?.id === entry.id ? colors.soft : "transparent", borderBottomColor: colors.border }]}>{entry.photo_attachments?.[0] ? <MentorMealImage attachment={entry.photo_attachments[0]} style={styles.recentPhoto} /> : <MentorQuestionIcon name="food" size={27} color={colors.green} />}<View style={{ flex: 1, gap: 3 }}><Text numberOfLines={1} style={[styles.photoLabel, { color: colors.text }]}>{entry.data.name}</Text><Text numberOfLines={1} style={[styles.caption, { color: colors.muted }]}>{foodDescription(entry.data)}</Text></View><MentorQuestionIcon name="chevronRight" color={colors.muted} size={19} /></Pressable>)}</ScrollView></View> : null}

    </>
    return <View style={{ flex: 1, backgroundColor: colors.surface }}>
        <MentorHomeHeader title={title} onBack={close} />
        {enteringFood ? <View testID="mentor-food-editor" style={[styles.sheet, styles.fixedSheet]}>{content}</View> : <ScrollView testID="mentor-food-editor" keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" contentContainerStyle={styles.sheet} style={{ flex: 1 }}>{content}</ScrollView>}
    </View>
}

const styles = StyleSheet.create({
    fixedSheet: { flex: 1, minHeight: 0, paddingBottom: 0 },
    recentSection: { flex: 1, minHeight: 0, gap: 8 }, recentList: { flex: 1, minHeight: 0 }, recentContent: { paddingBottom: 20 },
    sheet: { paddingHorizontal: 20, paddingTop: 4, paddingBottom: 20, gap: 18 }, handle: { width: 36, height: 4, borderRadius: 2, alignSelf: "center", marginBottom: 2 },
    header: { flexDirection: "row", alignItems: "center", gap: 12 }, title: { flex: 1, fontSize: 25, lineHeight: 32, fontWeight: "800", letterSpacing: -0.5 }, close: { width: 42, height: 42, borderRadius: 21, justifyContent: "center", alignItems: "center" },
    composer: { borderRadius: 22, borderWidth: 1, paddingHorizontal: 17, paddingTop: 14 }, input: { fontWeight: "500", minHeight: 100, maxHeight: 180, padding: 0, fontSize: 18, lineHeight: 27 }, toolbar: { borderTopWidth: StyleSheet.hairlineWidth, marginTop: 12, paddingVertical: 9, flexDirection: "row", justifyContent: "space-between", alignItems: "center" }, photoButton: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: 9, paddingRight: 12 }, photoLabel: { fontSize: 17, lineHeight: 23, fontWeight: "600" }, voiceArea: { flexDirection: "row", gap: 10, alignItems: "center" }, microphone: { width: 46, height: 44, borderRadius: 15, alignItems: "center", justifyContent: "center" },
    photo: { width: 70, height: 70, marginTop: 12 }, thumbnail: { width: 64, height: 64, borderRadius: 12 }, remove: { position: "absolute", right: -4, top: -6, width: 30, height: 30, borderRadius: 15, justifyContent: "center", alignItems: "center" }, primary: { minHeight: 54, borderRadius: 17, paddingHorizontal: 16, paddingVertical: 15, alignItems: "center", justifyContent: "center", flexDirection: "row", gap: 10 }, primaryText: { fontSize: 17, lineHeight: 24, fontWeight: "700", color: "#FFFFFF" }, edit: { minHeight: 44, alignItems: "center", justifyContent: "center" }, error: { fontWeight: "500", fontSize: 14, lineHeight: 20 },
    waterResult: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", borderRadius: 15, padding: 15 }, recent: { flexDirection: "row", alignItems: "center", gap: 12, borderRadius: 17, padding: 12, minHeight: 66, borderBottomWidth: StyleSheet.hairlineWidth }, recentPhoto: { width: 54, height: 54, borderRadius: 12 }, answer: { padding: 20, borderRadius: 22 },
    result: { gap: 14, paddingTop: 2 }, foodName: { fontSize: 18, lineHeight: 26, fontWeight: "600" }, calories: { fontSize: 45, lineHeight: 54, fontWeight: "800", letterSpacing: -1 }, unit: { fontSize: 19, fontWeight: "600" }, macros: { flexDirection: "row" }, macro: { flex: 1, alignItems: "center", gap: 5 }, macroLabel: { fontWeight: "500", fontSize: 13, lineHeight: 18 }, macroValue: { fontSize: 20, lineHeight: 26, fontWeight: "700" }, caption: { fontWeight: "500", fontSize: 13, lineHeight: 19 },
})
