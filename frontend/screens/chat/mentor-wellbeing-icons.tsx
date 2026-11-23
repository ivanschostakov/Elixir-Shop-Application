import HeartPulse from "@/assets/icons/mentor/wellbeing/heart-pulse.svg"
import PencilLine from "@/assets/icons/mentor/wellbeing/pencil-line.svg"
import Frown from "@/assets/icons/mentor/wellbeing/frown.svg"
import Annoyed from "@/assets/icons/mentor/wellbeing/annoyed.svg"
import Meh from "@/assets/icons/mentor/wellbeing/meh.svg"
import Smile from "@/assets/icons/mentor/wellbeing/smile.svg"
import Laugh from "@/assets/icons/mentor/wellbeing/laugh.svg"
import Apple from "@/assets/icons/mentor/wellbeing/apple.svg"
import Soup from "@/assets/icons/mentor/wellbeing/soup.svg"
import Sandwich from "@/assets/icons/mentor/wellbeing/sandwich.svg"
import BatteryWarning from "@/assets/icons/mentor/wellbeing/battery-warning.svg"
import BatteryLow from "@/assets/icons/mentor/wellbeing/battery-low.svg"
import BatteryMedium from "@/assets/icons/mentor/wellbeing/battery-medium.svg"
import BatteryFull from "@/assets/icons/mentor/wellbeing/battery-full.svg"
import BatteryCharging from "@/assets/icons/mentor/wellbeing/battery-charging.svg"
import CloudMoon from "@/assets/icons/mentor/wellbeing/cloud-moon.svg"
import Moon from "@/assets/icons/mentor/wellbeing/moon.svg"
import MoonStar from "@/assets/icons/mentor/wellbeing/moon-star.svg"
import Wind from "@/assets/icons/mentor/wellbeing/wind.svg"
import Waves from "@/assets/icons/mentor/wellbeing/waves.svg"
import Zap from "@/assets/icons/mentor/wellbeing/zap.svg"
import CloudLightning from "@/assets/icons/mentor/wellbeing/cloud-lightning.svg"
import Leaf from "@/assets/icons/mentor/leaf.svg"

export type WellbeingIconName = "face" | "energy" | "moon" | "apple" | "heart" | "stress" | "note"
const faces = [Frown, Annoyed, Meh, Smile, Laugh]
const energy = [BatteryWarning, BatteryLow, BatteryMedium, BatteryFull, BatteryCharging]
const appetite = [Apple, Soup, Sandwich]
const sleep = [CloudMoon, Moon, MoonStar]
const stress = [Leaf, Wind, Waves, Zap, CloudLightning]

/** Each level uses distinct original Lucide geometry, including neutral and happy faces. */
export function WellbeingIcon({ name, size = 24, color, level = 3 }: { name: WellbeingIconName; size?: number; color: string; filled?: boolean; level?: number }) {
    const set = name === "face" ? faces : name === "energy" ? energy : name === "apple" ? appetite : name === "moon" ? sleep : name === "stress" ? stress : null
    const Icon = set?.[Math.max(0, Math.min(set.length - 1, level - 1))]
    if (Icon) return <Icon width={size} height={size} color={color} strokeWidth={1.8} accessible={false} />
    const Mark = name === "heart" ? HeartPulse : PencilLine
    return <Mark width={size} height={size} color={color} strokeWidth={1.8} accessible={false} />
}
