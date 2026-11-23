import Svg, { Circle, Path, Rect } from "react-native-svg"
import { MentorSolidIcon, type MentorSolidIconName } from "@/screens/chat/mentor-icons"
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
import Settings from "@/assets/icons/mentor/settings.svg"
import Message from "@/assets/icons/mentor/message-square-text.svg"
import Target from "@/assets/icons/mentor/target.svg"
import ChevronRight from "@/assets/icons/mentor/chevron-right.svg"
import Check from "@/assets/icons/mentor/check.svg"
import Profile from "@/assets/icons/mentor/user-round.svg"
import Camera from "@/assets/icons/mentor/camera.svg"
import Microphone from "@/assets/icons/mentor/mic.svg"
import Stop from "@/assets/icons/mentor/square.svg"

const icons = { sedentary: Armchair, light: Footprints, moderate: Bike, high: Dumbbell, beginner: Sprout, occasional: CalendarClock, regular: CalendarCheck, home: House, gym: Dumbbell, mixed: ArrowLeftRight, custom: PencilLine, weight: Weight, summary: ClipboardCheck, weekly: CalendarDays, chevronDown: ChevronDown, back: ChevronLeft, close: Close, food: Utensils, leaf: Leaf, loss: TrendingDown, gain: TrendingUp, maintain: HeartPulse,
    settings: Settings, message: Message, target: Target, chevronRight: ChevronRight, check: Check, profile: Profile, camera: Camera, microphone: Microphone, stop: Stop }
export type MentorQuestionIconName = keyof typeof icons | "course" | "plus" | "book" | "progress" | "adjust" | "more" | "search" | "clock" | "water" | "trash"
const solidIcons: Partial<Record<MentorQuestionIconName, MentorSolidIconName>> = { food: "nutrition", gym: "workouts", high: "workouts", course: "course", maintain: "wellbeing", message: "chat" }
const utilityPaths = {
    plus: "M12 4v16M4 12h16",
    book: "M12 5v16M12 5C8 2 4 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-2-1-6-2-10 1Z",
    adjust: "M3 6h4m4 0h10M3 12h10m4 0h4M3 18h2m4 0h12",
    search: "m16 16 5 5", clock: "M12 6v6l4 2",
    water: "M12 3C9 7 5 11 5 15a7 7 0 0 0 14 0c0-4-4-8-7-12Z",
    trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7",
}

export function MentorQuestionIcon({ name, size = 26, color }: { name: MentorQuestionIconName; size?: number; color: string }) {
    const solid = solidIcons[name]
    if (solid) return <MentorSolidIcon name={solid} size={size} color={color} />
    if (name in icons) {
        const Icon = icons[name as keyof typeof icons]
        return <View style={{ width: size, height: size, flexShrink: 0 }}><Icon width={size} height={size} stroke={color} color={color} strokeWidth={2.2} accessible={false} /></View>
    }
    return <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" accessible={false}>
        {name in utilityPaths ? <Path d={utilityPaths[name as keyof typeof utilityPaths]} /> : null}
        {name === "search" || name === "clock" ? <Circle cx={name === "search" ? 10 : 12} cy={name === "search" ? 10 : 12} r={name === "search" ? 7 : 9} /> : null}
        {name === "adjust" ? <><Circle cx={9} cy={6} r={2} /><Circle cx={15} cy={12} r={2} /><Circle cx={7} cy={18} r={2} /></> : null}
        {name === "progress" ? [13, 8, 3].map((y, index) => <Rect key={y} x={3 + index * 7} y={y} width={4} height={19 - y} rx={1} fill={color} stroke="none" />) : null}
        {name === "more" ? [5, 12, 19].map(cx => <Circle key={cx} cx={cx} cy={12} r={1.6} fill={color} stroke="none" />) : null}
    </Svg>
}
