// Offline simulator fixture. Production routes never import this entry point.
import React, { useRef, useState } from "react"
import { registerRootComponent } from "expo"
import { Modal, Settings, View } from "react-native"
import { SafeAreaProvider, useSafeAreaInsets } from "react-native-safe-area-context"
import { AppFormLayout } from "@/components/platform/app-form-layout"
import { MentorWellbeingScreen } from "@/screens/chat/mentor-wellbeing"
import { MentorWeightEditor } from "@/screens/chat/mentor-weight-editor"
import { MentorWellbeingEditor } from "@/screens/chat/mentor-wellbeing-form"
import { MentorBottomNavigation } from "@/screens/chat/mentor-navigation"
import { calendarDate, deviceClockKey } from "@/screens/chat/companion-timezones"
import { lightColors } from "@/theme/colors"
import { setTranslationLanguage, translate } from "@/i18n/translations"

setTranslationLanguage("ru")
export const useTheme = () => ({ palette: lightColors, accentPalette: lightColors, isDark: false, themeName: "light" })
export const useLanguage = () => ({ language: "ru", t: key => translate(key, "ru") })
export const getErrorMessage = error => error.message
export const requestKey = () => `preview-${Date.now()}-${Math.random()}`
const day = calendarDate(-1)
let entries = [{ id: 1, version: 1, kind: "wellbeing", occurred_at: new Date(`${day}T12:00:00`).toISOString(), data: { kind: "wellbeing", occurred_at: new Date(`${day}T12:00:00`).toISOString(), wellbeing: 4, energy: 4, mood: 2, stress: 2, sleep_hours: 7.5, sleep_quality: 3, appetite: 3, note: "После прогулки было больше энергии." } }]
const weights = [1, 3].map((days, index) => {
    const at = new Date(calendarDate(-days) + "T08:30:00").toISOString()
    return { id: 2 + index, version: 1, kind: "weight", occurred_at: at, data: { kind: "weight", occurred_at: at, weight_kg: 78.5 + index / 10 } }
})
entries.push(...weights)
export const getCompanionEntries = async (from, to, kind) => ({ entries: entries.filter(entry => { const date = calendarDateFor(entry.occurred_at); return (!kind || entry.kind === kind) && date >= from && date < to }) })
function calendarDateFor(value) { const date = new Date(value); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}` }

function Preview() {
    const { top } = useSafeAreaInsets()
    const [state, setState] = useState({ available: true, entries, mentor: { latest_weight: weights[0] } })
    const [editor, setEditor] = useState(() => Settings.get("previewEditor") === "weight" ? { page: "weight" } : null)
    const [wellbeingRevision, setWellbeingRevision] = useState(0)
    const lastEditor = useRef(null)
    if (editor) lastEditor.current = editor
    const controller = { state, editor: editor ?? lastEditor.current, clock: deviceClockKey(), wellbeingRevision, busy: false, error: "", setError() {}, setEditor,
        async perform(action) {
            const previous = entries.find(item => item.id === action.resource_id)
            const entry = { id: previous?.id ?? Date.now(), version: (previous?.version ?? 0) + 1, kind: action.entry.kind, occurred_at: action.entry.occurred_at, data: action.entry }
            entries = [...entries.filter(item => item.id !== entry.id), entry]
            const next = { ...state, entries, mentor: { latest_weight: entry.kind === "weight" ? entry : state.mentor.latest_weight } }
            setState(next); setWellbeingRevision(value => value + 1)
            return next
        },
    }
    return <View style={{ flex: 1, backgroundColor: "#FFF" }}>
        <View style={{ flex: 1, paddingTop: top }}><MentorWellbeingScreen controller={controller} active onClose={() => {}} onSettings={() => {}} /></View>
        <MentorBottomNavigation active="wellbeing" onSelect={() => {}} />
        <Modal visible={!!editor} presentationStyle="fullScreen" animationType="slide" onRequestClose={() => setEditor(null)}>
            <AppFormLayout androidBehavior={null} style={{ flex: 1, backgroundColor: "#FFF" }}>
                {lastEditor.current?.page === "weight" ? <MentorWeightEditor controller={controller} onClose={() => setEditor(null)} onSaved={() => setEditor(null)} /> : lastEditor.current ? <MentorWellbeingEditor key={JSON.stringify(lastEditor.current)} controller={controller} onClose={() => setEditor(null)} /> : null}
            </AppFormLayout>
        </Modal>
    </View>
}

registerRootComponent(() => <SafeAreaProvider><Preview /></SafeAreaProvider>)
