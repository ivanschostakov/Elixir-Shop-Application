import { mentorText as mt } from "@/i18n/mentor-translations"
import type { CompanionAction, CompanionState } from "@/services/api/companion"

export type MentorForm = {
    goal: "weight_loss" | "weight_gain" | "maintain" | "custom" | null
    customGoal: string
    age: string
    sex: "male" | "female" | null
    height: string
    weight: string
    activity: "low" | "light" | "moderate" | "high" | null
}

const goals = ["weight_loss", "weight_gain", "maintain", "custom"]
const activities = ["low", "light", "moderate", "high"]
const numeric = (value: string) => /^\d+(?:[.,]\d+)?$/.test(value.trim()) ? Number(value.replace(",", ".")) : NaN

export function mentorFormFromState(state: CompanionState | null): MentorForm {
    const profile = state?.profile?.data
    return {
        goal: profile?.goal && goals.includes(profile.goal) ? profile.goal as MentorForm["goal"] : null,
        customGoal: profile?.custom_goal ?? "",
        age: profile?.age == null ? "" : String(profile.age),
        sex: profile?.sex ?? null,
        height: profile?.height_cm == null ? "" : String(profile.height_cm),
        weight: state?.mentor?.latest_weight?.data.weight_kg == null ? "" : String(state.mentor.latest_weight.data.weight_kg),
        activity: profile?.activity ?? null,
    }
}

export function mentorStepError(form: MentorForm, step: number): string {
    if (step === 0) {
        if (!form.goal || !goals.includes(form.goal)) return mt("Выберите цель.")
        if (form.goal === "custom" && !form.customGoal.trim()) return mt("Расскажите о своей цели.")
    } else if (step === 1) {
        const age = numeric(form.age)
        if (!Number.isInteger(age) || age < 18 || age > 120) return mt("Укажите возраст от 18 до 120 полных лет.")
        if (form.sex !== "male" && form.sex !== "female") return mt("Выберите пол.")
    } else if (step === 2) {
        const height = numeric(form.height), weight = numeric(form.weight)
        if (!Number.isFinite(height) || height < 50 || height > 260) return mt("Укажите рост от 50 до 260 см.")
        if (!Number.isFinite(weight) || weight <= 0 || weight > 500) return mt("Укажите текущий вес больше 0 и не больше 500 кг.")
    } else if (!form.activity || !activities.includes(form.activity)) return mt("Выберите уровень активности.")
    return ""
}

export function mentorProfileComplete(state: CompanionState | null): boolean {
    if (!state?.profile || state.consent_required) return false
    const form = mentorFormFromState(state)
    return [0, 1, 2, 3].every(step => !mentorStepError(form, step))
}

export function mentorOnboardingAction(form: MentorForm, state: CompanionState, requestKey: string): CompanionAction {
    for (const step of [0, 1, 2, 3]) {
        const error = mentorStepError(form, step)
        if (error) throw new Error(error)
    }
    return {
        kind: "onboard", expected_version: state.profile?.version, request_key: requestKey,
        onboarding: {
            goal: form.goal!, custom_goal: form.goal === "custom" ? form.customGoal.trim() : "",
            age: numeric(form.age), sex: form.sex!, height_cm: numeric(form.height),
            current_weight_kg: numeric(form.weight), activity: form.activity!,
        },
    }
}
