import { View } from "react-native"
import Armchair from "@/assets/icons/mentor/armchair.svg"
import Footprints from "@/assets/icons/mentor/footprints.svg"
import Bike from "@/assets/icons/mentor/bike.svg"
import Dumbbell from "@/assets/icons/mentor/dumbbell.svg"
import Sprout from "@/assets/icons/mentor/sprout.svg"
import CalendarClock from "@/assets/icons/mentor/calendar-clock.svg"
import CalendarCheck from "@/assets/icons/mentor/calendar-check.svg"
import House from "@/assets/icons/mentor/house.svg"
import ArrowLeftRight from "@/assets/icons/mentor/arrow-left-right.svg"
import PencilLine from "@/assets/icons/mentor/pencil-line.svg"
import Weight from "@/assets/icons/mentor/weight.svg"
import ClipboardCheck from "@/assets/icons/mentor/clipboard-check.svg"
import CalendarDays from "@/assets/icons/mentor/calendar-days.svg"
import ChevronDown from "@/assets/icons/mentor/chevron-down.svg"
import ChevronLeft from "@/assets/icons/mentor/chevron-left.svg"
import Close from "@/assets/icons/mentor/x.svg"
import Utensils from "@/assets/icons/mentor/utensils.svg"
import Leaf from "@/assets/icons/mentor/leaf.svg"
import TrendingDown from "@/assets/icons/mentor/trending-down.svg"
import TrendingUp from "@/assets/icons/mentor/trending-up.svg"
import HeartPulse from "@/assets/icons/mentor/heart-pulse.svg"

const icons = { sedentary: Armchair, light: Footprints, moderate: Bike, high: Dumbbell, beginner: Sprout, occasional: CalendarClock, regular: CalendarCheck, home: House, gym: Dumbbell, mixed: ArrowLeftRight, custom: PencilLine, weight: Weight, summary: ClipboardCheck, weekly: CalendarDays, chevronDown: ChevronDown, back: ChevronLeft, close: Close, food: Utensils, leaf: Leaf, loss: TrendingDown, gain: TrendingUp, maintain: HeartPulse }
export type MentorQuestionIconName = keyof typeof icons

export function MentorQuestionIcon({ name, size = 26, color }: { name: MentorQuestionIconName; size?: number; color: string }) {
    const Icon = icons[name]
    return <View style={{ width: size, height: size, flexShrink: 0 }}><Icon width={size} height={size} stroke={color} color={color} strokeWidth={1.7} accessible={false} /></View>
}
