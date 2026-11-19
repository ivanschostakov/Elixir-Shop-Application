import { useEffect, useRef, useState } from "react"
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import type { useCompanion } from "@/screens/chat/companion"
import { CompanionActionCancelled } from "@/screens/chat/companion-consent"
import { MentorDevelopmentNotice } from "@/screens/chat/mentor-development-notice"
import { MentorOnboarding } from "@/screens/chat/mentor-onboarding"
import { mentorFormFromState, mentorOnboardingAction, mentorOptionalAction, mentorOptionalFormFromState, mentorOptionalResumeStep, mentorProfileComplete, type MentorForm, type MentorOptionalForm } from "@/screens/chat/mentor-onboarding-data"
import { MentorOptionalOnboarding } from "@/screens/chat/mentor-onboarding-optional"
import { MentorNutritionResult } from "@/screens/chat/mentor-nutrition-result"
import { MentorStageTransition } from "@/screens/chat/mentor-onboarding-layout"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { requestKey, type CompanionAction, type CompanionState } from "@/services/api/companion"
import { syncPushNotifications } from "@/services/notifications/order-status-notifications"
import { getErrorMessage } from "@/utils/errors"

type Controller = ReturnType<typeof useCompanion>

export function MentorSetup({ controller: c, onClose }: { controller: Controller; onClose: () => void }) {
    useLanguage()
    const colors = useMentorPalette()
    const [view, setView] = useState<"form" | "nutrition" | "optional" | "placeholder">(() => mentorProfileComplete(c.state) ? "placeholder" : "form")
    const [form, setForm] = useState<MentorForm>(() => mentorFormFromState(c.state))
    const [optional, setOptional] = useState<MentorOptionalForm>(() => mentorOptionalFormFromState(c.state))
    const [optionalStep, setOptionalStep] = useState(() => mentorOptionalResumeStep(c.state))
    const [savedState, setSavedState] = useState<CompanionState | null>(null)
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
        setOptional(mentorOptionalFormFromState(c.state))
        setOptionalStep(mentorOptionalResumeStep(c.state))
        setView(mentorProfileComplete(c.state) ? "placeholder" : "form")
    }, [c.state])
    const change = (next: MentorForm) => { submission.current = null; setError(""); setForm(next) }
    const changeOptional = (next: MentorOptionalForm) => { submission.current = null; setError(""); setOptional(next) }
    const currentState = savedState && savedState.profile?.id === c.state?.profile?.id && (savedState.profile?.version ?? 0) >= (c.state?.profile?.version ?? 0) ? savedState : c.state
    const submit = async (build: () => CompanionAction | Promise<CompanionAction>, success: (state: CompanionState) => void) => {
        if (savingRef.current || !c.state) return
        savingRef.current = true; setSaving(true); setError("")
        try {
            const action = submission.current ?? await build()
            submission.current = action
            const saved = await c.perform(action)
            if (active.current) {
                const next = saved ?? c.state
                setSavedState(next); submission.current = null; success(next)
            }
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
    const save = () => submit(() => mentorOnboardingAction(form, c.state!, requestKey()), () => setView("nutrition"))
    const openOptional = () => {
        if (savingRef.current) return
        submission.current = null; setError("")
        setOptional(mentorOptionalFormFromState(currentState))
        setOptionalStep(mentorOptionalResumeStep(currentState)); setView("optional")
    }
    const saveOptional = (skipped: boolean) => {
        void submit(async () => {
            const action = mentorOptionalAction(optional, optionalStep, skipped, c.state!, requestKey())
            if (optionalStep === 5 && !skipped && (optional.weightEnabled || optional.dailyEnabled || optional.weeklyEnabled)) {
                const token = await syncPushNotifications({ requestPermissions: true })
                if (!token) throw new Error(mt("Разрешите уведомления на телефоне или продолжите без напоминаний."))
            }
            return action
        }, saved => {
            if (optionalStep === 5) setView("placeholder")
            else setOptionalStep(mentorOptionalResumeStep(saved, optionalStep + 1))
        })
    }
    const close = () => { if (!savingRef.current) onClose() }
    const stage = readyContent()

    function readyContent() {
        if (view === "placeholder") return <MentorDevelopmentNotice onChat={close} onContinue={openOptional} />
        if (view === "nutrition") return <MentorNutritionResult state={currentState} onContinue={openOptional} onDecline={() => setView("placeholder")} onBack={() => { submission.current = null; setView("form") }} onClose={close} />
        if (view === "optional") return <MentorOptionalOnboarding value={optional} onChange={changeOptional} step={optionalStep} onBack={() => { submission.current = null; setError(""); if (optionalStep) setOptionalStep(optionalStep - 1); else setView("nutrition") }} onClose={close} onNext={saveOptional} saving={saving} error={error} />
        return undefined
    }

    const ready = !!c.state?.available && !!c.state.profile && initializedProfile.current
    const loading = !c.initialized || !!c.state?.profile && !initializedProfile.current
    const content = ready ? stage ? <MentorStageTransition key={view}>{stage}</MentorStageTransition> : undefined :
    <View testID="mentor-setup" style={[styles.container, { backgroundColor: colors.surface }]}>
        {loading ? <ActivityIndicator color={colors.greenBright} /> : <>
            <Text accessibilityRole="alert" style={[styles.error, { color: colors.muted }]}>{c.error || mt("Наставник временно недоступен. Попробуйте ещё раз.")}</Text>
            <Pressable accessibilityRole="button" onPress={() => void c.refresh()} style={[styles.button, { backgroundColor: colors.greenBright }]}><Text style={styles.buttonText}>{mt("Обновить")}</Text></Pressable>
        </>}
        <Pressable accessibilityRole="button" onPress={close} style={styles.back}><Text style={{ color: colors.green }}>{mt("Назад")}</Text></Pressable>
    </View>
    return <MentorOnboarding visible value={form} onChange={change} onClose={close} onSave={save} saving={saving} error={error}>{content}</MentorOnboarding>
}

const styles = StyleSheet.create({
    container: { flex: 1, alignItems: "center", justifyContent: "center", paddingHorizontal: 24, gap: 20 },
    button: { minHeight: 54, borderRadius: 17, paddingVertical: 15, paddingHorizontal: 28, alignItems: "center", justifyContent: "center" },
    buttonText: { color: "#FFFFFF", fontSize: 17, fontWeight: "600" }, back: { minHeight: 44, justifyContent: "center", paddingHorizontal: 20 },
    error: { fontSize: 16, textAlign: "center" },
})
