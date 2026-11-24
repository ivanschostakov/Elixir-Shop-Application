import { mentorText as mt } from "@/i18n/mentor-translations"
import type { CompanionAction, CompanionSettings, CompanionState } from "@/services/api/companion"

export type MentorForm = {
    goal: "weight_loss" | "weight_gain" | "maintain" | "custom" | null
    customGoal: string
    age: string
    sex: "male" | "female" | null
    height: string
    weight: string
    targetWeight: string
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
        targetWeight: profile?.target_weight_kg == null ? "" : String(profile.target_weight_kg),
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
    } else if (step === 3) {
        if (!form.activity || !activities.includes(form.activity)) return mt("Выберите уровень активности.")
    } else {
        const target = numeric(form.targetWeight)
        if (!Number.isFinite(target) || target <= 0 || target > 500) return mt("Укажите желаемый вес больше 0 и не больше 500 кг.")
        if (form.goal === "weight_loss" && target >= numeric(form.weight)) return mt("Желаемый вес должен быть ниже текущего.")
        if (form.goal === "weight_gain" && target <= numeric(form.weight)) return mt("Желаемый вес должен быть выше текущего.")
    }
    return ""
}

export function mentorProfileComplete(state: CompanionState | null): boolean {
    if (!state?.profile || state.consent_required) return false
    const form = mentorFormFromState(state)
    // Later weigh-ins can meet or pass the original goal without invalidating the profile.
    const target = numeric(form.targetWeight)
    return [0, 1, 2, 3].every(step => !mentorStepError(form, step)) && target > 0 && target <= 500
}

export function mentorOnboardingAction(form: MentorForm, state: CompanionState, requestKey: string): CompanionAction {
    for (const step of [0, 1, 2, 3, 4]) {
        const error = mentorStepError(form, step)
        if (error) throw new Error(error)
    }
    return {
        kind: "onboard", expected_version: state.profile?.version, request_key: requestKey,
        onboarding: {
            goal: form.goal!, custom_goal: form.goal === "custom" ? form.customGoal.trim() : "",
            age: numeric(form.age), sex: form.sex!, height_cm: numeric(form.height),
            current_weight_kg: numeric(form.weight), activity: form.activity!,
            target_weight_kg: numeric(form.targetWeight),
        },
    }
}

export const optionalMentorFields = ["lifestyle", "preferences", "restrictions", "training_experience", "training_conditions"] as const
export type OptionalMentorField = typeof optionalMentorFields[number]
export type MentorExperienceChoice = "beginner" | "occasional" | "regular" | "custom"
export type MentorConditionsChoice = "home" | "gym" | "mixed" | "custom"
const experiencePresets = { beginner: "Начинаю", occasional: "Иногда", regular: "Регулярно" } as const
const conditionsPresets = { home: "Дома", gym: "В зале", mixed: "Дома и в зале" } as const
export type MentorOptionalForm = Record<OptionalMentorField, string> & {
    weightEnabled: boolean; weightTime: string; dailyEnabled: boolean; dailyTime: string
    weeklyEnabled: boolean; weeklyTime: string
    experienceChoice: MentorExperienceChoice | null; experienceCustom: string
    conditionsChoice: MentorConditionsChoice | null; conditionsCustom: string
}

function savedChoice<T extends string>(text: string, presets: Record<T, string>): T | "custom" | null {
    if (!text.trim()) return null
    for (const choice of Object.keys(presets) as T[]) {
        if ((["ru", "en", "kz"] as const).some(language => mt(presets[choice], [], language) === text)) return choice
    }
    return "custom"
}

export function mentorOptionalFormFromState(state: CompanionState | null): MentorOptionalForm {
    const data = state?.profile?.data, settings = state?.profile?.settings
    const experienceChoice = savedChoice(data?.training_experience ?? "", experiencePresets)
    const conditionsChoice = savedChoice(data?.training_conditions ?? "", conditionsPresets)
    return {
        lifestyle: data?.lifestyle ?? "", preferences: data?.preferences ?? "", restrictions: data?.restrictions ?? "",
        training_experience: data?.training_experience ?? "", training_conditions: data?.training_conditions ?? "",
        weightEnabled: !!settings?.weight_time, weightTime: settings?.weight_time?.slice(0, 5) ?? "08:00",
        dailyEnabled: !!settings?.daily_time, dailyTime: settings?.daily_time?.slice(0, 5) ?? "21:00",
        weeklyEnabled: !!settings?.weekly_time, weeklyTime: settings?.weekly_time?.slice(0, 5) ?? "08:00",
        experienceChoice, experienceCustom: experienceChoice === "custom" ? data?.training_experience ?? "" : "",
        conditionsChoice, conditionsCustom: conditionsChoice === "custom" ? data?.training_conditions ?? "" : "",
    }
}

export function mentorOptionalResumeStep(state: CompanionState | null, minimum = 0): number {
    const profile = state?.profile?.data
    const saved = profile?.onboarding_optional_step ?? 0
    if (saved >= 6 && minimum === 0) return 0
    let step = Math.max(minimum, saved)
    while (step < 5 && profile?.[optionalMentorFields[step]]?.trim()) step++
    return Math.min(5, step)
}

export function mentorOptionalError(form: MentorOptionalForm, step: number): string {
    if (step === 3 || step === 4) {
        const choice = step === 3 ? form.experienceChoice : form.conditionsChoice
        const custom = step === 3 ? form.experienceCustom : form.conditionsCustom
        if (!choice) return mt("Выберите вариант или пропустите шаг.")
        if (choice === "custom" && !custom.trim()) return mt("Опишите свой вариант или пропустите шаг.")
    }
    if (step !== 5) return ""
    const validTime = (time: string) => /^([01]\d|2[0-3]):[0-5]\d$/.test(time)
    if ((form.weightEnabled && !validTime(form.weightTime)) || (form.dailyEnabled && !validTime(form.dailyTime)) || (form.weeklyEnabled && !validTime(form.weeklyTime))) return mt("Укажите время напоминаний.")
    return ""
}

export function mentorOptionalAction(form: MentorOptionalForm, step: number, skipped: boolean, state: CompanionState, key: string): CompanionAction {
    const error = skipped ? "" : mentorOptionalError(form, step)
    if (error) throw new Error(error)
    const action: CompanionAction = { kind: "onboarding_details", expected_version: state.profile?.version, request_key: key, onboarding_details: { next_step: step + 1 } }
    if (step < 5 && !skipped) {
        let text = form[optionalMentorFields[step]].trim()
        if (step === 3) text = form.experienceChoice === "custom" ? form.experienceCustom.trim() : mt(experiencePresets[form.experienceChoice as keyof typeof experiencePresets])
        if (step === 4) text = form.conditionsChoice === "custom" ? form.conditionsCustom.trim() : mt(conditionsPresets[form.conditionsChoice as keyof typeof conditionsPresets])
        action.onboarding_details![optionalMentorFields[step]] = text
    }
    if (step === 5) {
        const settings: CompanionSettings = {
            timezone: "UTC", nutrition_auto_eligible: false, course_reminders: false, daily_time: null, weight_time: null,
            weekly_time: null, weekly_day: 0, supply_reminders: false, supply_days: 7, ...state.profile?.settings,
        }
        action.settings = { ...settings,
            weight_time: !skipped && form.weightEnabled ? form.weightTime : null,
            daily_time: !skipped && form.dailyEnabled ? form.dailyTime : null,
            weekly_time: !skipped && form.weeklyEnabled ? form.weeklyTime : null, weekly_day: 0,
        }
    }
    return action
}
