import { useId } from "react"
import { Circle, G, Mask, Path, Rect, Svg } from "react-native-svg"
import type { MealType } from "@/services/api/companion"

export function MentorMealIcon({ meal, filled, color, size = 24 }: { meal: MealType; filled: boolean; color: string; size?: number }) {
    const fill = filled ? color : "none"
    return <Svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" accessible={false}>
        {meal === "breakfast" ? <>
            <Path d="M6 15a6 6 0 0 1 12 0Z" fill={fill} />
            <Path d="M3 15h18M5 19h14M12 3v2M4.2 7.2l1.4 1.4M18.4 8.6l1.4-1.4M2 12h2M20 12h2" />
        </> : null}
        {meal === "lunch" ? <>
            <Circle cx={12} cy={12} r={4.5} fill={fill} />
            <Path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </> : null}
        {meal === "dinner" ? <>
            <Path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z" fill={fill} />
            <Path d="m17.5 2 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8Z" fill={fill} strokeWidth={1.3} />
        </> : null}
    </Svg>
}

/** Shared solid glyphs for navigation, onboarding, summaries and actions. */
export type MentorSolidIconName = "nutrition" | "workouts" | "course" | "chat" | "wellbeing"
export function MentorSolidIcon({ name, color, size = 24 }: { name: MentorSolidIconName; color: string; size?: number }) {
    const cutout = `mentor-icon-${useId().replace(/[^a-zA-Z0-9]/g, "")}`
    return <Svg width={size} height={size} viewBox="0 0 24 24" accessible={false}>
        {name === "nutrition" ? <>
            <Path d="M3 2a1 1 0 0 1 1 1v5h2V3a1 1 0 1 1 2 0v5h2V3a1 1 0 1 1 2 0v5a5 5 0 0 1-3.5 4.77V21a1.5 1.5 0 0 1-3 0v-8.23A5 5 0 0 1 2 8V3a1 1 0 0 1 1-1Z" fill={color} />
            <Path d="M20.5 2c-3.1 0-5.5 3.5-5.5 8v3a1 1 0 0 0 1 1h3v7a1.5 1.5 0 0 0 3 0V3.5A1.5 1.5 0 0 0 20.5 2Z" fill={color} />
        </> : null}
        {name === "workouts" ? <G rotation={-45} origin="12, 12" fill={color}>
            <Rect x={8} y={10.5} width={8} height={3} rx={1} />
            <Rect x={5} y={5} width={4} height={14} rx={1.5} />
            <Rect x={15} y={5} width={4} height={14} rx={1.5} />
            <Rect x={2} y={8} width={3} height={8} rx={1.2} />
            <Rect x={19} y={8} width={3} height={8} rx={1.2} />
        </G> : null}
        {name === "course" ? <>
            <Rect x={6} y={2} width={12} height={4} rx={1.2} fill={color} />
            <Mask id={cutout} x={0} y={0} width={24} height={24} maskUnits="userSpaceOnUse"><Rect width={24} height={24} fill="#FFFFFF" /><Rect x={8} y={13.5} width={8} height={4.5} rx={0.8} fill="#000000" /></Mask>
            <Path d="M8 7h8v2l3 3v8a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-8l3-3V7Z" fill={color} mask={`url(#${cutout})`} />
        </> : null}
        {name === "wellbeing" ? <>
            <Mask id={cutout} x={0} y={0} width={24} height={24} maskUnits="userSpaceOnUse"><Rect width={24} height={24} fill="#FFFFFF" /><Path d="M3.5 11h4l2-4 3.5 9 2.5-5h5" fill="none" stroke="#000000" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" /></Mask>
            <Path d="M12 21s-10-5.9-10-12.3C2 5.3 4.5 3 7.5 3c1.9 0 3.5 1 4.5 2.4C13 4 14.6 3 16.5 3 19.5 3 22 5.3 22 8.7 22 15.1 12 21 12 21Z" fill={color} mask={`url(#${cutout})`} />
        </> : null}
        {name === "chat" ? <>
            <Mask id={cutout} x={0} y={0} width={24} height={24} maskUnits="userSpaceOnUse"><Rect width={24} height={24} fill="#FFFFFF" /><Path d="M6.5 7h11M6.5 11h11M6.5 15h7" stroke="#000000" strokeWidth={1.7} strokeLinecap="round" /></Mask>
            <Path d="M5 2h14a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H8l-5 3a.65.65 0 0 1-1-.55V5a3 3 0 0 1 3-3Z" fill={color} mask={`url(#${cutout})`} />
        </> : null}
    </Svg>
}
