import { useState } from "react"
import { Keyboard, Modal, Pressable, StyleSheet, Text, View } from "react-native"
import { Picker } from "@react-native-picker/picker"
import { useLanguage } from "@/providers/language-provider"
import { AppPickerPanel } from "@/components/platform/app-picker"
import type { AppTimePickerProps } from "./app-date-time-picker"

const digits = (n: number) => String(n).padStart(2, "0")
const hours = Array.from({ length: 24 }, (_, i) => digits(i))
const minutes = Array.from({ length: 60 }, (_, i) => digits(i))

export function AppTimePicker({ label, value, onChange, disabled, dark, colors }: AppTimePickerProps) {
    const { t } = useLanguage()
    const [draft, setDraft] = useState<string | null>(null)
    const [hour, minute] = (draft ?? value).split(":")
    const close = () => setDraft(null)

    return <>
        <Pressable accessibilityRole="button" accessibilityLabel={label + ", " + value} disabled={disabled}
            accessibilityState={{ disabled }} style={[styles.button, { backgroundColor: dark ? "#263A31" : "#EAF3ED", opacity: disabled ? 0.5 : 1 }]}
            onPress={() => { Keyboard.dismiss(); setDraft(value) }}>
            <Text style={[styles.time, { color: dark ? "#B9E7C9" : "#235C42" }]}>{value}</Text>
        </Pressable>
        {draft !== null && <Modal transparent animationType="fade" onRequestClose={close}>
            <AppPickerPanel title={label} onCancel={close} onConfirm={() => { if (!disabled) onChange(draft); close() }}>
                <View style={styles.fields}>
                    <Picker accessibilityLabel={t("time.hours")} selectedValue={hour} style={[styles.field, { color: colors.text }]}
                        dropdownIconColor={colors.text} onValueChange={next => setDraft(current => current && next + ":" + current.split(":")[1])}>
                        {hours.map(h => <Picker.Item key={h} label={h} value={h} />)}
                    </Picker>
                    <Text style={{ color: colors.text }}>:</Text>
                    <Picker accessibilityLabel={t("time.minutes")} selectedValue={minute} style={[styles.field, { color: colors.text }]}
                        dropdownIconColor={colors.text} onValueChange={next => setDraft(current => current && current.split(":")[0] + ":" + next)}>
                        {minutes.map(m => <Picker.Item key={m} label={m} value={m} />)}
                    </Picker>
                </View>
            </AppPickerPanel>
        </Modal>}
    </>
}

const styles = StyleSheet.create({
    button: { alignSelf: "flex-end", minHeight: 44, minWidth: 78, paddingHorizontal: 12, borderRadius: 14, alignItems: "center", justifyContent: "center" },
    time: { fontSize: 19, fontWeight: "700", fontVariant: ["tabular-nums"] },
    fields: { flexDirection: "row", alignItems: "center" },
    field: { flex: 1 },
})
