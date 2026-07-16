import { useCallback, useEffect, useRef, useState } from "react"
import {
    Animated,
    Dimensions,
    Easing,
    Keyboard,
    Platform,
    View,
    type KeyboardEvent,
    type LayoutChangeEvent,
} from "react-native"
import { usePathname } from "expo-router"

import { BottomActionTemplate } from "@/components/footer/bottom-action-template"
import { BottomNavTemplate } from "@/components/footer/bottom-nav-template"
import { createStickyFooterStyles } from "@/components/footer/sticky-footer.styles"
import type {
    StickyFooterProps,
    StickyFooterSurfaceProps,
} from "@/components/footer/sticky-footer.types"
import { useEntranceAnimation } from "@/hooks/animation/use-entrance-animation"
import { useAppSafeAreaInsets } from "@/hooks/use-app-safe-area-insets"
import { useThemeStyles } from "@/hooks/use-theme-styles"
import { useBasket } from "@/hooks/basket/use-basket"
import { spacing } from "@/theme/spacing"

const DEFAULT_KEYBOARD_ANIMATION_DURATION = 220

type ActionLayout = {
    height: number
    y: number
}

function useFooterSafeAreaStyle() {
    const { bottom } = useAppSafeAreaInsets()

    return {
        paddingBottom: Math.max(spacing.md, bottom),
    }
}

function getKeyboardHeight(event: KeyboardEvent) {
    const screenHeight = Dimensions.get("screen").height
    const keyboardTop = event.endCoordinates?.screenY

    if (typeof keyboardTop === "number") {
        return Math.max(0, screenHeight - keyboardTop)
    }

    return Math.max(0, event.endCoordinates?.height ?? 0)
}

function getKeyboardAnimationDuration(event: KeyboardEvent) {
    return event.duration && event.duration > 0
        ? event.duration
        : DEFAULT_KEYBOARD_ANIMATION_DURATION
}

function useFooterKeyboardLift(enabled: boolean) {
    const translateY = useRef(new Animated.Value(0)).current
    const [keyboardHeight, setKeyboardHeight] = useState(0)
    const [animationDuration, setAnimationDuration] = useState(DEFAULT_KEYBOARD_ANIMATION_DURATION)
    const [footerHeight, setFooterHeight] = useState(0)
    const [actionLayout, setActionLayout] = useState<ActionLayout | null>(null)

    const actionBottomGap = actionLayout && footerHeight > 0
        ? Math.max(0, footerHeight - actionLayout.y - actionLayout.height)
        : 0
    const keyboardLift = enabled ? Math.max(0, keyboardHeight - actionBottomGap) : 0

    useEffect(() => {
        if (!enabled || Platform.OS === "web") {
            translateY.setValue(0)
            return
        }

        const showEvent = Platform.OS === "ios" ? "keyboardWillChangeFrame" : "keyboardDidShow"
        const hideEvent = Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide"

        const showSubscription = Keyboard.addListener(showEvent, (event) => {
            Keyboard.scheduleLayoutAnimation(event)
            setAnimationDuration(getKeyboardAnimationDuration(event))
            setKeyboardHeight(getKeyboardHeight(event))
        })
        const hideSubscription = Keyboard.addListener(hideEvent, (event) => {
            Keyboard.scheduleLayoutAnimation(event)
            setAnimationDuration(getKeyboardAnimationDuration(event))
            setKeyboardHeight(0)
        })

        return () => {
            showSubscription.remove()
            hideSubscription.remove()
        }
    }, [enabled, translateY])

    useEffect(() => {
        Animated.timing(translateY, {
            duration: animationDuration,
            easing: keyboardLift > 0 ? Easing.out(Easing.cubic) : Easing.in(Easing.cubic),
            toValue: -keyboardLift,
            useNativeDriver: true,
        }).start()
    }, [animationDuration, keyboardLift, translateY])

    const handleFooterLayout = useCallback((event: LayoutChangeEvent) => {
        const { height } = event.nativeEvent.layout
        setFooterHeight((currentHeight) => currentHeight === height ? currentHeight : height)
    }, [])

    const handleActionLayout = useCallback((event: LayoutChangeEvent) => {
        const { height, y } = event.nativeEvent.layout
        setActionLayout((currentLayout) => {
            if (currentLayout?.height === height && currentLayout.y === y) {
                return currentLayout
            }

            return { height, y }
        })
    }, [])

    return {
        footerKeyboardStyle: {
            transform: [{ translateY }],
        },
        handleActionLayout,
        handleFooterLayout,
    }
}

export function StickyFooterSurface({
    children,
    contentStyle,
    style,
    variant = "default",
}: StickyFooterSurfaceProps) {
    const stickyFooterStyles = useThemeStyles(createStickyFooterStyles)
    const entranceStyle = useEntranceAnimation({ translateY: 10 })
    const footerSafeAreaStyle = useFooterSafeAreaStyle()

    return (
        <Animated.View style={entranceStyle}>
            <View
                style={[
                    stickyFooterStyles.footerBase,
                    stickyFooterStyles.elevatedSurface,
                    footerSafeAreaStyle,
                    style,
                ]}
            >
                <View
                    style={[
                        variant === "search"
                            ? stickyFooterStyles.searchSection
                            : stickyFooterStyles.actionSection,
                        contentStyle,
                    ]}
                >
                    {children}
                </View>
            </View>
        </Animated.View>
    )
}

export default function StickyFooter({ template }: StickyFooterProps) {
    const stickyFooterStyles = useThemeStyles(createStickyFooterStyles)
    const pathname = usePathname()
    const { basket } = useBasket()
    const entranceStyle = useEntranceAnimation({ translateY: 10 })
    const footerSafeAreaStyle = useFooterSafeAreaStyle()
    const hasBasketItems = (basket?.total_quantity ?? 0) > 0
    const showProductAction = template.footer === "nav+productAction"
    const showBasketAction = template.footer === "nav+basketAction" && hasBasketItems
    const showCustomAction = template.footer === "nav+customAction" && Boolean(template.slots?.footer)
    const {
        footerKeyboardStyle,
        handleActionLayout,
        handleFooterLayout,
    } = useFooterKeyboardLift(showProductAction || showBasketAction || showCustomAction)

    if (template.footer === "customSurface") {
        return template.slots?.footer ? <StickyFooterSurface>{template.slots.footer}</StickyFooterSurface> : null
    }

    if (showProductAction || showBasketAction || showCustomAction) {
        return (
            <Animated.View style={entranceStyle}>
                <Animated.View
                    onLayout={handleFooterLayout}
                    style={[
                        stickyFooterStyles.footerBase,
                        stickyFooterStyles.elevatedSurface,
                        footerSafeAreaStyle,
                        footerKeyboardStyle,
                    ]}
                >
                    <View style={stickyFooterStyles.stack}>
                        <View
                            onLayout={handleActionLayout}
                            style={stickyFooterStyles.actionKeyboardLayer}
                        >
                            <View style={stickyFooterStyles.actionSection}>
                                {showCustomAction
                                    ? template.slots?.footer
                                    : <BottomActionTemplate variant={showProductAction ? "product" : "basket"} />}
                            </View>
                        </View>
                        <BottomNavTemplate pathname={pathname} />
                    </View>
                </Animated.View>
            </Animated.View>
        )
    }

    return (
        <Animated.View style={[stickyFooterStyles.footerBase, footerSafeAreaStyle, entranceStyle]}>
            <BottomNavTemplate pathname={pathname} />
        </Animated.View>
    )
}
