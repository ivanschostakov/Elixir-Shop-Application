import { useState, type ReactNode } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"
import { mentorNumber, mentorText as mt } from "@/i18n/mentor-translations"
import { goalLabels } from "@/screens/chat/mentor-data"
import { MentorQuestionIcon } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"
import type { CompanionState, ProfileData } from "@/services/api/companion"

const activityLabels = { low: "Низкая активность", light: "Лёгкая", moderate: "Умеренная", high: "Высокая" } as const
const weightLabel = (value: ProfileData["target_weight_kg"]) => value == null ? "—" : mt("{0} кг", [mentorNumber(Number(value))])

function Details({ title, rows }: { title: string; rows: [string, string | undefined][] }) {
    const colors = useMentorPalette()
    return <View style={styles.section}>
        <Text accessibilityRole="header" style={[styles.heading, { color: colors.text }]}>{title}</Text>
        {rows.map(([label, value]) => <View key={label} style={[styles.row, { borderBottomColor: colors.border }]}>
            <Text style={[styles.label, { color: colors.muted }]}>{label}</Text>
            <Text style={[styles.value, { color: colors.text }]}>{value || "—"}</Text>
        </View>)}
    </View>
}

export function MentorProfileSummary({ state, onEdit, onContinue, children }: { state: CompanionState; onEdit: () => void; onContinue?: () => void; children: ReactNode }) {
    const colors = useMentorPalette()
    const [manage, setManage] = useState(false)
    const data = state.profile!.data
    const goal = data.goal === "custom" && data.custom_goal ? data.custom_goal : data.goal ? goalLabels[data.goal] : "—"
    return <View style={styles.content}>
        <View style={styles.hero}>
            <View style={styles.heroHeader}><MentorQuestionIcon name="target" color="#C8E9D5" /><Text style={styles.eyebrow}>{mt("Моя цель")}</Text>
                <Pressable accessibilityRole="button" accessibilityLabel={mt("Изменить профиль")} onPress={onEdit} style={styles.edit}><MentorQuestionIcon name="custom" color="#FFFFFF" size={20} /></Pressable></View>
            <Text style={styles.goal}>{goal}</Text>
        </View>
        <View style={styles.metrics}>
            {[[mt("Текущий вес"), weightLabel(state.mentor?.latest_weight?.data.weight_kg)], [mt("Целевой вес"), weightLabel(data.target_weight_kg)]].map(([label, value], index) =>
                <View key={label} style={[styles.metric, index === 1 && { borderLeftColor: colors.border, borderLeftWidth: 1, paddingLeft: 16 }]}>
                    <Text style={[styles.label, { color: colors.muted }]}>{label}</Text><Text style={[styles.number, { color: colors.text }]}>{value}</Text>
                </View>)}
        </View>
        <Details title={mt("Личные данные")} rows={[
            [mt("Возраст"), data.age?.toString()], [mt("Пол"), data.sex ? mt(data.sex === "female" ? "Женский" : "Мужской") : undefined],
            [mt("Рост"), data.height_cm != null ? mentorNumber(Number(data.height_cm)) + " " + mt("см") : undefined],
            [mt("Активность"), data.activity ? mt(activityLabels[data.activity]) : undefined],
        ]} />
        <Details title={mt("Питание")} rows={[[mt("Предпочтения"), data.preferences], [mt("Ограничения"), data.restrictions]]} />
        {onContinue ? <Pressable accessibilityRole="button" onPress={onContinue} style={styles.link}><Text style={[styles.linkText, { color: colors.green }]}>{mt("Продолжить заполнение")}</Text></Pressable> : null}
        <Pressable accessibilityRole="button" accessibilityState={{ expanded: manage }} onPress={() => setManage(!manage)} style={styles.link}>
            <Text style={[styles.label, { color: colors.muted }]}>{mt("Управление данными")}</Text><MentorQuestionIcon name={manage ? "chevronDown" : "chevronRight"} color={colors.muted} size={17} />
        </Pressable>
        {manage ? children : null}
    </View>
}
const styles = StyleSheet.create({
    content: { gap: 20 }, hero: { padding: 18, paddingTop: 10, gap: 4, borderRadius: 20, backgroundColor: "#19583F" },
    heroHeader: { flexDirection: "row", alignItems: "center", gap: 9 }, eyebrow: { color: "#DEEFE4", flex: 1, fontSize: 15, fontWeight: "600" },
    edit: { alignItems: "center", justifyContent: "center", width: 44, height: 44 }, goal: { color: "#FFFFFF", fontSize: 26, lineHeight: 33, fontWeight: "700" },
    metrics: { flexDirection: "row" }, metric: { flex: 1, gap: 6 }, number: { fontSize: 26, fontWeight: "700", fontVariant: ["tabular-nums"] },
    section: { gap: 2 }, heading: { fontSize: 20, fontWeight: "700", marginBottom: 6 }, row: { flexDirection: "row", alignItems: "baseline", gap: 12, borderBottomWidth: StyleSheet.hairlineWidth, paddingVertical: 11 },
    label: { fontSize: 15, lineHeight: 21, flexShrink: 1 }, value: { flex: 1, textAlign: "right", fontSize: 16, lineHeight: 22, fontWeight: "600" },
    link: { flexDirection: "row", minHeight: 44, gap: 6, alignItems: "center" }, linkText: { fontWeight: "700", fontSize: 16 },
})
