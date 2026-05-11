import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Animated, Pressable, Text, View, type LayoutChangeEvent } from "react-native"

import { contentStyles } from "@/components/content/content.styles"
import type { ContentTabBarProps } from "@/components/content/content-tab-bar.types"
export type { ContentTabBarItem } from "@/components/content/content-tab-bar.types"

type TabLayout = {
    width: number
    x: number
}

export function ContentTabBar({ tabs, variant = "default" }: ContentTabBarProps) {
    const activeTabKey = tabs.find((tab) => tab.isActive)?.key ?? tabs[0]?.key ?? null
    const tabSignature = useMemo(() => tabs.map((tab) => tab.key).join("|"), [tabs])
    const [tabLayouts, setTabLayouts] = useState<Record<string, TabLayout>>({})
    const indicatorX = useRef(new Animated.Value(0)).current
    const indicatorWidth = useRef(new Animated.Value(0)).current
    const hasMountedIndicator = useRef(false)
    const previousTabSignature = useRef(tabSignature)

    useEffect(() => {
        if (previousTabSignature.current === tabSignature) {
            return
        }

        previousTabSignature.current = tabSignature
        setTabLayouts({})
        hasMountedIndicator.current = false
        indicatorX.setValue(0)
        indicatorWidth.setValue(0)
    }, [indicatorWidth, indicatorX, tabSignature])

    useEffect(() => {
        if (!activeTabKey) {
            return
        }

        const activeLayout = tabLayouts[activeTabKey]

        if (!activeLayout) {
            return
        }

        if (!hasMountedIndicator.current) {
            indicatorX.setValue(activeLayout.x)
            indicatorWidth.setValue(activeLayout.width)
            hasMountedIndicator.current = true
            return
        }

        Animated.parallel([
            Animated.timing(indicatorX, {
                duration: 180,
                toValue: activeLayout.x,
                useNativeDriver: false,
            }),
            Animated.timing(indicatorWidth, {
                duration: 180,
                toValue: activeLayout.width,
                useNativeDriver: false,
            }),
        ]).start()
    }, [activeTabKey, indicatorWidth, indicatorX, tabLayouts])

    const handleTabLayout = useCallback((tabKey: string, event: LayoutChangeEvent) => {
        const { width, x } = event.nativeEvent.layout

        setTabLayouts((currentLayouts) => {
            const existingLayout = currentLayouts[tabKey]

            if (existingLayout && existingLayout.width === width && existingLayout.x === x) {
                return currentLayouts
            }

            return {
                ...currentLayouts,
                [tabKey]: { width, x },
            }
        })
    }, [])

    const showIndicator = activeTabKey ? Boolean(tabLayouts[activeTabKey]) : false

    return (
        <View style={contentStyles.topTabBar}>
            {tabs.map((tab) => (
                <Pressable
                    key={tab.key}
                    accessibilityRole="button"
                    accessibilityState={{ selected: tab.isActive }}
                    onLayout={(event) => {
                        handleTabLayout(tab.key, event)
                    }}
                    onPress={tab.onPress}
                    style={({ pressed }) => [
                        contentStyles.topTabButton,
                        pressed && contentStyles.topTabButtonPressed,
                    ]}
                >
                    <Text
                        style={[
                            contentStyles.topTabLabel,
                            variant === "onColor" && contentStyles.topTabLabelOnColor,
                            tab.isActive && contentStyles.topTabLabelActive,
                            tab.isActive && variant === "onColor" && contentStyles.topTabLabelActiveOnColor,
                        ]}
                    >
                        {tab.label}
                    </Text>
                </Pressable>
            ))}
            {showIndicator ? (
                <Animated.View
                    pointerEvents="none"
                    style={[
                        contentStyles.topTabIndicator,
                        variant === "onColor" && contentStyles.topTabIndicatorOnColor,
                        {
                            transform: [{ translateX: indicatorX }],
                            width: indicatorWidth,
                        },
                    ]}
                />
            ) : null}
        </View>
    )
}
