import { useEffect, useRef } from "react"
import { ActivityIndicator, Animated, Pressable, StyleSheet, View } from "react-native"
import Svg, { Path, Rect } from "react-native-svg"

import { useLanguage } from "@/providers/language-provider"
import { useTheme } from "@/providers/theme-provider"
import { useChatReducedMotion } from "@/screens/chat/chat-mode-transition"
import { motion } from "@/theme/motion"

export function AdminComposerAction({ active, backgroundColor, busy, disabled, onPress, recording, transcribing }: {
    active: boolean
    backgroundColor: string
    busy: boolean
    disabled: boolean
    onPress: () => void
    recording: boolean
    transcribing: boolean
}) {
    const { t } = useLanguage()
    const { palette } = useTheme()
    const reducedMotion = useChatReducedMotion()
    const state = busy ? "busy" : recording ? "stop" : active ? "send" : "mic"
    const values = useRef({
        mic: new Animated.Value(state === "mic" ? 1 : 0),
        send: new Animated.Value(state === "send" ? 1 : 0),
        stop: new Animated.Value(state === "stop" ? 1 : 0),
        busy: new Animated.Value(state === "busy" ? 1 : 0),
    }).current

    useEffect(() => {
        const keys = ["mic", "send", "stop", "busy"] as const
        if (reducedMotion) {
            keys.forEach((key) => values[key].setValue(key === state ? 1 : 0))
            return
        }
        const animation = Animated.parallel(keys.map((key) => Animated.timing(values[key], {
            toValue: key === state ? 1 : 0,
            duration: motion.duration.standard,
            easing: motion.easing.standard,
            useNativeDriver: true,
        })))
        animation.start()
        return () => animation.stop()
    }, [reducedMotion, state, values])

    const label = {
        mic: t("chat.voiceRecordAction"),
        send: t("chat.sendAction"),
        stop: t("chat.voiceStopAction"),
        busy: t(transcribing ? "chat.voiceTranscribing" : "chat.sending"),
    }[state]

    return (
        <Pressable
            accessibilityLabel={label}
            accessibilityRole="button"
            accessibilityState={{ busy, disabled }}
            disabled={disabled}
            onPress={onPress}
            style={({ pressed }) => [styles.button, { opacity: pressed ? 0.82 : disabled && !busy ? 0.5 : 1 }]}
        >
            <View pointerEvents="none" style={[styles.background, { backgroundColor, borderColor: palette.border }]} />
            <Animated.View pointerEvents="none" style={[styles.layer, { opacity: values.mic, transform: [{ scale: values.mic.interpolate({ inputRange: [0, 1], outputRange: [0.76, 1] }) }] }]}>
                <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
                    <Path d="M12 15a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v7a3 3 0 0 0 3 3ZM5.5 11.5v.5a6.5 6.5 0 0 0 13 0v-.5M12 18.5V22m-3 0h6" stroke={palette.text} strokeWidth={1.8} strokeLinecap="round" />
                </Svg>
            </Animated.View>
            <Animated.View pointerEvents="none" style={[styles.layer, styles.send, { opacity: values.send, transform: [{ scale: values.send.interpolate({ inputRange: [0, 1], outputRange: [0.82, 1] }) }] }]}>
                <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                    <Path d="M21.2 3.4 3.5 10.2c-1.2.5-1.2 1.2-.2 1.5l4.5 1.4 10.5-6.6c.5-.3.9-.1.5.2l-8.5 7.7-.3 4.5c.5 0 .8-.2 1-.5l2.2-2.1 4.6 3.4c.8.5 1.4.2 1.6-.8l3-14.1c.3-1.2-.5-1.8-1.2-1.4Z" fill="#FFFFFF" />
                </Svg>
            </Animated.View>
            <Animated.View pointerEvents="none" style={[styles.layer, { opacity: values.stop }]}>
                <Svg width={22} height={22} viewBox="0 0 24 24">
                    <Rect x={5} y={5} width={14} height={14} rx={3} fill={palette.danger} />
                </Svg>
            </Animated.View>
            <Animated.View pointerEvents="none" style={[styles.layer, { opacity: values.busy }]}>
                <ActivityIndicator animating={busy} color={palette.text} size="small" />
            </Animated.View>
        </Pressable>
    )
}

const styles = StyleSheet.create({
    button: { width: 44, height: 44, flexShrink: 0 },
    background: { ...StyleSheet.absoluteFillObject, borderRadius: 22, borderWidth: StyleSheet.hairlineWidth },
    layer: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center" },
    send: { backgroundColor: "#078BF5", borderRadius: 22 },
})
