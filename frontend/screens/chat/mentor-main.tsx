import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react"
import { Keyboard, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { SafeAreaInsetsContext } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { CompanionPanel, type useCompanion } from "@/screens/chat/companion"
import { MentorHomeHeader, MentorHomeScreen, mentorHomeStyles } from "@/screens/chat/mentor-home"
import { mentorHomeData } from "@/screens/chat/mentor-home-data"
import { MentorBottomNavigation, MentorTabPages, mentorTabLabel, type MentorTab } from "@/screens/chat/mentor-navigation"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"

type Controller = ReturnType<typeof useCompanion>
export type MentorChatRenderer = (props: { active: boolean; onBack: () => void }) => ReactNode
const unchanged = async () => {}
const zeroInsets = { top: 0, bottom: 0, left: 0, right: 0 }

export function MentorMainScreen({ controller: c, onClose, renderChat, onContinue, visible = true, initialTab = "nutrition" }: {
    controller: Controller; onClose: () => void; renderChat: MentorChatRenderer; onContinue: () => void; visible?: boolean; initialTab?: MentorTab
}) {
    useLanguage()
    const colors = useMentorPalette()
    const [tab, setTab] = useState<MentorTab>(initialTab)
    const [settingsOpen, setSettingsOpen] = useState(false)
    const [chatVisited, setChatVisited] = useState(initialTab === "chat")
    const [keyboardVisible, setKeyboardVisible] = useState(false)
    const [entrance, setEntrance] = useState(0)
    const callbacks = useRef(c); callbacks.current = c
    useLayoutEffect(() => { if (visible) { setTab(initialTab); setSettingsOpen(false); if (initialTab === "chat") setChatVisited(true); setEntrance(value => value + 1); void callbacks.current.refresh() } }, [visible, initialTab])
    useEffect(() => {
        const show = Keyboard.addListener(Platform.OS === "ios" ? "keyboardWillShow" : "keyboardDidShow", event => { Keyboard.scheduleLayoutAnimation(event); setKeyboardVisible(true) })
        const hide = Keyboard.addListener(Platform.OS === "ios" ? "keyboardWillHide" : "keyboardDidHide", event => { Keyboard.scheduleLayoutAnimation(event); setKeyboardVisible(false) })
        return () => { show.remove(); hide.remove() }
    }, [])
    const select = (next: MentorTab) => { Keyboard.dismiss(); c.setEditor(null); setSettingsOpen(false); if (next === "chat") setChatVisited(true); setTab(next) }
    const settings: { label: string; icon: MentorQuestionIconName; action: () => void }[] = [
        { label: mt("Мой профиль"), icon: "profile", action: () => c.setEditor({ page: "profile" }) },
        { label: mt("Настроить питание"), icon: "food", action: () => c.setEditor({ page: "nutrition" }) },
        { label: mt("Записать вес"), icon: "weight", action: () => c.setEditor({ page: "weight" }) },
        { label: mt("Настройки и напоминания"), icon: "settings", action: () => c.setEditor({ page: "settings" }) },
        ...(mentorHomeData(c.state, c.clock).optionalIncomplete ? [{ label: mt("Продолжить заполнение"), icon: "custom" as const, action: onContinue }] : []),
    ]
    const render = (page: MentorTab) => {
        if (page === "nutrition") return <MentorHomeScreen state={c.state} clock={c.clock} animationKey={entrance} error={c.error} busy={c.busy} onRefresh={() => void c.refresh()} onClose={onClose}
            onSettings={() => setSettingsOpen(true)} onAddFood={() => c.setEditor({ page: "meal" })} onNutrition={() => c.setEditor({ page: "nutrition" })}
            onMeal={entry => c.setEditor({ page: "meal", entry })} onJournal={() => c.setEditor({ page: "journal" })} />
        if (page === "chat") return chatVisited ? <SafeAreaInsetsContext.Provider value={zeroInsets}>{renderChat({ active: visible && tab === "chat" && !settingsOpen, onBack: () => select("nutrition") })}</SafeAreaInsetsContext.Provider> : null
        return <View style={styles.fill}><MentorHomeHeader title={mentorTabLabel(page)} onBack={() => select("nutrition")} onSettings={() => setSettingsOpen(true)} />
            <View testID={`mentor-placeholder-${page}`} style={styles.placeholder}><View style={[styles.placeholderIcon, { backgroundColor: colors.soft }]}><MentorQuestionIcon name={page === "workouts" ? "gym" : "maintain"} size={38} color={colors.green} /></View>
                <Text accessibilityRole="header" style={[styles.placeholderTitle, { color: colors.text }]}>{mentorTabLabel(page)}</Text><Text style={[styles.placeholderCopy, { color: colors.muted }]}>{mt("Раздел скоро появится")}</Text></View></View>
    }
    return <View style={[styles.fill, { backgroundColor: colors.surface }]}>
        <View style={[styles.fill, settingsOpen && styles.hidden]} pointerEvents={settingsOpen ? "none" : "auto"} accessibilityElementsHidden={settingsOpen} importantForAccessibility={settingsOpen ? "no-hide-descendants" : "auto"}><MentorTabPages active={tab} render={render} onSelect={select} /></View>
        {settingsOpen ? <View style={styles.fill}><MentorHomeHeader title={mt("Настройки")} onBack={() => setSettingsOpen(false)} /><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={mentorHomeStyles.body}>{settings.map(item => <Pressable key={item.label} accessibilityRole="button" accessibilityLabel={item.label} onPress={item.action} style={({ pressed }) => [styles.setting, { borderBottomColor: colors.border, opacity: pressed ? 0.65 : 1 }]}><MentorQuestionIcon name={item.icon} color={colors.green} /><Text style={[styles.settingText, { color: colors.text }]}>{item.label}</Text><MentorQuestionIcon name="chevronRight" size={20} color={colors.muted} /></Pressable>)}</ScrollView></View> : null}
        {!(tab === "chat" && keyboardVisible && !settingsOpen) ? <MentorBottomNavigation active={tab} onSelect={select} /> : null}
        <CompanionPanel controller={c} onChanged={unchanged} workspaceVisible navigationVisible={false} />
    </View>
}

const styles = StyleSheet.create({ fill: { flex: 1, minHeight: 0 }, hidden: { display: "none" }, setting: { minHeight: 64, flexDirection: "row", gap: 14, alignItems: "center", paddingVertical: 15, borderBottomWidth: StyleSheet.hairlineWidth }, settingText: { flex: 1, fontSize: 17, lineHeight: 24 },
    placeholder: { flex: 1, padding: 32, alignItems: "center", justifyContent: "center", gap: 14 }, placeholderIcon: { width: 78, height: 78, borderRadius: 26, alignItems: "center", justifyContent: "center" }, placeholderTitle: { fontSize: 25, fontWeight: "700" }, placeholderCopy: { fontSize: 16, textAlign: "center", lineHeight: 23 } })
