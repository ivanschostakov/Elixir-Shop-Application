import { useRef, useState } from "react"
import { ActivityIndicator, StyleSheet, Switch, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import type { useCompanion } from "@/screens/chat/companion"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import type { CompanionSettings, MobileReminders } from "@/services/api/companion"

const mobileDefaults: MobileReminders = {
    topics: ["nutrition", "meal_balance", "water", "photo", "post_water", "training", "energy", "rest", "unfinished", "reschedule", "program", "effort", "wellbeing", "bedtime", "sleep", "stress"],
    water_time: "15:00", workout_time: "18:00", wellbeing_time: "09:00", bedtime: "22:30", stress_time: "20:00",
    short_sleep_hours: 7, effort_delay: 30, water_portion: 250,
}

function hasReminderSchedule(settings: CompanionSettings) {
    return !!(settings.mobile?.topics?.length || settings.meal_reminders?.length || settings.course_reminders ||
        settings.supply_reminders || settings.daily_time || settings.weight_time || settings.weekly_time ||
        settings.checkin_time || settings.inactivity_days)
}

export function MentorNotificationSetting({ controller: c }: { controller: ReturnType<typeof useCompanion> }) {
    const colors = useMentorPalette()
    const [pending, setPending] = useState<boolean | null>(null)
    const locked = useRef(false)
    const profile = c.state?.profile
    if (!profile) return null
    const settings = profile.settings
    const configured = hasReminderSchedule(settings)
    const enabled = configured && !settings.notifications_paused
    const change = async (value: boolean) => {
        if (locked.current || c.busy || value === enabled) return
        locked.current = true
        setPending(value)
        try {
            await c.attempt(async () => {
                if (value) {
                    const { syncPushNotifications } = await import("@/services/notifications/order-status-notifications")
                    if (!await syncPushNotifications({ requestPermissions: true })) throw new Error(mt("Разрешите уведомления на телефоне или продолжите без напоминаний."))
                }
                await c.perform({ kind: "settings", expected_version: profile.version, settings: {
                    ...settings, notifications_paused: !value,
                    ...(value && !configured ? { mobile: { ...mobileDefaults, ...settings.mobile, topics: mobileDefaults.topics }, meal_reminders: ["breakfast", "lunch", "dinner"] } : {}),
                } })
            })
        } finally {
            locked.current = false
            setPending(null)
        }
    }
    const label = mt("Получать уведомления от наставника")
    return <View style={[styles.row, { borderColor: colors.border }]}>
        <Text style={[styles.label, { color: colors.text }]}>{label}</Text>
        {pending !== null ? <ActivityIndicator color={colors.green} /> : null}
        <Switch accessibilityLabel={label} disabled={pending !== null || c.busy} value={pending ?? enabled} onValueChange={value => void change(value)}
            trackColor={{ false: colors.border, true: colors.greenBright }} thumbColor="#FFFFFF" ios_backgroundColor={colors.border} />
    </View>
}

const styles = StyleSheet.create({
    row: { minHeight: 68, flexDirection: "row", alignItems: "center", borderWidth: 1, borderRadius: 18, gap: 12, paddingHorizontal: 16, paddingVertical: 12 },
    label: { flex: 1, fontSize: 16, lineHeight: 22, fontWeight: "600" },
})
