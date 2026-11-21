import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react"
import { InteractionManager, Keyboard, Pressable, ScrollView, StyleSheet, Text, View } from "react-native"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { mentorText as mt } from "@/i18n/mentor-translations"
import { useLanguage } from "@/providers/language-provider"
import { CompanionPanel, type useCompanion } from "@/screens/chat/companion"
import { MentorHomeHeader, MentorHomeScreen, mentorHomeStyles } from "@/screens/chat/mentor-home"
import { getNavigationFooterHeight } from "@/components/footer/sticky-footer.styles"
import { mentorHomeData } from "@/screens/chat/mentor-home-data"
import { MentorBottomNavigation, MentorTabPages, mentorTabLabel, mentorTabs, type MentorPage, type MentorTab } from "@/screens/chat/mentor-navigation"
import { MentorQuestionIcon, type MentorQuestionIconName } from "@/screens/chat/mentor-question-icon"
import { useMentorPalette } from "@/screens/chat/mentor-ui"

type Controller = ReturnType<typeof useCompanion>
export type MentorChatRenderer = (props: { active: boolean; onBack: () => void }) => ReactNode
const unchanged = async () => {}

export function MentorMainScreen({ controller: c, onClose, renderChat, onContinue, visible = true, initialTab = "nutrition" }: {
    controller: Controller; onClose: () => void; renderChat: MentorChatRenderer; onContinue: () => void; visible?: boolean; initialTab?: MentorTab
}) {
    useLanguage()
    const colors = useMentorPalette()
    const { top, bottom } = useSafeAreaInsets()
    const footerHeight = getNavigationFooterHeight(bottom)
    const [navigation, setNavigation] = useState({ tab: initialTab, settingsOpen: false, direction: 1, revision: 0 })
    const { tab, settingsOpen, direction, revision } = navigation
    const route = useRef(navigation); route.current = navigation
    const [chatInteractive, setChatInteractive] = useState(initialTab === "chat")
    const [chatVisited, setChatVisited] = useState(initialTab === "chat")
    const [entrance, setEntrance] = useState(0)
    const callbacks = useRef(c); callbacks.current = c
    useLayoutEffect(() => {
        if (!visible) return
        setNavigation({ tab: initialTab, settingsOpen: false, direction: 1, revision: 0 }); setChatInteractive(initialTab === "chat")
        if (initialTab === "chat") setChatVisited(true)
        setEntrance(value => value + 1); void callbacks.current.refresh()
    }, [visible, initialTab])
    useEffect(() => {
        if (!visible || chatVisited) return
        let idle: ReturnType<typeof InteractionManager.runAfterInteractions> | undefined
        // Prepare the retained composer after the modal's entrance, with no API request.
        const timer = setTimeout(() => { idle = InteractionManager.runAfterInteractions(() => setChatVisited(true)) }, 350)
        return () => { clearTimeout(timer); idle?.cancel() }
    }, [visible, chatVisited])
    const select = useCallback((next: MentorTab) => {
        const current = route.current
        if (current.tab === next && !current.settingsOpen) return
        Keyboard.dismiss(); callbacks.current.setEditor(null); setChatInteractive(false)
        if (next === "chat") setChatVisited(true)
        const destination = { tab: next, settingsOpen: false, direction: mentorTabs.indexOf(next) > (current.settingsOpen ? 4 : mentorTabs.indexOf(current.tab)) ? 1 : -1, revision: current.revision + 1 }
        route.current = destination; setNavigation(destination)
    }, [])
    const backToMenu = useCallback(() => select("nutrition"), [select])
    const openSettings = () => { Keyboard.dismiss(); setNavigation(current => ({ ...current, settingsOpen: true, direction: 1, revision: current.revision + 1 })) }
    const closeSettings = () => setNavigation(current => ({ ...current, settingsOpen: false, direction: -1, revision: current.revision + 1 }))
    const settled = useCallback((page: MentorPage) => { if (page === (route.current.settingsOpen ? "settings" : route.current.tab)) setChatInteractive(page === "chat") }, [])
    const settings: { label: string; icon: MentorQuestionIconName; action: () => void }[] = [
        { label: mt("Мой профиль"), icon: "profile", action: () => c.setEditor({ page: "profile" }) },
        { label: mt("Настроить питание"), icon: "food", action: () => c.setEditor({ page: "nutrition" }) },
        { label: mt("Записать вес"), icon: "weight", action: () => c.setEditor({ page: "weight" }) },
        { label: mt("Настройки и напоминания"), icon: "settings", action: () => c.setEditor({ page: "settings" }) },
        ...(mentorHomeData(c.state, c.clock).optionalIncomplete ? [{ label: mt("Продолжить заполнение"), icon: "custom" as const, action: onContinue }] : []),
    ]
    const render = (page: MentorPage) => {
        if (page === "nutrition") return <View style={[styles.fill, { paddingTop: top, paddingBottom: footerHeight }]}><MentorHomeScreen state={c.state} clock={c.clock} animationKey={entrance} error={c.error} busy={c.busy} onRefresh={() => void c.refresh()} onClose={onClose}
            onSettings={openSettings} onAddFood={() => c.setEditor({ page: "meal" })} onNutrition={() => c.setEditor({ page: "nutrition" })}
            onMeal={entry => c.setEditor({ page: "meal", entry })} onJournal={() => c.setEditor({ page: "journal" })} /></View>
        if (page === "chat") return chatVisited ? <View style={styles.fill}>{renderChat({ active: visible && tab === "chat" && chatInteractive && !settingsOpen, onBack: backToMenu })}</View> : null
        if (page === "settings") return <View style={[styles.fill, { paddingTop: top, paddingBottom: footerHeight }]}><MentorHomeHeader title={mt("Настройки")} onBack={closeSettings} /><ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={mentorHomeStyles.body}>{settings.map(item => <Pressable key={item.label} accessibilityRole="button" accessibilityLabel={item.label} onPress={item.action} style={({ pressed }) => [styles.setting, { borderBottomColor: colors.border, opacity: pressed ? 0.65 : 1 }]}><MentorQuestionIcon name={item.icon} color={colors.green} /><Text style={[styles.settingText, { color: colors.text }]}>{item.label}</Text><MentorQuestionIcon name="chevronRight" size={20} color={colors.muted} /></Pressable>)}</ScrollView></View>
        return <View style={[styles.fill, { paddingTop: top, paddingBottom: footerHeight }]}><MentorHomeHeader title={mentorTabLabel(page)} backLabel={mt("На главную магазина")} onBack={onClose} onSettings={openSettings} />
            <View testID={`mentor-placeholder-${page}`} style={styles.placeholder}><View style={[styles.placeholderIcon, { backgroundColor: colors.soft }]}><MentorQuestionIcon name={page === "workouts" ? "gym" : "maintain"} size={38} color={colors.green} /></View>
                <Text accessibilityRole="header" style={[styles.placeholderTitle, { color: colors.text }]}>{mentorTabLabel(page)}</Text><Text style={[styles.placeholderCopy, { color: colors.muted }]}>{mt("Раздел скоро появится")}</Text></View></View>
    }
    return <View style={[styles.fill, { backgroundColor: colors.surface }]}>
        <MentorTabPages active={settingsOpen ? "settings" : tab} direction={direction} transitionKey={revision} render={render} onSelect={select} onSettled={settled}
            footerHeight={footerHeight} footerVisible={tab !== "chat" || settingsOpen} footer={<MentorBottomNavigation active={tab} onSelect={select} />} />
        <CompanionPanel controller={c} onChanged={unchanged} workspaceVisible navigationVisible={false} />
    </View>
}

const styles = StyleSheet.create({ fill: { flex: 1, minHeight: 0 }, setting: { minHeight: 64, flexDirection: "row", gap: 14, alignItems: "center", paddingVertical: 15, borderBottomWidth: StyleSheet.hairlineWidth }, settingText: { fontWeight: "600", flex: 1, fontSize: 17, lineHeight: 24 },
    placeholder: { flex: 1, padding: 32, alignItems: "center", justifyContent: "center", gap: 14 }, placeholderIcon: { width: 78, height: 78, borderRadius: 26, alignItems: "center", justifyContent: "center" }, placeholderTitle: { fontSize: 25, fontWeight: "800" }, placeholderCopy: { fontWeight: "500", fontSize: 16, textAlign: "center", lineHeight: 23 } })
