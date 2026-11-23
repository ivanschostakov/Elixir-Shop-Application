import Svg, { Path } from "react-native-svg"
import { Keyboard, Platform, Pressable, StyleSheet, Text, View } from "react-native"
import DateTimePicker, { DateTimePickerAndroid, type DateTimePickerEvent } from "@react-native-community/datetimepicker"

export function AppTimePicker({ label, value, onChange, disabled, locale, dark, colors }: {
    label: string; value: string; onChange: (value: string) => void; disabled: boolean; locale: string; dark: boolean
    colors: { surface: string; border: string; text: string; greenBright: string; muted: string }
}) {
    const [hour, minute] = value.split(":").map(Number)
    // Only a wall-clock time is saved. A neutral date keeps today's DST
    // transition from removing a selectable hour from a recurring reminder.
    const selected = new Date(2000, 0, 15, hour, minute, 0, 0)
    const change = (event: DateTimePickerEvent, date?: Date) => {
        if (event.type !== "set" || !date) return
        onChange(`${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`)
    }
    if (Platform.OS === "ios") {
        return <View style={styles.nativeContainer} pointerEvents={disabled ? "none" : "auto"}>
            <DateTimePicker testID={`mentor-native-time-${label}`} accessibilityLabel={label} value={selected} mode="time" display="compact" onChange={change} disabled={disabled}
                locale={locale.startsWith("en") ? "en-GB" : locale} accentColor={colors.greenBright} themeVariant={dark ? "dark" : "light"} style={styles.nativePicker} />
        </View>
    }
    return <Pressable accessibilityRole="button" accessibilityLabel={`${label}: ${value}`} accessibilityState={{ disabled }} disabled={disabled || Platform.OS !== "android"}
        onPress={() => { Keyboard.dismiss(); DateTimePickerAndroid.open({ value: selected, mode: "time", is24Hour: true, onChange: change }) }}
        style={[styles.button, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        <Text style={[styles.time, { color: colors.text }]}>{value}</Text><Svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke={colors.muted} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><Path d="m6 9 6 6 6-6" /></Svg>
    </Pressable>
}

const styles = StyleSheet.create({
    nativeContainer: { alignSelf: "flex-end", minHeight: 44, justifyContent: "center" }, nativePicker: { height: 44 },
    button: { alignSelf: "flex-end", minHeight: 44, paddingHorizontal: 10, borderWidth: 1, borderRadius: 13, flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 7 },
    time: { fontSize: 18, fontWeight: "700", fontVariant: ["tabular-nums"] },
})
