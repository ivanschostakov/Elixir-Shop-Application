import { shiftCalendarDay } from "@/screens/chat/companion-timezones"

export type ReviewRange = { start: string; end: string }
export const recentReviewRange = (today: string, days: 1 | 7 | 30): ReviewRange => ({ start: shiftCalendarDay(today, 1 - days), end: today })
export const lastReviewDay = (start: string) => shiftCalendarDay(start, 89)
export const exclusiveReviewEnd = (range: ReviewRange) => shiftCalendarDay(range.end, 1)

export function selectReviewDay(range: ReviewRange, field: keyof ReviewRange, day: string): ReviewRange {
    if (field === "end") return day < range.start || day > lastReviewDay(range.start) ? range : { ...range, end: day }
    return { start: day, end: range.end < day || range.end > lastReviewDay(day) ? day : range.end }
}
