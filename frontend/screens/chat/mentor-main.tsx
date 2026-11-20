import { useLayoutEffect, useRef, useState } from "react"
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { CompanionPanel, type useCompanion } from "@/screens/chat/companion"
import { MentorWorkspace, type MentorComposeMode } from "@/screens/chat/mentor"
import type { MentorPage } from "@/screens/chat/mentor-data"
import { MentorHomeHeader, MentorHomeScreen, mentorHomeStyles } from "@/screens/chat/mentor-home"
import { mentorHomeData } from "@/screens/chat/mentor-home-data"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { MentorStageTransition } from "@/screens/chat/mentor-onboarding-layout"
import { useMentorPalette } from "@/screens/chat/mentor-ui"

type Controller = ReturnType<typeof useCompanion>
const unchanged = async () => {}

export function MentorMainScreen({ controller: c, onClose, onAsk, onContinue, visible = true }: {
    controller: Controller; onClose: () => void; onAsk: (text?: string, mode?: MentorComposeMode) => void; onContinue: () => void; visible?: boolean
}) {
    useLanguage()
    const colors = useMentorPalette()
    const [page, setPage] = useState<MentorPage | "settings">("today")
    const [entrance, setEntrance] = useState(0)
    const callbacks = useRef(c); callbacks.current = c
    useLayoutEffect(() => { if (visible) { setPage("today"); setEntrance(value => value + 1); void callbacks.current.refresh() } }, [visible])
    const setMentorPage: Controller["setMentorPage"] = next => setPage(current => (typeof next === "function" ? next(current === "settings" ? null : current) : next) ?? "today")
    const controller = { ...c, mentorPage: page === "settings" ? null : page, setMentorPage }
    const optionalIncomplete = mentorHomeData(c.state, c.clock).optionalIncomplete
    const settings: { label: string; icon: MentorQuestionIconName; action: () => void }[] = [
        { label: mt("Мой профиль"), icon: "profile", action: () => c.setEditor({ page: "profile" }) },
        { label: mt("Настроить питание"), icon: "food", action: () => c.setEditor({ page: "nutrition" }) },
        { label: mt("Записать вес"), icon: "weight", action: () => c.setEditor({ page: "weight" }) },
        { label: mt("Прогресс"), icon: "target", action: () => setPage("progress") },
        { label: mt("Настройки и напоминания"), icon: "settings", action: () => c.setEditor({ page: "settings" }) },
        ...(optionalIncomplete ? [{ label: mt("Продолжить заполнение"), icon: "custom" as const, action: onContinue }] : []),
    ]
    return <View style={styles.fill}>
        {page === "today" ? <MentorHomeScreen state={c.state} clock={c.clock} animationKey={entrance} error={c.error} busy={c.busy} onRefresh={() => void c.refresh()} onClose={onClose}
            onSettings={() => setPage("settings")} onAddFood={() => c.setEditor({ page: "meal" })} onNutrition={() => c.setEditor({ page: "nutrition" })}
            onMeal={entry => c.setEditor({ page: "meal", entry })} onWellbeing={entry => c.setEditor({ page: "wellbeing", ...(entry ? { entry } : {}) })}
            onWorkout={() => setPage("workouts")} onCourse={() => setPage("course")} onWeight={() => c.setEditor({ page: "weight" })} onAsk={() => onAsk()} onJournal={() => c.setEditor({ page: "journal" })} /> : <>
            <MentorHomeHeader title={page === "settings" ? mt("Настройки") : page === "workouts" ? mt("Тренировки") : page === "course" ? mt("Мой курс") : mt("Наставник")} onBack={() => setPage("today")} />
            <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={mentorHomeStyles.body}>
                <MentorStageTransition key={page}>
                    {page === "settings" ? <View style={styles.settings}>{settings.map(item => <Pressable key={item.label} accessibilityRole="button" accessibilityLabel={item.label} onPress={item.action} style={({ pressed }) => [styles.setting, { borderBottomColor: colors.border, opacity: pressed ? 0.65 : 1 }]}><MentorQuestionIcon name={item.icon} color={colors.green} /><Text style={[styles.settingText, { color: colors.text }]}>{item.label}</Text><MentorQuestionIcon name="chevronRight" size={20} color={colors.muted} /></Pressable>)}</View> :
                        <MentorWorkspace controller={controller} embedded onCompose={(mode, text) => onAsk(text, mode)} onPrompt={async text => onAsk(text)} />}
                </MentorStageTransition>
            </ScrollView>
        </>}
        <CompanionPanel controller={controller} onChanged={unchanged} workspaceVisible navigationVisible={false} />
    </View>
}

const styles = StyleSheet.create({
    fill: { flex: 1 }, settings: { gap: 2 }, setting: { minHeight: 64, flexDirection: "row", gap: 14, alignItems: "center", paddingVertical: 15, borderBottomWidth: StyleSheet.hairlineWidth }, settingText: { flex: 1, fontSize: 17, lineHeight: 24 },
})
