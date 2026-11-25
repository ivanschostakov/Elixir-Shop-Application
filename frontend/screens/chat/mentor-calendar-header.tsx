import { Pressable, Text, View } from "react-native"
import type { CalendarHeaderProps } from "react-native-calendars/src/calendar/header"
import { useLanguage } from "@/providers/language-provider"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"

const months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
const weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

// Both callers use firstDay=1. Do not read or change the calendar library's shared XDate locale.
export function MentorCalendarHeader({ month, addMonth, disableArrowLeft, disableArrowRight, theme }: CalendarHeaderProps) {
    const { language } = useLanguage()
    const arrow = (next: boolean) => {
        const disabled = next ? disableArrowRight : disableArrowLeft
        return <Pressable accessibilityRole="button" accessibilityLabel={mt(next ? "Следующий месяц" : "Предыдущий месяц", [], language)}
            disabled={disabled} accessibilityState={{ disabled }} onPress={() => addMonth?.(next ? 1 : -1)}
            style={{ minWidth: 48, minHeight: 48, alignItems: "center", justifyContent: "center", opacity: disabled ? 0.35 : 1 }}>
            <MentorQuestionIcon name={next ? "chevronRight" : "back"} size={22} color={theme?.arrowColor ?? theme?.monthTextColor ?? "#206647"} />
        </Pressable>
    }
    return <View>
        <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
            {arrow(false)}
            <Text accessibilityRole="header" style={{ color: theme?.monthTextColor, fontSize: theme?.textMonthFontSize ?? 18, fontWeight: "700" }}>
                {month && mt(months[month.getMonth()], [], language) + " " + month.getFullYear()}
            </Text>
            {arrow(true)}
        </View>
        <View style={{ flexDirection: "row", minHeight: 24, alignItems: "center" }}>
            {weekdays.map(day => <Text key={day} style={{ flex: 1, textAlign: "center", color: theme?.textSectionTitleColor, fontSize: theme?.textDayHeaderFontSize ?? 12 }}>{mt(day, [], language)}</Text>)}
        </View>
    </View>
}
