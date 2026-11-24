import { useEffect, useRef, useState } from "react"
import { StyleSheet, Text, View } from "react-native"
import LottieView from "lottie-react-native"
import confetti from "@/assets/stickers/nutrition-confetti.json"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { numeric } from "@/screens/chat/mentor-data"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import type { MentorDashboard } from "@/services/api/companion"

const goals = ["kcal", "protein", "fat", "carbs", "water"] as const
type Goal = typeof goals[number]
type Today = MentorDashboard["today"]
const titles = {
    kcal: "Цель по калориям достигнута!",
    protein: "Цель по белку достигнута!",
    fat: "Цель по жирам достигнута!",
    carbs: "Цель по углеводам достигнута!",
    water: "Цель по воде достигнута!",
} as const

function values(today: Today, goal: Goal) {
    return goal === "water"
        ? { amount: numeric(today.water?.consumed_ml), target: numeric(today.water?.target_ml) }
        : { amount: numeric(today.nutrition.consumed[goal]), target: numeric(today.nutrition.target?.[goal]) }
}

/** The parent keys this component to one profile and one local day. */
export function MentorGoalCelebration({ today, visible, top }: { today: Today; visible: boolean; top: number }) {
    const previous = useRef<Today | null>(null)
    const reached = useRef(new Set<Goal>())
    const [achievement, setAchievement] = useState<Goal[]>([])
    const reducedMotion = useChatReducedMotion()
    const colors = useMentorPalette()

    useEffect(() => {
        // Compare the totals once the editor closes so the receipt is visible.
        if (!visible && previous.current) return
        const crossed: Goal[] = []
        for (const goal of goals) {
            const { amount, target } = values(today, goal)
            if (target === null || target <= 0 || amount === null || amount < target || reached.current.has(goal)) continue
            const before = previous.current && values(previous.current, goal)
            if (before && before.target === target && before.amount !== null && before.amount < target) crossed.push(goal)
            reached.current.add(goal)
        }
        previous.current = today
        if (crossed.length) setAchievement(crossed)
    }, [today, visible])

    useEffect(() => {
        if (!achievement.length) return
        if (!visible) {
            setAchievement([])
            return
        }
        const timer = setTimeout(() => setAchievement([]), 3200)
        return () => clearTimeout(timer)
    }, [achievement, visible])

    if (!visible || !achievement.length) return null
    return <View testID="mentor-goal-celebration" pointerEvents="none" style={[styles.overlay, { top }]}>
        {!reducedMotion && <LottieView key={achievement.join("-")} source={confetti} autoPlay loop={false} resizeMode="contain" style={styles.animation} webStyle={{ width: "100%", height: "100%", position: "absolute" }} />}
        <Text accessibilityRole="alert" style={[styles.title, { color: colors.green, backgroundColor: colors.mint }]}>
            {achievement.length === 1 ? mt(titles[achievement[0]]) : mt("Достигнуты дневные цели · {0}", [
                achievement.map(goal => mt({ kcal: "Калории", protein: "Белки", fat: "Жиры", carbs: "Углеводы", water: "Вода" }[goal])).join(", "),
            ])}
        </Text>
    </View>
}

const styles = StyleSheet.create({
    overlay: { position: "absolute", left: 0, right: 0, height: 190, alignItems: "center", justifyContent: "center", zIndex: 12 },
    animation: { ...StyleSheet.absoluteFillObject, width: "100%", height: "100%" },
    title: { maxWidth: "88%", overflow: "hidden", borderRadius: 15, paddingVertical: 9, paddingHorizontal: 16, textAlign: "center", fontSize: 16, fontWeight: "700" },
})
