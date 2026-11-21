import { useEffect, type ReactNode } from "react"
import { StyleSheet, View, useWindowDimensions } from "react-native"
import { useAppSafeAreaInsets } from "@/hooks/use-app-safe-area-insets"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { PanGestureHandler, State, type PanGestureHandlerStateChangeEvent } from "react-native-gesture-handler"
import { FooterNavRow } from "@/components/footer/footer-nav-row"
import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useTheme } from "@/providers/theme-provider"
import Reanimated, { Easing, ReduceMotion, cancelAnimation, runOnJS, runOnUI, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated"
import { MentorSolidIcon } from "@/screens/chat/mentor-icons"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import { spacing } from "@/theme/spacing"

export const mentorTabs = ["nutrition", "workouts", "wellbeing", "chat"] as const
export type MentorTab = typeof mentorTabs[number]
export type MentorPage = MentorTab | "settings"
const mentorPages: MentorPage[] = [...mentorTabs, "settings"]
const transition = { duration: 240, easing: Easing.bezier(0.22, 0.7, 0.22, 1), reduceMotion: ReduceMotion.System }
export const mentorTabLabel = (tab: MentorTab) => ({ nutrition: mt("Питание"), workouts: mt("Тренировки"), wellbeing: mt("Самочувствие"), chat: mt("Чат") })[tab]

export function MentorBottomNavigation({ active, onSelect }: { active: MentorTab; onSelect: (tab: MentorTab) => void }) {
    const colors = useMentorPalette()
    const { palette } = useTheme()
    const { bottom } = useAppSafeAreaInsets()
    const styles = useThemeStyles(createStickyFooterStyles)
    return <View testID="mentor-bottom-navigation" style={[styles.footerBase, { paddingBottom: Math.max(spacing.md, bottom) }]}>
        <FooterNavRow tabs items={mentorTabs.map(tab => ({ key: tab, accessibilityLabel: mentorTabLabel(tab), isActive: active === tab,
            icon: <MentorSolidIcon name={tab} color={active === tab ? colors.green : palette.mutedText} />, onPress: () => onSelect(tab) }))} />
    </View>
}

/** Move only the departing and destination pages; keep UIKit glass fully opaque. */
function MentorPagePane({ page, active, direction, transitionKey, width, onSettled, children }: { page: MentorPage; active: boolean; direction: number; transitionKey: number; width: number; onSettled: (page: MentorPage) => void; children: ReactNode }) {
    const position = useSharedValue(active ? 0 : 1)
    const selected = useSharedValue(active)
    useEffect(() => {
        runOnUI((shown: boolean, nextDirection: number) => {
            const wasSelected = selected.value
            selected.value = shown
            if (shown) {
                // Reposition only fully offscreen pages; rapid reversals retain the current frame.
                if (Math.abs(position.value) >= 1) position.value = nextDirection
                position.value = withTiming(0, transition, finished => {
                    if (finished) runOnJS(onSettled)(page)
                })
            } else if (wasSelected) {
                // An interrupted incoming page returns to its nearest edge. Other
                // departing pages keep their current animation instead of crossing back.
                const edge = Math.abs(position.value) > 0.001 ? Math.sign(position.value) : -nextDirection
                position.value = withTiming(edge, transition)
            }
        })(active, direction)
    }, [active, direction, transitionKey, position, selected, onSettled, page])
    useEffect(() => () => cancelAnimation(position), [position])
    const motion = useAnimatedStyle(() => ({ transform: [{ translateX: position.value * width }] }))
    return <Reanimated.View testID={`mentor-tab-${page}`} pointerEvents={active ? "auto" : "none"} accessibilityElementsHidden={!active} importantForAccessibility={active ? "auto" : "no-hide-descendants"}
        style={[StyleSheet.absoluteFill, { zIndex: active ? 1 : 0 }, motion]}>{children}</Reanimated.View>
}

function MentorFooterMotion({ visible, height, children }: { visible: boolean; height: number; children: ReactNode }) {
    const shown = useSharedValue(visible ? 1 : 0)
    useEffect(() => { shown.value = withTiming(visible ? 1 : 0, transition) }, [visible, shown])
    const motion = useAnimatedStyle(() => ({ opacity: shown.value, transform: [{ translateY: (1 - shown.value) * (height + spacing.xl) }] }))
    return <Reanimated.View testID="mentor-footer-motion" pointerEvents={visible ? "auto" : "none"} accessibilityElementsHidden={!visible} importantForAccessibility={visible ? "auto" : "no-hide-descendants"} style={[styles.footer, motion]}>{children}</Reanimated.View>
}

export function MentorTabPages({ active, direction, transitionKey, render, onSelect, footer, footerVisible, footerHeight, onSettled }: {
    active: MentorPage; direction: number; transitionKey: number; render: (page: MentorPage) => ReactNode; onSelect: (tab: MentorTab) => void
    footer: ReactNode; footerVisible: boolean; footerHeight: number; onSettled: (page: MentorPage) => void
}) {
    const { width } = useWindowDimensions()
    const swipe = (event: PanGestureHandlerStateChangeEvent) => {
        if (active === "settings" || active === "chat" || active === "nutrition" || event.nativeEvent.state !== State.END) return
        const { translationX, velocityX } = event.nativeEvent
        const left = translationX < -70 || velocityX < -650
        const right = translationX > 70 || velocityX > 650
        if (!left && !right) return
        const next = Math.max(0, Math.min(mentorTabs.indexOf(active) + (left ? 1 : -1), mentorTabs.length - 1))
        if (mentorTabs[next] !== active) onSelect(mentorTabs[next])
    }
    return <PanGestureHandler enabled={active === "workouts" || active === "wellbeing"} activeOffsetX={[-40, 40]} failOffsetY={[-24, 24]} onHandlerStateChange={swipe}><View testID="mentor-tab-pages" style={styles.viewport}>
        {mentorPages.map(page => <MentorPagePane key={page} page={page} active={active === page} direction={direction} transitionKey={transitionKey} width={width} onSettled={onSettled}>{render(page)}</MentorPagePane>)}
        <MentorFooterMotion visible={footerVisible} height={footerHeight}>{footer}</MentorFooterMotion>
    </View></PanGestureHandler>
}

const styles = StyleSheet.create({ viewport: { flex: 1, minHeight: 0, overflow: "hidden" }, footer: { position: "absolute", left: 0, right: 0, bottom: 0, zIndex: 10 } })
