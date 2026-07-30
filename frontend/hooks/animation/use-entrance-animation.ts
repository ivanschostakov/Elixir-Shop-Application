import { useEffect, useRef } from "react"
import { Animated, Platform } from "react-native"

import { motion } from "@/theme/motion"

type EntranceAnimationOptions = {
    delay?: number
    duration?: number
    translateY?: number
}

export function useEntranceAnimation({
    delay = 0,
    duration = motion.duration.enter,
    translateY = 8,
}: EntranceAnimationOptions = {}) {
    const shouldAnimate = Platform.OS !== "android"
    const progress = useRef(new Animated.Value(shouldAnimate ? 0 : 1)).current

    useEffect(() => {
        if (!shouldAnimate) {
            progress.setValue(1)
            return
        }

        progress.setValue(0)
        Animated.timing(progress, {
            delay,
            duration,
            easing: motion.easing.enter,
            toValue: 1,
            useNativeDriver: true,
        }).start()
    }, [delay, duration, progress, shouldAnimate])

    return {
        opacity: progress,
        transform: [
            {
                translateY: progress.interpolate({
                    inputRange: [0, 1],
                    outputRange: [translateY, 0],
                }),
            },
        ],
    }
}
