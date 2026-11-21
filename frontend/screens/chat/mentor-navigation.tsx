import { useEffect, useRef, useState, type ReactNode } from "react"
import { Animated, StyleSheet, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { PanGestureHandler, State, type PanGestureHandlerStateChangeEvent } from "react-native-gesture-handler"
import { FooterNavRow } from "@/components/footer/footer-nav-row"
import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useTheme } from "@/providers/theme-provider"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { spacing } from "@/theme/spacing"

export const mentorTabs = ["nutrition", "workouts", "wellbeing", "chat"] as const
export type MentorTab = typeof mentorTabs[number]
export const mentorTabLabel = (tab: MentorTab) => ({ nutrition: mt("Питание"), workouts: mt("Тренировки"), wellbeing: mt("Самочувствие"), chat: mt("Чат") })[tab]
const icons: Record<MentorTab, MentorQuestionIconName> = { nutrition: "food", workouts: "gym", wellbeing: "maintain", chat: "message" }

export function MentorBottomNavigation({ active, onSelect }: { active: MentorTab; onSelect: (tab: MentorTab) => void }) {
    const colors = useMentorPalette()
    const { palette } = useTheme()
    const { bottom } = useSafeAreaInsets()
    const styles = createStickyFooterStyles({ ...palette, background: colors.surface })
    return <View testID="mentor-bottom-navigation" style={[styles.footerBase, { paddingBottom: Math.max(spacing.md, bottom) }]}>
        <FooterNavRow tabs items={mentorTabs.map(tab => ({ key: tab, accessibilityLabel: mentorTabLabel(tab), isActive: active === tab,
            icon: <MentorQuestionIcon name={icons[tab]} size={24} color={active === tab ? colors.green : colors.muted} />, onPress: () => onSelect(tab) }))} />
    </View>
}

/** Retain drafts while moving all tabs on the same native-driven track. */
export function MentorTabPages({ active, render, onSelect }: { active: MentorTab; render: (tab: MentorTab) => ReactNode; onSelect: (tab: MentorTab) => void }) {
    const reducedMotion = useChatReducedMotion()
    const progress = useRef(new Animated.Value(mentorTabs.indexOf(active))).current
    const [width, setWidth] = useState(0)
    useEffect(() => {
        if (reducedMotion || !width) { progress.setValue(mentorTabs.indexOf(active)); return }
        const animation = Animated.spring(progress, { toValue: mentorTabs.indexOf(active), damping: 32, stiffness: 300, mass: 1, overshootClamping: true, useNativeDriver: true })
        animation.start(); return () => animation.stop()
    }, [active, progress, reducedMotion, width])
    const swipe = (event: PanGestureHandlerStateChangeEvent) => {
        if (event.nativeEvent.state !== State.END) return
        const { translationX, velocityX } = event.nativeEvent
        const left = translationX < -70 || velocityX < -650
        const right = translationX > 70 || velocityX > 650
        if (!left && !right) return
        const next = Math.max(0, Math.min(mentorTabs.indexOf(active) + (left ? 1 : -1), mentorTabs.length - 1))
        if (mentorTabs[next] !== active) onSelect(mentorTabs[next])
    }
    return <PanGestureHandler activeOffsetX={[-40, 40]} failOffsetY={[-24, 24]} onHandlerStateChange={swipe}><View testID="mentor-tab-pages" onLayout={event => setWidth(event.nativeEvent.layout.width)} style={styles.viewport}>
        {mentorTabs.map((tab, index) => <Animated.View key={tab} testID={`mentor-tab-${tab}`} pointerEvents={active === tab ? "auto" : "none"} accessibilityElementsHidden={active !== tab} importantForAccessibility={active === tab ? "auto" : "no-hide-descendants"}
            style={[StyleSheet.absoluteFill, { opacity: width || active === tab ? 1 : 0, transform: [{ translateX: progress.interpolate({ inputRange: [0, 1, 2, 3], outputRange: mentorTabs.map((_, position) => (index - position) * width) }) }] }]}>{render(tab)}</Animated.View>)}
    </View></PanGestureHandler>
}

const styles = StyleSheet.create({ viewport: { flex: 1, minHeight: 0, overflow: "hidden" } })
