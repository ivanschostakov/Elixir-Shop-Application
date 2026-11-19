// Isolated synthetic native preview. Uses production screens and no real account.
import React, { useState } from "react"
import { registerRootComponent } from "expo"
import { NativeModules, View } from "react-native"
import { SafeAreaProvider } from "react-native-safe-area-context"
import { MentorOnboarding } from "@/screens/chat/mentor-onboarding"
import { MentorOptionalOnboarding } from "@/screens/chat/mentor-onboarding-optional"
import { MentorNutritionResult } from "@/screens/chat/mentor-nutrition-result"
import { MentorDevelopmentNotice } from "@/screens/chat/mentor-development-notice"
import { mentorFormFromState, mentorOptionalFormFromState } from "@/screens/chat/mentor-onboarding-data"
import { lightColors } from "@/theme/colors"
import { translate } from "@/i18n/translations"

export const useTheme = () => ({ palette: lightColors, isDark: false, themeName: "light" })
export const useLanguage = () => ({ language: "ru", t: key => translate(key, "ru") })
export const requestKey = () => "synthetic-preview-key"
export const syncPushNotifications = async () => "synthetic-notification-token"
const saved = { available: true, consent_required: false, profile: { id: 1, version: 1, data: { goal: "weight_loss", age: 32, sex: "female", height_cm: "170", activity: "moderate", nutrition: { kcal: "1900", protein: "130", fat: "60", carbs: "210" } } }, mentor: { latest_weight: { data: { weight_kg: "78.5" } } } }

function Preview() {
    const source = NativeModules.SourceCode?.getConstants?.().scriptURL ?? ""
    const [screen, setScreen] = useState(globalThis.__MENTOR_PREVIEW_SCREEN__ ?? new URL(source || "http://127.0.0.1").searchParams.get("previewScreen") ?? "required")
    const [form, setForm] = useState(mentorFormFromState(saved))
    const [optional, setOptional] = useState({ ...mentorOptionalFormFromState(saved), weightEnabled: true, dailyEnabled: true })
    const [step, setStep] = useState(screen === "reminders" ? 5 : 0)
    const close = () => setScreen("placeholder")
    const content = screen === "result" ? <MentorNutritionResult state={saved} onContinue={() => { setScreen("optional"); setStep(0) }} onDecline={close} onBack={() => setScreen("required")} onClose={close} /> : screen === "optional" || screen === "reminders" ? <MentorOptionalOnboarding value={optional} onChange={setOptional} step={step} onBack={() => step ? setStep(step - 1) : setScreen("result")} onClose={close} onNext={() => step === 5 ? close() : setStep(step + 1)} saving={false} error="" /> : screen === "placeholder" ? <MentorDevelopmentNotice onChat={() => setScreen("required")} onContinue={() => { setScreen("optional"); setStep(0) }} /> : undefined
    return <SafeAreaProvider><View style={{ flex: 1, backgroundColor: "white" }}><MentorOnboarding visible value={form} onChange={setForm} onClose={close} onSave={async () => setScreen("result")} saving={false} error="">{content}</MentorOnboarding></View></SafeAreaProvider>
}
registerRootComponent(Preview)
