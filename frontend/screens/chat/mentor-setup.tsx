import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import type { useCompanion } from "@/screens/chat/companion"
import { CompanionActionCancelled } from "@/screens/chat/companion-consent"
import { MentorDevelopmentNotice } from "@/screens/chat/mentor-development-notice"
import { MentorOnboarding } from "@/screens/chat/mentor-onboarding"
import { mentorFormFromState, mentorOnboardingAction, mentorProfileComplete, type MentorForm } from "@/screens/chat/mentor-onboarding-data"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { requestKey, type CompanionAction } from "@/services/api/companion"
import { getErrorMessage } from "@/utils/errors"

type Controller = ReturnType<typeof useCompanion>

export function MentorSetup({ controller: c, onClose }: { controller: Controller; onClose: () => void }) {
    useLanguage()
    const colors = useMentorPalette()
    const [view, setView] = useState<"form" | "placeholder">(() => mentorProfileComplete(c.state) ? "placeholder" : "form")
    const [form, setForm] = useState<MentorForm>(() => mentorFormFromState(c.state))
    const initializedProfile = useRef(!!c.state?.profile)
    const [error, setError] = useState("")
    const [saving, setSaving] = useState(false)
    const active = useRef(true)
    const savingRef = useRef(false)
    const submission = useRef<CompanionAction | null>(null)
    useEffect(() => { active.current = true; return () => { active.current = false } }, [])

    useEffect(() => {
        if (initializedProfile.current || !c.state?.profile) return
        initializedProfile.current = true
        setForm(mentorFormFromState(c.state))
        setView(mentorProfileComplete(c.state) ? "placeholder" : "form")
    }, [c.state])
    const change = (next: MentorForm) => { submission.current = null; setError(""); setForm(next) }
    const save = async () => {
        if (savingRef.current || !c.state) return
        savingRef.current = true; setSaving(true); setError("")
        try {
            const action = submission.current ?? mentorOnboardingAction(form, c.state, requestKey())
            submission.current = action
            await c.perform(action)
            if (active.current) setView("placeholder")
        } catch (e) {
            if (active.current && !(e instanceof CompanionActionCancelled)) {
                setError(getErrorMessage(e))
                const state = await c.refresh()
                if (state?.profile && state.profile.version !== submission.current?.expected_version) submission.current = null
            }
        } finally {
            savingRef.current = false
            if (active.current) setSaving(false)
        }
    }

    const ready = !!c.state?.available && !!c.state.profile && initializedProfile.current
    const loading = !c.initialized || !!c.state?.profile && !initializedProfile.current
    const content = ready ? view === "placeholder" ? <MentorDevelopmentNotice onChat={onClose} /> : undefined :
    <View testID="mentor-setup" style={[styles.container, { backgroundColor: colors.surface }]}>
        {loading ? <ActivityIndicator color={colors.greenBright} /> : <>
            <Text accessibilityRole="alert" style={[styles.error, { color: colors.muted }]}>{c.error || mt("Наставник временно недоступен. Попробуйте ещё раз.")}</Text>
            <Pressable accessibilityRole="button" onPress={() => void c.refresh()} style={[styles.button, { backgroundColor: colors.greenBright }]}><Text style={styles.buttonText}>{mt("Обновить")}</Text></Pressable>
        </>}
        <Pressable accessibilityRole="button" onPress={onClose} style={styles.back}><Text style={{ color: colors.green }}>{mt("Назад")}</Text></Pressable>
    </View>
    return <MentorOnboarding visible value={form} onChange={change} onClose={onClose} onSave={save} saving={saving} error={error}>{content}</MentorOnboarding>
}

const styles = StyleSheet.create({
    container: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 24, gap: 20 },
    button: { minHeight: 54, borderRadius: 17, paddingVertical: 15, paddingHorizontal: 28, alignItems: "center", justifyContent: "center" },
    buttonText: { color: "#FFFFFF", fontSize: 17, fontWeight: "600" }, back: { minHeight: 44, justifyContent: "center", paddingHorizontal: 20 },
    error: { fontSize: 16, textAlign: "center" },
})
