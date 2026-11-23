import { AppTimePicker } from "@/components/platform/app-date-time-picker"
import { mentorLocale } from "@/i18n/mentor-translations"
import { useTheme } from "@/providers/theme-provider"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
export function MentorReminderTime(props: { label: string; value: string; onChange: (value: string) => void; disabled: boolean }) {
    const colors = useMentorPalette(), { isDark } = useTheme()
    return <AppTimePicker {...props} locale={mentorLocale()} dark={isDark} colors={colors} />
}
