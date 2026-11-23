// Offline visual fixture. The production entry point never imports this file.
import React, { useState } from "react"
import { registerRootComponent } from "expo"
import { View } from "react-native"
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context"
import { MentorTrainingScreen } from "@/screens/chat/mentor-training"
import { MentorBottomNavigation } from "@/screens/chat/mentor-navigation"
import { calendarDate, deviceClockKey } from "@/screens/chat/companion-timezones"
import { lightColors } from "@/theme/colors"
import { setTranslationLanguage, translate } from "@/i18n/translations"
setTranslationLanguage("ru")
export const useTheme = () => ({ palette: lightColors, accentPalette: lightColors, isDark: false, themeName: "light" })
export const useLanguage = () => ({ language: "ru", t: key => translate(key, "ru") })
export const getErrorMessage = error => error.message
export const requestKey = () => `preview-${Date.now()}-${Math.random()}`
let entries = []
export const getCompanionEntries = async () => ({ entries })
export const getWorkoutLibrary = async () => ({ entries, may_have_more: false })
export const requestWorkoutDraft = async request => ({ plan: request.current_plan ?? { name: "Силовая программа", start_date: calendarDate(), end_date: null, days: (request.setup?.weekdays ?? [(new Date().getDay() + 6) % 7]).map((weekday, index) => ({ key: `day-${index}`, name: index % 2 ? "Ноги и плечи" : "Грудь и спина", weekdays: [weekday], duration_minutes: request.setup?.minutes ?? 45, exercises: [{ key: "bench", name: "Жим гантелей лёжа", sets: 3, target_reps: 8, target_reps_max: 12, target_weight_kg: null, rest_seconds: 90 }, { key: "row", name: "Тяга верхнего блока", sets: 3, target_reps: 10, target_reps_max: 12, target_weight_kg: null, rest_seconds: 60 }, { key: "fly", name: "Разведение гантелей", sets: 3, target_reps: 12, target_reps_max: 15, target_weight_kg: null, rest_seconds: 60 }] })) }, message: "Проверьте программу", questions: [] })
function Preview() {
    const { top } = useSafeAreaInsets()
    const [state, setState] = useState({ available: true, entries, profile: { id: 1, version: 1, enabled: true, data: {}, settings: { timezone: "Europe/Moscow" } } })
    const c = { state, clock: deviceClockKey(), busy: false, async perform(action) {
        let next = state
        if (action.kind === "workout_plan") next = { ...state, profile: { ...state.profile, version: state.profile.version + 1, data: { workout_plan: action.workout_plan } } }
        else {
            const previous = entries.find(entry => entry.id === action.resource_id)
            const row = { id: previous?.id ?? Date.now(), version: (previous?.version ?? 0) + 1, kind: "workout", occurred_at: action.entry.occurred_at, data: action.entry }
            entries = [...entries.filter(entry => entry.id !== row.id), row]; next = { ...state, entries }
        }
        setState(next); return next
    } }
    return <View style={{ flex: 1, backgroundColor: "#FFF" }}><View style={{ flex: 1, paddingTop: top }}><MentorTrainingScreen controller={c} active onClose={() => {}} onSettings={() => {}} /></View><MentorBottomNavigation active="workouts" onSelect={() => {}} /></View>
}
registerRootComponent(() => <SafeAreaProvider><Preview /></SafeAreaProvider>)
